/* Vésper · aba Robô: "Patrulha ao vivo".
 * Uma rua simulada (postes, luz, obstáculos) e o carrinho do Maker Lab andando nela. Os sensores saem da cena
 * (LDR digital: escuro fora da luz dos postes; ultrassom frontal: distância até o próximo obstáculo) e a decisão
 * é da IA REAL do carrinho: os pesos de tinyml-carrinho.json vêm do ModeloTreinado.h que vai para o ESP32
 * (scripts/exportar_tinyml_web.py). Mesma janela, mesma confirmação (3 seguidas com >= 70%) do firmware.
 * Trecho escuro confirmado = POST /v1/alerta-robo de verdade, como o Vesper.h faz no carrinho.
 * Usa os ajudantes do app.js ($, el, api, JSON_POST, estado, PAULISTA). */
"use strict";
(() => {
  const cena = $("#pt-cena");
  if (!cena) return;
  const ctx = cena.getContext("2d");

  /* ---------------------------------------------------------------- mundo (em cm) */
  const RUA = 3600;                 // 36 m de rua
  const POSTES_X = [300, 750, 1200, 1650, 2100, 2550, 3000, 3450];
  const RAIO_LUZ = 290;             // alcance da luz de um poste no chão
  const VEL = 80;                   // cm/s do carrinho
  const ALCANCE = 300;              // ultrassom: até 3 m
  const PARA_EM = 15;               // para a 15 cm do obstáculo
  const ESPERA_S = 2.4;             // tempo parado (a IA classifica) antes de desviar
  const META = { claro_livre: ["Claro, livre", "#8fa3c7"], claro_obstaculo: ["Claro, obstáculo", "#7fb0ff"],
    escuro_livre: ["Escuro, livre", "#f2d27a"], escuro_obstaculo: ["Escuro, obstáculo", "#ff7a6b"] };

  let IA = null;
  let mundo, robo, sim, rodando = false, ultimoQuadro = 0;

  function cenaPadrao() {
    return { postes: POSTES_X.map((x, i) => ({ x, aceso: i !== 2 && i !== 5 })), obstaculos: [{ x: 1900 }, { x: 2600 }] };
  }
  function cenaAleatoria() {
    const postes = POSTES_X.map((x) => ({ x, aceso: Math.random() > 0.35 }));
    if (postes.every((p) => p.aceso)) postes[2 + Math.floor(Math.random() * 4)].aceso = false;
    const obstaculos = [];
    for (let i = 0, n = 1 + Math.floor(Math.random() * 3); i < n; i++) {
      const x = 700 + Math.random() * 2600;
      if (obstaculos.every((o) => Math.abs(o.x - x) > 350)) obstaculos.push({ x: Math.round(x) });
    }
    return { postes, obstaculos };
  }
  function reiniciar(novoMundo) {
    if (novoMundo) mundo = novoMundo;
    mundo.obstaculos.forEach((o) => { o.passado = false; });
    robo = { x: 60, faixa: 0, modo: "andando", espera: 0, desviando: null, led: "nenhuma", ledAte: 0 };
    sim = { t: 0, acum: 0, janela: [], novas: 0, pendente: -1, rep: 0, confirmado: -1, ultima: null,
      trilha: [], marcas: [], ultimoX: null, trecho: { ativo: false, obstaculo: false }, enviados: 0, fim: false, leitura: null };
    rodando = false;
    $("#pt-play span").textContent = "Patrulhar";
    $("#pt-log").textContent = "";
    $("#pt-alertas").replaceChildren();
    $("#pt-led").dataset.acao = "nenhuma";
    resposta("Nenhum alerta ainda", "Quando a IA confirmar um trecho escuro, o carrinho envia POST /v1/alerta-robo.");
    $("#pt-conf").replaceChildren("Aperte ", el("strong", {}, "Patrulhar"), ": a IA precisa de 1 s de leituras para a primeira decisão.");
    ["#pt-ldr", "#pt-dist", "#pt-gps"].forEach((s) => { $(s).textContent = "--"; });
    desenharProbs(null); atualizarRede(null, null, null);
    log("Carrinho CitizenTech pronto · IA " + (IA ? "carregada (4 → 12 → 4)" : "carregando…"));
    desenhar();
  }

  /* ---------------------------------------------------------------- sensores pela cena */
  const iluminado = (x) => mundo.postes.some((p) => p.aceso && Math.abs(p.x - x) <= RAIO_LUZ);
  function distanciaFrente() {
    const frente = robo.x + 25;
    let d = ALCANCE;
    for (const o of mundo.obstaculos) {
      if (o.passado) continue;
      const gap = o.x - 20 - frente;
      if (gap > -10 && gap < d) d = Math.max(2, gap);
    }
    return d;
  }
  const ruido = (s) => (Math.random() + Math.random() + Math.random() - 1.5) * s;
  function coordenadas(x) {
    const base = estado.local || PAULISTA;
    return { latitude: +(base.lat + 0.0009).toFixed(6), longitude: +(base.lon - 0.002 + (x / RUA) * 0.004).toFixed(6) };
  }

  /* ---------------------------------------------------------------- a IA do carrinho */
  function atributos(j) {
    const d = j.map((l) => l[0]);
    const media = d.reduce((a, b) => a + b, 0) / d.length;
    const varianca = d.reduce((a, b) => a + b * b, 0) / d.length - media * media;
    return [media, Math.min(...d), Math.sqrt(Math.max(0, varianca)), j.reduce((a, l) => a + l[1], 0) / j.length];
  }
  function prever(x) {   // igual a preverRede() do .ino
    const z = x.map((v, i) => (v - IA.media[i]) / IA.escala[i]);
    const h = IA.b1.map((b, j) => Math.max(0, b + z.reduce((s, zi, i) => s + zi * IA.w1[i][j], 0)));
    const lg = IA.b2.map((b, k) => b + h.reduce((s, hj, j) => s + hj * IA.w2[j][k], 0));
    const topo = Math.max(...lg), e = lg.map((v) => Math.exp(v - topo)), tot = e.reduce((a, b) => a + b, 0);
    return { z, h, p: e.map((v) => v / tot) };
  }

  /* ---------------------------------------------------------------- um passo de 100 ms (como amostrar() + inferir()) */
  function passo(dt) {
    // movimento
    const d0 = distanciaFrente();
    if (robo.modo === "andando") {
      const virando = robo.desviando && robo.faixa < 0.7 && robo.x > robo.desviando.x - 75;
      if (d0 <= PARA_EM) { robo.modo = "parado"; robo.espera = 0; log(`obstáculo a ${d0.toFixed(0)} cm: parando`); }
      else robo.x += VEL * dt * (virando ? 0.15 : 1);
    } else if (robo.modo === "parado") {
      robo.espera += dt;
      if (robo.espera >= ESPERA_S) {
        const alvo = mundo.obstaculos.filter((o) => !o.passado && o.x > robo.x).sort((a, b) => a.x - b.x)[0];
        if (alvo) { alvo.passado = true; robo.desviando = alvo; }
        robo.modo = "andando"; log("desviando do obstáculo");
      }
    }
    if (robo.desviando) {
      const o = robo.desviando, fim = o.x + 110;
      robo.faixa = robo.x <= fim ? Math.min(1, robo.faixa + dt * 2.2) : Math.max(0, robo.faixa - dt * 1.6);
      if (robo.x > fim && robo.faixa === 0) robo.desviando = null;
    }
    if (robo.x >= RUA - 80) { robo.x = RUA - 80; terminar(); return; }

    // leitura
    const dist = Math.max(2, distanciaFrente() + ruido(0.9));
    const escuro = iluminado(robo.x) ? 0 : 1;
    sim.leitura = { dist, escuro };
    sim.janela.push([dist, escuro]); if (sim.janela.length > IA.janela) sim.janela.shift();
    sim.novas++;
    if (sim.janela.length < IA.janela || sim.novas < IA.passo) return;
    sim.novas = 0;

    // inferência + confirmação (regra do firmware)
    const x = atributos(sim.janela), r = prever(x);
    const k = r.p.indexOf(Math.max(...r.p)), conf = r.p[k];
    sim.ultima = { x, ...r, k, conf };
    if (conf < IA.escore_min) { sim.pendente = -1; sim.rep = 0; }
    else {
      if (sim.pendente === k) sim.rep++; else { sim.pendente = k; sim.rep = 1; }
      if (sim.rep >= IA.repeticoes && sim.confirmado !== k) { sim.confirmado = k; confirmou(IA.classes[k], conf); }
    }
  }

  function confirmou(classe, conf) {
    log(`[EVENTO] IA confirmou ${classe} (${(conf * 100).toFixed(0)}%)`);
    sim.trilha.push({ x: robo.x, classe });
    if (classe.startsWith("escuro_")) {
      const obst = classe === "escuro_obstaculo";
      if (!sim.trecho.ativo) {
        sim.trecho = { ativo: true, obstaculo: obst };
        if (sim.ultimoX !== null && robo.x - sim.ultimoX < 200) log("mesmo trecho escuro: já avisado");
        else alertar(classe, conf);
      }
      else if (obst && !sim.trecho.obstaculo) { sim.trecho.obstaculo = true; log("obstáculo no trecho escuro: prioridade sobe"); alertar(classe, conf); }
    } else sim.trecho = { ativo: false, obstaculo: false };
  }

  async function alertar(classe, conf) {
    const x = robo.x, pos = coordenadas(x);
    sim.ultimoX = x;
    const corpo = { origem: "robo", ...pos, alerta: ["escuro"], classe_ia: classe, confianca_ia: +conf.toFixed(3) };
    const marca = { x, classe, texto: "enviando…", acao: "nenhuma" };
    sim.marcas.push(marca);
    const item = el("li", { class: classe }, el("strong", {}, META[classe][0]), el("span", {}, `${(conf * 100).toFixed(0)}% · ${(x / 100).toFixed(1)} m · enviando…`));
    $("#pt-alertas").prepend(item);
    if (!$("#pt-enviar").checked) {
      marca.texto = "não enviado";
      item.lastChild.textContent = `${(conf * 100).toFixed(0)}% · ${(x / 100).toFixed(1)} m · não enviado (envio desligado)`;
      log(`POST /v1/alerta-robo (desligado) ${JSON.stringify(corpo)}`);
      return;
    }
    log(`→ POST /v1/alerta-robo ${classe} ${conf.toFixed(2)} @ ${pos.latitude},${pos.longitude}`);
    try {
      const r = await api("/v1/alerta-robo", JSON_POST(corpo), 60000);
      sim.enviados++;
      marca.texto = r.protocolo || "sem protocolo"; marca.acao = r.acao_robo;
      robo.led = r.acao_robo; robo.ledAte = sim.t + 6;
      $("#pt-led").dataset.acao = r.acao_robo;
      const nivel = (NIVEIS[r.prioridade_previa.nivel] || r.prioridade_previa.nivel).toLowerCase();
      resposta(`Suspeita ${r.protocolo || ""} · prioridade ${nivel} (${r.prioridade_previa.pontuacao})`,
        `${r.encaminhar_para?.[0]?.orgao || "central"} · LED ${r.acao_robo === "led_vermelho" ? "vermelho" : "amarelo"} no carrinho`);
      item.lastChild.replaceChildren(`${(conf * 100).toFixed(0)}% · prioridade ${nivel} · `,
        r.protocolo ? el("a", { href: `#acompanhar/${r.protocolo}` }, r.protocolo) : "sem protocolo");
      log(`← 200 ${r.status} ${r.protocolo || ""} ${r.acao_robo}`);
    } catch (e) {
      marca.texto = "falhou";
      item.lastChild.textContent = `${(conf * 100).toFixed(0)}% · falhou: ${e.message}`;
      log(`✗ API: ${e.message} (o carrinho segue patrulhando)`);
    }
  }

  function terminar() {
    if (sim.fim) return;
    sim.fim = true; rodando = false;
    $("#pt-play span").textContent = "Patrulhar de novo";
    log(`fim da rua · ${sim.enviados} alerta(s) na central`);
  }

  /* ---------------------------------------------------------------- painéis */
  function log(t) {
    const pre = $("#pt-log");
    const linhas = (pre.textContent ? pre.textContent.split("\n") : []);
    linhas.push(`[${(sim ? sim.t : 0).toFixed(1).padStart(5, "0")}s] ${t}`);
    pre.textContent = linhas.slice(-40).join("\n");
    pre.scrollTop = pre.scrollHeight;
  }
  function resposta(titulo, texto) { $("#pt-resposta").replaceChildren(el("strong", {}, titulo), el("span", {}, texto)); }

  function desenharProbs(p) {
    const ul = $("#pt-probs");
    const classes = IA ? IA.classes : Object.keys(META);
    ul.replaceChildren(...classes.map((c, i) => {
      const v = p ? p[i] : 0, topo = p && v === Math.max(...p);
      return el("li", { class: topo ? "lider" : "" }, el("span", {}, META[c][0]),
        el("i", { style: `--v:${(v * 100).toFixed(1)}%;--c:${META[c][1]}` }), el("b", {}, p ? `${(v * 100).toFixed(0)}%` : "--"));
    }));
  }

  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
  let rede = null;
  function montarRede() {
    const svg = $("#pt-rede");
    const X = [84, 204, 306], ys = (n, top, h) => Array.from({ length: n }, (_, i) => top + (h * (i + 0.5)) / n);
    const yIn = ys(4, 8, 220), yH = ys(12, 4, 228), yOut = ys(4, 8, 220);
    const g = svgEl("g", {}), arestas1 = [], arestas2 = [];
    const maxW1 = Math.max(...IA.w1.flat().map(Math.abs)), maxW2 = Math.max(...IA.w2.flat().map(Math.abs));
    IA.w1.forEach((linha, i) => linha.forEach((w, j) => {
      const l = svgEl("line", { x1: X[0], y1: yIn[i], x2: X[1], y2: yH[j], class: w >= 0 ? "pos" : "neg" });
      l.dataset.peso = Math.abs(w) / maxW1; g.append(l); arestas1.push({ l, i, j });
    }));
    IA.w2.forEach((linha, j) => linha.forEach((w, k) => {
      const l = svgEl("line", { x1: X[1], y1: yH[j], x2: X[2], y2: yOut[k], class: w >= 0 ? "pos" : "neg" });
      l.dataset.peso = Math.abs(w) / maxW2; g.append(l); arestas2.push({ l, j, k });
    }));
    const nos = (xs, yv, cls, r) => yv.map((y) => { const c = svgEl("circle", { cx: xs, cy: y, r, class: `no ${cls}` }); g.append(c); return c; });
    const nIn = nos(X[0], yIn, "entrada", 9), nH = nos(X[1], yH, "oculto", 7), nOut = nos(X[2], yOut, "saida", 9);
    const rot = (x, y, t, anc, cls = "rot") => { const tx = svgEl("text", { x, y, "text-anchor": anc, class: cls }); tx.textContent = t; g.append(tx); return tx; };
    const nomesIn = ["média", "mínimo", "desvio", "escuro"];
    const valIn = yIn.map((y, i) => { rot(X[0] - 16, y - 2, nomesIn[i], "end"); return rot(X[0] - 16, y + 11, "--", "end", "val"); });
    IA.classes.forEach((c, k) => rot(X[2] + 16, yOut[k] + 4, META[c][0], "start"));
    svg.replaceChildren(g);
    rede = { arestas1, arestas2, nIn, nH, nOut, valIn };
  }
  function atualizarRede(x, r, k) {
    if (!rede) return;
    const ativo = !!r;
    const hMax = ativo ? Math.max(1e-6, ...r.h) : 1;
    rede.valIn.forEach((t, i) => { t.textContent = ativo ? (i === 3 ? `${(x[3] * 100).toFixed(0)}%` : `${x[i].toFixed(1)} cm`) : "--"; });
    rede.nIn.forEach((c, i) => c.style.setProperty("--a", ativo ? Math.min(1, Math.abs(r.z[i]) / 2 + 0.25) : 0.15));
    rede.nH.forEach((c, j) => c.style.setProperty("--a", ativo ? 0.12 + (0.88 * r.h[j]) / hMax : 0.12));
    rede.nOut.forEach((c, kk) => { c.style.setProperty("--a", ativo ? 0.15 + 0.85 * r.p[kk] : 0.15); c.classList.toggle("vencedor", ativo && kk === k); });
    rede.arestas1.forEach(({ l, i }) => l.style.setProperty("--a", (ativo ? Math.min(1, Math.abs(r.z[i]) / 2 + 0.1) : 0.35) * l.dataset.peso * 0.8));
    rede.arestas2.forEach(({ l, j }) => l.style.setProperty("--a", (ativo ? r.h[j] / hMax : 0.35) * l.dataset.peso * 0.9));
  }

  function atualizarPaineis() {
    const l = sim.leitura;
    if (l) {
      $("#pt-ldr").textContent = l.escuro ? "ESCURO" : "claro";
      $("#pt-ldr").className = l.escuro ? "escuro" : "";
      $("#pt-dist").textContent = l.dist >= ALCANCE - 2 ? "300+ cm" : `${l.dist.toFixed(0)} cm`;
      const c = coordenadas(robo.x);
      $("#pt-gps").textContent = `${c.latitude.toFixed(5)}, ${c.longitude.toFixed(5)}`;
    }
    const u = sim.ultima;
    if (!u) return;
    desenharProbs(u.p);
    atualizarRede(u.x, u, u.k);
    const nome = META[IA.classes[u.k]][0];
    const conf = $("#pt-conf");
    if (u.conf < IA.escore_min) conf.replaceChildren(`Indecisa: ${nome} com ${(u.conf * 100).toFixed(0)}% (precisa de 70%)`);
    else if (sim.confirmado === u.k) conf.replaceChildren("Confirmado: ", el("strong", {}, nome), ` · ${(u.conf * 100).toFixed(0)}%`);
    else conf.replaceChildren("Confirmando ", el("strong", {}, nome), ` · ${Math.min(sim.rep, IA.repeticoes)}/${IA.repeticoes}`);
  }

  /* ---------------------------------------------------------------- desenho da cena */
  let vista = { w: 0, h: 260, esc: 1, cam: 0 };
  function medir() {
    const w = cena.clientWidth || 800, dpr = window.devicePixelRatio || 1;
    vista.w = w; vista.h = w < 560 ? 230 : 270;
    cena.style.height = `${vista.h}px`;
    cena.width = Math.round(w * dpr); cena.height = Math.round(vista.h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const visivel = Math.min(RUA + 240, w * 3.4);
    vista.esc = w / visivel; vista.visivel = visivel;
  }
  const px = (x) => (x - vista.cam) * vista.esc;
  // o desenho é maior que a escala: alinha a FRENTE do carrinho e a BORDA do obstáculo às posições reais
  const desenhoRobo = () => px(robo.x + 25) - 22;
  const desenhoObstaculo = (o) => px(o.x - 20) + 13;
  function geometria() {
    const H = vista.h;
    return { calcadaTopo: [26, 58], pista: [58, H - 44], faixa: H - 44 - 34, faixa2: 58 + 40, centro: (58 + H - 44) / 2, calcadaBaixo: [H - 44, H - 22] };
  }
  function desenhar() {
    if (!mundo) return;
    const { w, h } = vista, G = geometria();
    vista.cam = Math.max(-120, Math.min(RUA + 120 - vista.visivel, robo.x - vista.visivel * 0.35));
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#060912"; ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "#121a2e"; ctx.fillRect(0, G.calcadaTopo[0], w, G.calcadaTopo[1] - G.calcadaTopo[0]);
    ctx.fillRect(0, G.calcadaBaixo[0], w, G.calcadaBaixo[1] - G.calcadaBaixo[0]);
    ctx.fillStyle = "#0a0f1d"; ctx.fillRect(0, G.pista[0], w, G.pista[1] - G.pista[0]);

    // luz dos postes (soma de luz)
    ctx.save(); ctx.globalCompositeOperation = "lighter";
    for (const p of mundo.postes) {
      if (!p.aceso) continue;
      const cx = px(p.x), cy = G.centro + 6, r = RAIO_LUZ * vista.esc * 1.05;
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
      grad.addColorStop(0, "rgba(255,200,107,.40)"); grad.addColorStop(0.65, "rgba(255,200,107,.16)"); grad.addColorStop(1, "rgba(255,200,107,0)");
      ctx.save(); ctx.translate(cx, cy); ctx.scale(1, 0.62); ctx.translate(-cx, -cy);
      ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    }
    ctx.restore();

    // faixa central
    ctx.strokeStyle = "rgba(230,178,94,.35)"; ctx.lineWidth = 2; ctx.setLineDash([16, 14]);
    ctx.lineDashOffset = vista.cam * vista.esc;
    ctx.beginPath(); ctx.moveTo(0, G.centro); ctx.lineTo(w, G.centro); ctx.stroke(); ctx.setLineDash([]);

    // trechos que a IA confirmou
    for (let i = 0; i < sim.trilha.length; i++) {
      const a = sim.trilha[i], fim = i + 1 < sim.trilha.length ? sim.trilha[i + 1].x : robo.x;
      ctx.fillStyle = META[a.classe][1]; ctx.globalAlpha = 0.85;
      ctx.fillRect(px(a.x), G.calcadaBaixo[0] + 8, Math.max(2, px(fim) - px(a.x)), 6);
      ctx.globalAlpha = 1;
    }

    // postes
    for (const p of mundo.postes) {
      const x = px(p.x);
      if (x < -30 || x > w + 30) continue;
      ctx.strokeStyle = "#3b4a70"; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(x, G.calcadaTopo[0] + 4); ctx.lineTo(x, G.pista[0] + 2); ctx.stroke();
      ctx.beginPath(); ctx.arc(x, G.calcadaTopo[0] + 6, 7, 0, Math.PI * 2);
      ctx.fillStyle = p.aceso ? "#ffd27f" : "#2a3552"; ctx.shadowColor = p.aceso ? "#ffc86b" : "transparent"; ctx.shadowBlur = p.aceso ? 16 : 0;
      ctx.fill(); ctx.shadowBlur = 0;
      if (!p.aceso) {
        ctx.strokeStyle = "#ff7a6b"; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(x - 4, G.calcadaTopo[0] + 2); ctx.lineTo(x + 4, G.calcadaTopo[0] + 10);
        ctx.moveTo(x + 4, G.calcadaTopo[0] + 2); ctx.lineTo(x - 4, G.calcadaTopo[0] + 10); ctx.stroke();
      }
    }

    // obstáculos
    for (const o of mundo.obstaculos) {
      const x = desenhoObstaculo(o), y = G.faixa;
      if (x < -30 || x > w + 30) continue;
      ctx.fillStyle = o.passado ? "#5a4630" : "#8a6a3e"; ctx.strokeStyle = "#e6b25e"; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.roundRect(x - 13, y - 11, 26, 22, 4); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = "rgba(255,200,107,.55)"; ctx.beginPath();
      ctx.moveTo(x - 9, y - 7); ctx.lineTo(x + 9, y + 7); ctx.moveTo(x + 9, y - 7); ctx.lineTo(x - 9, y + 7); ctx.stroke();
    }

    // marcas dos alertas enviados
    ctx.font = "600 11px Inter, system-ui, sans-serif"; ctx.textAlign = "center";
    sim.marcas.forEach((m, i) => {
      const x = px(m.x), dy = i > 0 && Math.abs(px(sim.marcas[i - 1].x) - x) < 90 ? 14 : 0, cor = m.acao === "led_vermelho" ? "#ff7a6b" : m.acao === "led_amarelo" ? "#f2d27a" : "#a6b0c8";
      ctx.fillStyle = cor; ctx.beginPath(); ctx.moveTo(x, G.pista[0] + 16); ctx.lineTo(x - 6, G.pista[0] + 6); ctx.lineTo(x + 6, G.pista[0] + 6); ctx.fill();
      ctx.fillText(m.texto, x, G.pista[0] + 30 + dy);
    });

    // carrinho
    const ry = G.faixa - (G.faixa - G.faixa2) * robo.faixa, rx = desenhoRobo();
    const d = sim.leitura ? sim.leitura.dist : ALCANCE;
    const alcance = Math.min(d, ALCANCE) * vista.esc;
    const grad = ctx.createLinearGradient(rx + 22, 0, rx + 22 + alcance, 0);
    const perto = d < 30;
    grad.addColorStop(0, perto ? "rgba(255,122,107,.45)" : "rgba(127,176,255,.28)"); grad.addColorStop(1, "rgba(127,176,255,0)");
    ctx.fillStyle = grad; ctx.beginPath(); ctx.moveTo(rx + 22, ry - 3); ctx.lineTo(rx + 22 + alcance, ry - 14); ctx.lineTo(rx + 22 + alcance, ry + 14); ctx.lineTo(rx + 22, ry + 3); ctx.fill();
    ctx.fillStyle = "#0d1426"; [[-14, -14], [10, -14], [-14, 14], [10, 14]].forEach(([dx, dy]) => { ctx.fillRect(rx + dx - 4, ry + dy - 3, 8, 6); });
    ctx.fillStyle = "#24314f"; ctx.strokeStyle = "#ffc86b"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.roundRect(rx - 22, ry - 12, 44, 24, 6); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#c9954a"; ctx.fillRect(rx + 18, ry - 6, 5, 12);
    const escuro = sim.leitura && sim.leitura.escuro;
    ctx.beginPath(); ctx.arc(rx - 6, ry, 4, 0, Math.PI * 2); ctx.fillStyle = escuro ? "#3b4a70" : "#ffd27f"; ctx.fill();
    const ledOn = robo.ledAte > sim.t && robo.led !== "nenhuma" && (robo.led !== "led_vermelho" || Math.floor(sim.t * 4) % 2 === 0);
    ctx.beginPath(); ctx.arc(rx + 8, ry, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = ledOn ? (robo.led === "led_vermelho" ? "#ff7a6b" : "#f2d27a") : "#131c33";
    ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = ledOn ? 14 : 0; ctx.fill(); ctx.shadowBlur = 0;

    // régua e estado
    ctx.fillStyle = "#6f7a96"; ctx.font = "11px Inter, system-ui, sans-serif"; ctx.textAlign = "left";
    for (let m = 0; m <= RUA / 100; m += 6) { const x = px(m * 100); if (x > -10 && x < w - 20) ctx.fillText(`${m} m`, x + 2, h - 4); }
    ctx.textAlign = "right"; ctx.fillStyle = "#a6b0c8";
    const estadoTxt = sim.fim ? "patrulha concluída" : !rodando ? (sim.t ? "pausado" : "pronto") : robo.modo === "parado" ? "parado: obstáculo à frente" : robo.desviando ? "desviando" : "patrulhando";
    ctx.fillText(`${estadoTxt} · ${(robo.x / 100).toFixed(1)} m · ${sim.t.toFixed(1)} s`, w - 8, 18);
  }

  /* ---------------------------------------------------------------- laço */
  function quadro(agora) {
    if (!rodando) return;
    const dt = Math.min(0.1, (agora - ultimoQuadro) / 1000) * Number($("#pt-vel").value);
    ultimoQuadro = agora;
    sim.acum += dt;
    while (sim.acum >= 0.1 && rodando) { sim.acum -= 0.1; sim.t += 0.1; passo(0.1); }
    atualizarPaineis();
    desenhar();
    if (rodando) requestAnimationFrame(quadro);
  }
  function alternar() {
    if (!IA) { log("a IA ainda está carregando…"); return; }
    if (sim.fim) reiniciar();
    rodando = !rodando;
    $("#pt-play span").textContent = rodando ? "Pausar" : "Continuar";
    if (rodando) { ultimoQuadro = performance.now(); log(sim.t ? "continuando" : "patrulha iniciada"); requestAnimationFrame(quadro); }
    else desenhar();
  }

  /* ---------------------------------------------------------------- edição da rua */
  cena.addEventListener("click", (ev) => {
    const r = cena.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top, G = geometria();
    const xMundo = mx / vista.esc + vista.cam;
    if (my < G.pista[0] + 4) {
      const p = mundo.postes.reduce((a, b) => (Math.abs(b.x - xMundo) < Math.abs(a.x - xMundo) ? b : a));
      if (Math.abs(px(p.x) - mx) < 26) { p.aceso = !p.aceso; log(`poste a ${(p.x / 100).toFixed(1)} m ${p.aceso ? "aceso" : "apagado"}`); }
    } else if (my < G.pista[1]) {
      const perto = mundo.obstaculos.findIndex((o) => Math.abs(desenhoObstaculo(o) - mx) < 18);
      if (perto >= 0) { mundo.obstaculos.splice(perto, 1); log("obstáculo retirado"); }
      else if (xMundo > robo.x + 80 && xMundo < RUA - 120 && mundo.obstaculos.length < 6) {
        mundo.obstaculos.push({ x: Math.round(xMundo) }); log(`obstáculo em ${(xMundo / 100).toFixed(1)} m`);
      }
    }
    desenhar();
  });

  $("#pt-play").addEventListener("click", alternar);
  $("#pt-reiniciar").addEventListener("click", () => reiniciar());
  $("#pt-sortear").addEventListener("click", () => reiniciar(cenaAleatoria()));
  window.addEventListener("resize", () => { medir(); desenhar(); });
  // a aba começa escondida: mede de novo quando ela aparece
  new MutationObserver(() => { if (!$("#tela-robo").hidden) { medir(); desenhar(); } }).observe($("#tela-robo"), { attributes: true, attributeFilter: ["hidden"] });

  mundo = cenaPadrao();
  medir();
  reiniciar();
  fetch("/static/tinyml-carrinho.json?v=patrulha-1").then((r) => r.json()).then((m) => {
    IA = m; montarRede(); desenharProbs(null); atualizarRede(null, null, null);
    log(`IA do carrinho carregada: ${m.classes.length} classes, pesos de ${m.origem.split("/").pop()}`);
  }).catch(() => log("não consegui carregar a IA do carrinho (tinyml-carrinho.json)"));
})();
