/* Front do MVP: cidadão (foto), robô (sensores), prefeitura (mapa + fila).
 * Fala só com a API da própria Visão (mesma origem). Texto vindo do servidor entra sempre por
 * textContent, nunca como HTML. Fotos não são guardadas no navegador: só os dados do chamado. */
"use strict";

const PAULISTA = { lat: -23.5614, lon: -46.6559 };
const CHAVE_FILA = "ruas-escuras:chamados";
const NOMES_TIPO = {
  conserto_poste: "Conserto de poste",
  instalacao_iluminacao: "Instalação de iluminação",
  poda_ou_obstrucao: "Poda / obstrução",
  buraco: "Buraco na via",
};
const NOMES_TRECHO = { iluminada: "Iluminado", parcial: "Parcialmente escuro", escura: "Escuro", sem_postes_visiveis: "Sem postes visíveis" };
const CORES_CLASSE = { poste_aceso: "#4ade80", poste_apagado: "#ff5d5d", buraco: "#ff9f1c" };
const NOMES_NIVEL = { alta: "Alta", media: "Média", baixa: "Baixa", nenhuma: "Nenhuma" };
const NOMES_CLASSE = { poste_aceso: "aceso", poste_apagado: "apagado", buraco: "buraco" };

const $ = (sel) => document.querySelector(sel);
const estado = { arquivo: null, gps: null, sensores: null, mapa: null, camadaMapa: null };

function el(tag, props = {}, ...filhos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k === "dataset") Object.assign(n.dataset, v);
    else n.setAttribute(k, v);
  }
  for (const f of filhos) n.append(f instanceof Node ? f : document.createTextNode(String(f)));
  return n;
}

async function api(caminho, opcoes = {}, tempoMs = 120000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), tempoMs);
  try {
    const r = await fetch(caminho, { ...opcoes, signal: ctrl.signal });
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof corpo.detail === "string" ? corpo.detail : `erro ${r.status}`);
    return corpo;
  } catch (e) {
    if (e.name === "AbortError") throw new Error("o servidor demorou demais para responder; tente de novo");
    throw e;
  } finally {
    clearTimeout(t);
  }
}

/* ============================================================== abas */
function mostrarTela(nome) {
  if (!document.getElementById(`tela-${nome}`)) nome = "cidadao";
  document.querySelectorAll(".tela").forEach((t) => { t.hidden = t.id !== `tela-${nome}`; });
  document.querySelectorAll(".aba").forEach((a) => a.setAttribute("aria-selected", String(a.dataset.tela === nome)));
  if (location.hash !== `#${nome}`) history.replaceState(null, "", `#${nome}`);
  if (nome === "prefeitura") abrirPrefeitura();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
document.querySelectorAll(".aba").forEach((a) => a.addEventListener("click", () => mostrarTela(a.dataset.tela)));
window.addEventListener("hashchange", () => mostrarTela(location.hash.slice(1)));

/* ============================================================== status da API */
async function verificarApi() {
  const box = $("#status-api"), txt = box.querySelector(".texto");
  const aviso = setTimeout(() => { box.dataset.estado = "acordando"; txt.textContent = "acordando o servidor…"; }, 1500);
  try {
    const s = await api("/saude", {}, 90000);
    box.dataset.estado = s.modelo_carregado ? "ok" : "erro";
    txt.textContent = s.modelo_carregado ? "IA online" : "IA sem modelo";
  } catch {
    box.dataset.estado = "erro"; txt.textContent = "servidor indisponível";
  } finally { clearTimeout(aviso); }
}

/* ============================================================== localização */
function pedirGps() {
  const info = $("#gps-info");
  if (!$("#usar-gps").checked) { estado.gps = null; info.textContent = ""; return; }
  if (!("geolocation" in navigator)) { info.textContent = "navegador sem GPS: usaremos o da foto"; return; }
  info.textContent = "localizando…";
  navigator.geolocation.getCurrentPosition(
    (p) => {
      estado.gps = { lat: p.coords.latitude, lon: p.coords.longitude };
      info.textContent = `📍 ${estado.gps.lat.toFixed(4)}, ${estado.gps.lon.toFixed(4)} (±${Math.round(p.coords.accuracy)} m)`;
    },
    () => { estado.gps = null; info.textContent = "sem permissão: usaremos o GPS da foto, se houver"; },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
  );
}
$("#usar-gps").addEventListener("change", pedirGps);

/* ============================================================== cidadão: foto */
function escolherArquivo(f) {
  if (!f) return;
  if (!/^image\/(jpeg|png|webp)$/.test(f.type)) { mostrarErro("Use uma foto JPEG, PNG ou WebP."); return; }
  estado.arquivo = f;
  const previa = $("#previa");
  previa.src = URL.createObjectURL(f);
  previa.hidden = false;
  $("#soltar-texto").hidden = true;
  $("#enviar").disabled = false;
  mostrarErro("");
}
$("#arquivo").addEventListener("change", (e) => escolherArquivo(e.target.files[0]));
const soltar = $("#soltar");
["dragenter", "dragover"].forEach((ev) => soltar.addEventListener(ev, (e) => { e.preventDefault(); soltar.classList.add("arrastando"); }));
["dragleave", "drop"].forEach((ev) => soltar.addEventListener(ev, (e) => { e.preventDefault(); soltar.classList.remove("arrastando"); }));
soltar.addEventListener("drop", (e) => escolherArquivo(e.dataTransfer.files[0]));

/* Com o GPS do navegador, reduzimos a foto no aparelho (mais rápido, menos dados).
 * Sem ele, mandamos o original: o GPS escondido na foto (EXIF) é lido pela API e descartado. */
async function prepararImagem(f) {
  if (!estado.gps || !("createImageBitmap" in window)) return f;
  try {
    const bmp = await createImageBitmap(f, { imageOrientation: "from-image" });
    const escala = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
    if (escala === 1 && f.size < 2.5e6) return f;
    const c = el("canvas"); c.width = Math.round(bmp.width * escala); c.height = Math.round(bmp.height * escala);
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    const blob = await new Promise((ok) => c.toBlob(ok, "image/jpeg", 0.88));
    return blob ? new File([blob], "foto.jpg", { type: "image/jpeg" }) : f;
  } catch { return f; }
}

function mostrarErro(msg) { const e = $("#erro-envio"); e.textContent = msg; e.hidden = !msg; }

function animarEtapas() {
  const itens = [...document.querySelectorAll("#etapas li")];
  $("#etapas").hidden = false;
  let i = 0;
  const passo = () => {
    itens.forEach((li, j) => { li.className = j < i ? "feita" : j === i ? "atual" : ""; });
    if (i < itens.length - 1) i++;
  };
  passo();
  const id = setInterval(passo, 1400);
  return (sucesso) => { clearInterval(id); itens.forEach((li) => { li.className = sucesso ? "feita" : ""; }); if (!sucesso) $("#etapas").hidden = true; };
}

$("#form-foto").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!estado.arquivo) return;
  const botao = $("#enviar");
  botao.disabled = true; botao.textContent = "Analisando…"; mostrarErro("");
  const fim = animarEtapas();
  try {
    const dados = new FormData();
    dados.append("imagem", await prepararImagem(estado.arquivo));
    dados.append("origem", estado.sensores ? "robo" : "cidadao");
    dados.append("retornar_imagem", "true");
    dados.append("incluir_orientacao", "true");
    if (estado.gps) { dados.append("latitude", estado.gps.lat); dados.append("longitude", estado.gps.lon); }
    if (estado.sensores) {
      dados.append("sensor_lux", estado.sensores.lux);
      dados.append("sensor_distancia_cm", estado.sensores.dist);
      if (estado.sensores.alertas.length) dados.append("alerta", estado.sensores.alertas.join(","));
    }
    const analise = await api("/v1/analisar", { method: "POST", body: dados });
    fim(true);
    mostrarResultado(analise);
  } catch (err) {
    fim(false);
    mostrarErro(`Não deu para analisar: ${err.message}`);
  } finally {
    botao.disabled = false; botao.textContent = "Analisar e abrir chamado";
  }
});

function desenharDeteccoes(analise) {
  const canvas = $("#canvas-resultado"), ctx = canvas.getContext("2d");
  const img = new Image();
  img.onload = () => {
    canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
    ctx.drawImage(img, 0, 0);
    const espessura = Math.max(3, Math.round(Math.max(img.naturalWidth, img.naturalHeight) / 250));
    ctx.font = `700 ${espessura * 6}px system-ui, sans-serif`;
    for (const d of analise.deteccoes) {
      const [x1, y1, x2, y2] = d.bbox, cor = CORES_CLASSE[d.classe] || "#7aa2ff";
      ctx.lineWidth = espessura; ctx.strokeStyle = cor; ctx.shadowColor = cor; ctx.shadowBlur = espessura * 3;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      ctx.shadowBlur = 0;
      const rotulo = `${NOMES_CLASSE[d.classe] || d.classe} ${Math.round(d.confianca * 100)}%`;
      const largura = ctx.measureText(rotulo).width + espessura * 3, altura = espessura * 8;
      const y = y1 - altura < 0 ? y1 : y1 - altura;
      ctx.fillStyle = cor; ctx.fillRect(x1, y, largura, altura);
      ctx.fillStyle = "#0b1020"; ctx.fillText(rotulo, x1 + espessura * 1.5, y + altura - espessura * 2);
    }
  };
  if (analise.imagem_anonimizada_base64) img.src = `data:image/jpeg;base64,${analise.imagem_anonimizada_base64}`;
  else img.src = URL.createObjectURL(estado.arquivo);
}

function preencherLista(ul, itens) { ul.replaceChildren(...itens.map((t) => el("li", {}, t))); }

function mostrarResultado(a) {
  $("#resultado").hidden = false;
  desenharDeteccoes(a);

  const v = $("#veredito");
  const tipos = a.fusao?.tipos_chamado || [];
  if (a.validacao.abrir_chamado) {
    v.className = "veredito abre";
    v.replaceChildren(el("span", { class: "icone" }, "🚨"),
      el("div", {}, "Chamado aberto", el("small", {}, tipos.length ? `Encaminhado para: ${tipos.map((t) => NOMES_TIPO[t] || t).join(" + ")}` : "Encaminhado à prefeitura")));
  } else if (!a.validacao.foto_valida) {
    v.className = "veredito invalida";
    v.replaceChildren(el("span", { class: "icone" }, "📷"),
      el("div", {}, "A foto não serviu como evidência", el("small", {}, a.validacao.motivos[0] || "tente outra foto")));
  } else {
    v.className = "veredito ok";
    v.replaceChildren(el("span", { class: "icone" }, "✅"), el("div", {}, "Rua iluminada", el("small", {}, "Nenhuma falha encontrada: nenhum chamado necessário")));
  }

  const p = a.prioridade;
  $("#bloco-prioridade").hidden = p.nivel === "nenhuma";
  $("#prioridade-nivel").textContent = `${NOMES_NIVEL[p.nivel] || p.nivel} · ${p.pontuacao}/100`;
  requestAnimationFrame(() => { $("#prioridade-barra").style.width = `${p.pontuacao}%`; });
  preencherLista($("#prioridade-fatores"), p.fatores);

  const r = a.resumo;
  $("#info-trecho").textContent = NOMES_TRECHO[r.status_trecho] || r.status_trecho;
  $("#info-postes").textContent = `${r.postes_acesos} aceso${r.postes_acesos === 1 ? "" : "s"} · ${r.postes_apagados} apagado${r.postes_apagados === 1 ? "" : "s"}`;
  $("#info-setor").textContent = tipos.length ? tipos.map((t) => NOMES_TIPO[t] || t).join(", ") : "—";
  preencherLista($("#lista-motivos"), [...a.validacao.motivos, ...(a.fusao?.motivos || [])]);

  mostrarOrientacao(a);
  $("#selo-rostos").textContent = a.privacidade.rostos_borrados ? `🙂 ${a.privacidade.rostos_borrados} rosto(s) borrado(s)` : "🙂 Nenhum rosto na foto";
  $("#protocolo").textContent = `Protocolo ${a.id_captura.slice(0, 8)} · ${new Date(a.timestamp).toLocaleString("pt-BR")} · modelo ${a.modelo.versao}`;

  if (a.validacao.abrir_chamado) {
    salvarChamado({
      id: a.id_captura, ts: a.timestamp, origem: estado.sensores ? "robo+foto" : "cidadao",
      lat: a.localizacao?.latitude, lon: a.localizacao?.longitude,
      nivel: p.nivel, pontos: p.pontuacao, tipos, trecho: r.status_trecho,
      confirmacao: a.fusao?.confirmacao,
    });
  }
  if (estado.sensores) desvincular();
  $("#resultado").scrollIntoView({ behavior: "smooth", block: "start" });
}

function mostrarOrientacao(a) {
  const box = $("#orientacao");
  if (!a.validacao.abrir_chamado) { box.hidden = true; return; }
  const ok = (a.orientacao || []).find((o) => o.status === "ok");
  box.hidden = false;
  if (ok) {
    box.replaceChildren(el("strong", {}, "⏱️ Prazo oficial: "), ok.resposta,
      ok.trecho_citado ? el("blockquote", {}, `Fonte (${ok.citacao}): ${ok.trecho_citado}`) : "",
      el("small", {}, ok.aviso || ""));
  } else {
    box.replaceChildren(el("strong", {}, "📞 Canal oficial: "),
      "em São Paulo, o serviço de iluminação pública atende pelo telefone 156 ou pelo portal SP156. ",
      el("small", {}, "O assistente de prazos está fora do ar nesta demonstração; esta orientação é fixa."));
  }
}

/* ============================================================== robô */
const lux = $("#lux"), dist = $("#dist");
function atualizarSensores() {
  $("#lux-valor").textContent = `${Number(lux.value).toFixed(1)} lux`;
  $("#dist-valor").textContent = `${dist.value} cm`;
}
[lux, dist].forEach((i) => i.addEventListener("input", atualizarSensores));
const CENARIOS = { normal: [30, 8], escuro: [2, 8], buraco: [35, 26], ambos: [2.5, 24] };
document.querySelectorAll("[data-cenario]").forEach((b) => b.addEventListener("click", () => {
  [lux.value, dist.value] = CENARIOS[b.dataset.cenario];
  atualizarSensores();
  enviarAlerta();
}));

function posicaoRobo(i = 0) {
  const base = estado.gps || PAULISTA;
  return { latitude: +(base.lat + i * 0.0002).toFixed(6), longitude: +base.lon.toFixed(6) };
}

function leituraAtual() {
  return { ...posicaoRobo(), sensor_lux: +lux.value, sensor_distancia_cm: +dist.value };
}

/* Manda a leitura ao /v1/alerta-robo (o mesmo JSON que o firmware do robô envia) e mostra o LED. */
async function enviarAlerta(leitura = leituraAtual()) {
  const corpo = { origem: "robo", ...leitura };
  try {
    const r = await api("/v1/alerta-robo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
    $("#led").dataset.acao = r.acao_robo;
    const suspeita = r.status === "suspeita";
    $("#robo-resposta").replaceChildren(
      el("strong", {}, suspeita ? `Suspeita registrada · prioridade ${(NOMES_NIVEL[r.prioridade_previa.nivel] || "").toLowerCase()} (${r.prioridade_previa.pontuacao})` : "Tudo normal neste ponto"),
      el("span", {}, suspeita ? r.proximo_passo : "Nenhum sensor disparou."));
    preencherLista($("#robo-fatores"), suspeita ? r.prioridade_previa.fatores : []);
    const confirmar = $("#confirmar-foto");
    confirmar.hidden = !suspeita;
    confirmar.onclick = () => vincularSensores(corpo, r.alertas);
    if (suspeita) {
      salvarChamado({ id: r.id_alerta, ts: r.timestamp, origem: "robo", lat: corpo.latitude, lon: corpo.longitude,
        nivel: r.prioridade_previa.nivel, pontos: r.prioridade_previa.pontuacao, tipos: r.alertas.map((x) => `suspeita_${x}`), trecho: "suspeita" });
    }
    return r;
  } catch (e) {
    $("#robo-resposta").replaceChildren(el("strong", {}, "Falha ao falar com a API"), el("span", {}, e.message));
    return null;
  }
}
$("#enviar-alerta").addEventListener("click", () => enviarAlerta());

$("#patrulha").addEventListener("click", async () => {
  const botao = $("#patrulha"), trilha = $("#trilha");
  botao.disabled = true;
  trilha.replaceChildren(...Array.from({ length: 12 }, () => el("span")));
  for (let i = 0; i < 12; i++) {
    const escuro = i >= 6 && i < 10;
    const leitura = { ...posicaoRobo(i), sensor_lux: escuro ? +(0.8 + Math.random() * 3).toFixed(1) : +(12 + Math.random() * 25).toFixed(1),
      sensor_distancia_cm: i === 8 ? 24 : +(6 + Math.random() * 3).toFixed(1) };
    lux.value = leitura.sensor_lux; dist.value = leitura.sensor_distancia_cm; atualizarSensores();
    const r = await enviarAlerta(leitura);
    if (r) trilha.children[i].dataset.acao = r.acao_robo;
    await new Promise((ok) => setTimeout(ok, 700));
  }
  botao.disabled = false;
});

function vincularSensores(corpo, alertas) {
  estado.sensores = { lux: corpo.sensor_lux, dist: corpo.sensor_distancia_cm, alertas };
  $("#sensores-resumo").textContent = `${corpo.sensor_lux} lux · ${corpo.sensor_distancia_cm} cm · ${alertas.join(" + ")}`;
  $("#sensores-vinculados").hidden = false;
  mostrarTela("cidadao");
}
function desvincular() { estado.sensores = null; $("#sensores-vinculados").hidden = true; }
$("#desvincular").addEventListener("click", desvincular);

/* ============================================================== prefeitura */
function lerFila() { try { return JSON.parse(localStorage.getItem(CHAVE_FILA)) || []; } catch { return []; } }
function salvarChamado(c) {
  try {
    const fila = lerFila().filter((x) => x.id !== c.id);
    fila.push(c);
    localStorage.setItem(CHAVE_FILA, JSON.stringify(fila.slice(-200)));
  } catch { /* navegador sem armazenamento: a demo segue sem a fila */ }
}
$("#limpar-fila").addEventListener("click", () => { try { localStorage.removeItem(CHAVE_FILA); } catch {} abrirPrefeitura(); });

function rotuloTipos(c) {
  return (c.tipos || []).map((t) => NOMES_TIPO[t] || (t.startsWith("suspeita_") ? `Suspeita: ${t.slice(9)}` : t)).join(" + ") || "Chamado";
}

function abrirPrefeitura() {
  const fila = lerFila().sort((a, b) => b.pontos - a.pontos || b.ts.localeCompare(a.ts));
  $("#kpi-total").textContent = fila.length;
  $("#kpi-alta").textContent = fila.filter((c) => c.nivel === "alta").length;
  $("#kpi-conserto").textContent = fila.filter((c) => (c.tipos || []).includes("conserto_poste")).length;
  $("#kpi-robo").textContent = fila.filter((c) => c.origem === "robo").length;
  $("#fila-vazia").hidden = fila.length > 0;
  $("#lista-chamados").replaceChildren(...fila.map((c) => el("li", { class: "chamado" },
    el("span", { class: `pts ${c.nivel}` }, c.pontos),
    el("div", {}, rotuloTipos(c), el("small", {}, `${new Date(c.ts).toLocaleString("pt-BR")} · ${NOMES_TRECHO[c.trecho] || c.trecho}`)),
    el("span", { class: "origem", title: c.origem }, c.origem === "robo" ? "🤖" : c.origem === "robo+foto" ? "🤖📸" : "📸"))));

  if (!window.L) return;
  if (!estado.mapa) {
    estado.mapa = L.map("mapa", { zoomControl: true }).setView([PAULISTA.lat, PAULISTA.lon], 14);
    // OpenStreetMap (aberto, sem chave); o tema noturno vem de um filtro CSS nos blocos do mapa
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(estado.mapa);
    estado.camadaMapa = L.layerGroup().addTo(estado.mapa);
  }
  setTimeout(() => estado.mapa.invalidateSize(), 50);
  estado.camadaMapa.clearLayers();
  const cor = { alta: "#ff5d5d", media: "#ffd166", baixa: "#8b97b8", nenhuma: "#8b97b8" };
  const pontos = fila.filter((c) => Number.isFinite(c.lat) && Number.isFinite(c.lon));
  for (const c of pontos) {
    L.circleMarker([c.lat, c.lon], { radius: 6 + c.pontos / 12, color: cor[c.nivel], fillColor: cor[c.nivel], fillOpacity: 0.55, weight: 2 })
      .bindPopup(el("div", {}, el("strong", {}, `${c.pontos} pts · prioridade ${(NOMES_NIVEL[c.nivel] || c.nivel).toLowerCase()}`), el("br"), rotuloTipos(c)))
      .addTo(estado.camadaMapa);
  }
  if (pontos.length) estado.mapa.fitBounds(L.latLngBounds(pontos.map((c) => [c.lat, c.lon])).pad(0.3), { maxZoom: 16 });
}

/* ============================================================== início */
atualizarSensores();
pedirGps();
verificarApi();
mostrarTela(location.hash.slice(1) || "cidadao");
