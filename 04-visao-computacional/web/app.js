/* Vésper · front do MVP (da escuridão à luz).
 * Fala com a API da própria Visão (mesma origem) e, só para endereço, com o Nominatim (OpenStreetMap).
 * Texto vindo de fora entra sempre por textContent. Fotos nunca são guardadas no navegador:
 * a "base" da demonstração (localStorage) tem só os dados do chamado. */
"use strict";

/* ================================================================== constantes */
const PAULISTA = { lat: -23.5614, lon: -46.6559 };
const CHAVE = "vesper:chamados";
const NOMINATIM = "https://nominatim.openstreetmap.org";
const TIPOS = {
  conserto_poste: "Conserto de poste",
  instalacao_iluminacao: "Instalação de iluminação",
  poda_ou_obstrucao: "Poda / obstrução",
  buraco: "Buraco na via",
  trecho_sem_luz: "Trecho sem luz (inspeção)",
  suspeita_escuro: "Suspeita: rua escura",
  suspeita_buraco: "Suspeita: buraco",
};
const TRECHOS = { iluminada: "Iluminado", parcial: "Parcialmente escuro", escura: "Escuro", sem_postes_visiveis: "Sem postes visíveis", suspeita: "A confirmar" };
const NIVEIS = { alta: "Alta", media: "Média", baixa: "Baixa", nenhuma: "Nenhuma" };
const CLASSES = { poste_aceso: ["aceso", "#ffc86b"], poste_apagado: ["apagado", "#ff7a6b"], buraco: ["buraco", "#f2d27a"] };
const STATUS = {
  suspeita: "Suspeita registrada", recebido: "Recebido e validado pela IA", confirmado: "Confirmado pelo atendente",
  encaminhado: "Encaminhado à equipe (RPA)", em_reparo: "Equipe em campo", resolvido: "Luz acesa · resolvido", recusado: "Recusado",
};
const ETIQUETAS = { suspeita: "suspeita", recebido: "recebido", confirmado: "confirmado", encaminhado: "encaminhado", em_reparo: "em reparo", resolvido: "resolvido", recusado: "recusado" };
const FLUXO = ["recebido", "confirmado", "encaminhado", "em_reparo", "resolvido"];
const ORIGENS = { cidadao: "📷 Foto", relato: "📍 Relato", robo: "🤖 Robô", "robo+foto": "🤖📷 Robô + foto" };

const $ = (s, raiz = document) => raiz.querySelector(s);
const $$ = (s, raiz = document) => [...raiz.querySelectorAll(s)];
const estado = { modo: "foto", arquivo: null, local: null, sensores: null, mapas: {}, marcadorLocal: null, camadaCentral: null };

function el(tag, props = {}, ...filhos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat()) if (f !== null && f !== undefined && f !== false) n.append(f instanceof Node ? f : document.createTextNode(String(f)));
  return n;
}
const dataHora = (iso) => new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
const nomeTipos = (tipos) => (tipos || []).map((t) => TIPOS[t] || t).join(" + ") || "Chamado";
const lista = (ul, itens) => ul.replaceChildren(...itens.map((t) => el("li", {}, t)));

async function api(caminho, opcoes = {}, tempoMs = 120000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), tempoMs);
  try {
    const r = await fetch(caminho, { ...opcoes, signal: ctrl.signal });
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof corpo.detail === "string" ? corpo.detail : `erro ${r.status}`);
    return corpo;
  } catch (e) {
    throw e.name === "AbortError" ? new Error("o servidor demorou demais; tente de novo") : e;
  } finally { clearTimeout(t); }
}

/* ================================================================== "base" da demonstração */
const base = {
  todos() { try { return JSON.parse(localStorage.getItem(CHAVE)) || []; } catch { return []; } },
  salvar(l) { try { localStorage.setItem(CHAVE, JSON.stringify(l.slice(-300))); } catch { /* sem armazenamento: segue sem fila */ } },
  adicionar(c) { const l = base.todos().filter((x) => x.id !== c.id); l.push(c); base.salvar(l); return c; },
  porProtocolo(p) { return base.todos().find((c) => c.protocolo === p.trim().toUpperCase()); },
  mudarStatus(id, status, nota) {
    const l = base.todos(), c = l.find((x) => x.id === id); if (!c) return null;
    c.status = status; c.historico.push({ status, ts: new Date().toISOString(), nota }); base.salvar(l); return c;
  },
};
const protocoloDe = (id) => `VSP-${id.replace(/-/g, "").slice(0, 6).toUpperCase()}`;

/* ================================================================== rotas */
function irPara(rota) {
  const [nome, param] = (rota || "inicio").split("/");
  const tela = document.getElementById(`tela-${nome}`) ? nome : "inicio";
  $$(".tela").forEach((t) => { t.hidden = t.dataset.tela !== tela; });
  $$(".nav a").forEach((a) => { if (a.dataset.rota === tela) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  if (tela === "inicio") acenderRua();
  if (tela === "reportar") abrirReportar();
  if (tela === "acompanhar") abrirAcompanhar(param);
  if (tela === "central") abrirCentral();
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", () => irPara(location.hash.slice(1)));
$$('.porta[data-modo="relato"]').forEach((a) => a.addEventListener("click", () => setTimeout(() => trocarModo("relato"), 0)));

/* ================================================================== status da API */
async function verificarApi() {
  const box = $("#status-api"), txt = $(".texto", box);
  const aviso = setTimeout(() => { box.dataset.estado = "acordando"; txt.textContent = "acordando a IA…"; }, 1500);
  try {
    const s = await api("/saude", {}, 90000);
    box.dataset.estado = s.modelo_carregado ? "ok" : "erro";
    txt.textContent = s.modelo_carregado ? "IA online" : "IA sem modelo";
  } catch { box.dataset.estado = "erro"; txt.textContent = "IA indisponível"; }
  finally { clearTimeout(aviso); }
}

/* ================================================================== abertura: a rua acende */
/* A rua é desenhada na largura real da tela (sem esticar), e redesenhada se a janela mudar. */
const NS = "http://www.w3.org/2000/svg";
const forma = (tag, attrs) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
let larguraRua = 0;
function montarRua() {
  const svg = $("#rua"), g = $("#postes"), w = Math.max(320, document.documentElement.clientWidth), h = Math.round(svg.getBoundingClientRect().height) || 300; // desenho na medida exata da tela
  if (`${w}x${h}` === larguraRua) return false;
  larguraRua = `${w}x${h}`;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  $("#rua-morros").setAttribute("d", `M0 ${h - 110} C${w * 0.15} ${h - 150} ${w * 0.3} ${h - 120} ${w * 0.45} ${h - 140} S${w * 0.75} ${h - 165} ${w} ${h - 130} V${h} H0Z`);
  $("#rua-calcada").setAttribute("d", `M0 ${h - 50} H${w} V${h} H0Z`);
  g.replaceChildren();
  const passo = w < 600 ? 120 : 190, chao = h - 50, n = Math.ceil(w / passo) + 1;
  for (let i = 0; i < n; i++) {
    const x = 40 + i * passo, topo = Math.max(78, h - 200) + (i % 2) * 8; // espaço acima para o halo não ser cortado
    const p = forma("g", { class: "poste" });
    p.append(
      forma("polygon", { class: "poste-cone", points: `${x + 34},${topo + 14} ${x - 30},${chao} ${x + 98},${chao}`, fill: "url(#cone)" }),
      forma("circle", { class: "poste-halo", cx: x + 34, cy: topo + 10, r: 70, fill: "url(#halo)" }),
      forma("path", { class: "poste-haste", d: `M${x} ${chao} V${topo + 20} Q${x} ${topo} ${x + 20} ${topo} H${x + 30}` }),
      forma("rect", { class: "poste-cabeca", x: x + 22, y: topo - 6, width: 26, height: 10, rx: 4 }),
      forma("ellipse", { class: "poste-lampada", cx: x + 35, cy: topo + 6, rx: 9, ry: 4 }),
    );
    g.append(p);
  }
  return true;
}
function acenderRua() {
  montarRua();
  const postes = $$("#postes .poste"), reduzir = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const apagado = Math.min(3, postes.length - 1); // o poste apagado da história... até o Vésper acender
  postes.forEach((p) => p.classList.remove("aceso"));
  postes.forEach((p, i) => { if (i !== apagado) setTimeout(() => p.classList.add("aceso"), reduzir ? 0 : 500 + i * 300); });
  setTimeout(() => postes[apagado]?.classList.add("aceso"), reduzir ? 0 : 4200);
}
let temporizadorRua;
window.addEventListener("resize", () => {
  clearTimeout(temporizadorRua);
  temporizadorRua = setTimeout(() => {
    if (!$("#tela-inicio").hidden && montarRua()) $$("#postes .poste").forEach((p) => p.classList.add("aceso"));
  }, 200);
});

/* ================================================================== mapas */
function camadaOSM() {
  return L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  });
}
function iconeLocal() {
  const d = el("div", { style: "width:22px;height:22px;border-radius:50%;background:#8fd2a7;box-shadow:0 0 0 6px rgba(143,210,167,.25),0 0 24px #8fd2a7;border:3px solid #0a1e13" });
  return L.divIcon({ className: "", html: d.outerHTML, iconSize: [22, 22], iconAnchor: [11, 11] });
}

/* ================================================================== endereço (Nominatim) */
function resumirEndereco(r) {
  const a = r.address || {};
  const rua = [a.road || a.pedestrian || a.footway, a.house_number].filter(Boolean).join(", ");
  const partes = [rua, a.suburb || a.neighbourhood || a.quarter, a.city || a.town || a.village || a.municipality].filter(Boolean);
  return (partes.length ? partes.join(" · ") : (r.display_name || "").split(",").slice(0, 3).join(",")).slice(0, 200);
}
async function geocodificarReverso(lat, lon) {
  try {
    const r = await fetch(`${NOMINATIM}/reverse?format=jsonv2&addressdetails=1&zoom=18&accept-language=pt-BR&lat=${lat}&lon=${lon}`);
    return r.ok ? resumirEndereco(await r.json()) : null;
  } catch { return null; }
}
async function buscarEnderecos(q) {
  const r = await fetch(`${NOMINATIM}/search?format=jsonv2&addressdetails=1&limit=5&countrycodes=br&accept-language=pt-BR&q=${encodeURIComponent(q)}`);
  return r.ok ? r.json() : [];
}

async function definirLocal(lat, lon, { endereco = null, fonte = "mapa", mover = true } = {}) {
  estado.local = { lat: +lat.toFixed(6), lon: +lon.toFixed(6), endereco, fonte };
  const mapa = estado.mapas.local;
  if (mapa) {
    if (!estado.marcadorLocal) {
      estado.marcadorLocal = L.marker([lat, lon], { icon: iconeLocal(), draggable: true }).addTo(mapa);
      estado.marcadorLocal.on("dragend", (e) => { const p = e.target.getLatLng(); definirLocal(p.lat, p.lng, { mover: false }); });
    } else estado.marcadorLocal.setLatLng([lat, lon]);
    if (mover) mapa.flyTo([lat, lon], 17, { duration: 0.8 });
  }
  mostrarEndereco(); atualizarBotaoEnviar();
  if (!endereco) {
    const achado = await geocodificarReverso(lat, lon);
    if (estado.local && estado.local.lat === +lat.toFixed(6)) { estado.local.endereco = achado; mostrarEndereco(); }
  }
}
function mostrarEndereco() {
  const p = $("#endereco-escolhido"), l = estado.local;
  if (!l) { p.className = "endereco-escolhido"; p.textContent = "Nenhum local marcado. Toque no mapa, busque o endereço ou use o GPS."; return; }
  p.className = "endereco-escolhido ok";
  p.textContent = `${l.endereco || "buscando o endereço…"}  (${l.lat.toFixed(5)}, ${l.lon.toFixed(5)})`;
}

let temporizadorBusca;
$("#busca-endereco").addEventListener("input", (e) => {
  clearTimeout(temporizadorBusca);
  const q = e.target.value.trim(), ul = $("#sugestoes");
  if (q.length < 4) { ul.hidden = true; return; }
  temporizadorBusca = setTimeout(async () => { // política do Nominatim: no máximo 1 busca por segundo
    try {
      const res = await buscarEnderecos(q);
      ul.replaceChildren(...(res.length ? res.map((r) => el("li", { role: "option", onclick: () => {
        ul.hidden = true; e.target.value = resumirEndereco(r);
        definirLocal(+r.lat, +r.lon, { endereco: resumirEndereco(r), fonte: "endereço" });
      } }, resumirEndereco(r))) : [el("li", { "aria-disabled": "true" }, "Nenhum endereço encontrado")]));
      ul.hidden = false;
    } catch { ul.hidden = true; }
  }, 800);
});
document.addEventListener("click", (e) => { if (!e.target.closest(".busca")) $("#sugestoes").hidden = true; });

$("#usar-gps").addEventListener("click", () => {
  const b = $("#usar-gps");
  if (!("geolocation" in navigator)) { b.textContent = "Navegador sem GPS"; return; }
  b.disabled = true; b.textContent = "📡 Localizando…";
  navigator.geolocation.getCurrentPosition(
    (p) => { b.disabled = false; b.textContent = `📡 GPS ±${Math.round(p.coords.accuracy)} m`; definirLocal(p.coords.latitude, p.coords.longitude, { fonte: "GPS" }); },
    () => { b.disabled = false; b.textContent = "📡 Sem permissão de GPS"; },
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 },
  );
});

/* ================================================================== reportar */
function abrirReportar() {
  if (!estado.mapas.local && window.L) {
    const m = L.map("mapa-local").setView([PAULISTA.lat, PAULISTA.lon], 13);
    camadaOSM().addTo(m);
    m.on("click", (e) => definirLocal(e.latlng.lat, e.latlng.lng, { mover: false }));
    estado.mapas.local = m;
  }
  setTimeout(() => estado.mapas.local?.invalidateSize(), 60);
}
function trocarModo(modo) {
  estado.modo = modo;
  $$(".modo").forEach((b) => { const ativo = b.dataset.modo === modo; b.classList.toggle("ativo", ativo); b.setAttribute("aria-checked", String(ativo)); });
  $("#area-foto").hidden = modo !== "foto";
  $("#area-relato").hidden = modo !== "relato";
  $("#enviar").textContent = modo === "foto" ? "Analisar e abrir chamado" : "Registrar relato";
  atualizarBotaoEnviar();
}
$$(".modo").forEach((b) => b.addEventListener("click", () => trocarModo(b.dataset.modo)));
function atualizarBotaoEnviar() {
  const relatoOk = estado.local && $$('input[name="problema"]:checked').length > 0;
  $("#enviar").disabled = estado.modo === "foto" ? !estado.arquivo : !relatoOk;
}
$$('input[name="problema"]').forEach((c) => c.addEventListener("change", atualizarBotaoEnviar));

function escolherArquivo(f) {
  if (!f) return;
  if (!/^image\/(jpeg|png|webp)$/.test(f.type)) { mostrarErro("Use uma foto JPEG, PNG ou WebP."); return; }
  estado.arquivo = f;
  const previa = $("#previa"); previa.src = URL.createObjectURL(f); previa.hidden = false;
  $("#soltar-texto").hidden = true; mostrarErro(""); atualizarBotaoEnviar();
}
$("#arquivo").addEventListener("change", (e) => escolherArquivo(e.target.files[0]));
const soltar = $("#soltar");
["dragenter", "dragover"].forEach((ev) => soltar.addEventListener(ev, (e) => { e.preventDefault(); soltar.classList.add("arrastando"); }));
["dragleave", "drop"].forEach((ev) => soltar.addEventListener(ev, (e) => { e.preventDefault(); soltar.classList.remove("arrastando"); }));
soltar.addEventListener("drop", (e) => escolherArquivo(e.dataTransfer.files[0]));

/* Com o local já marcado, reduzimos a foto no aparelho (mais rápido). Sem local, vai o original:
 * o GPS escondido na foto (EXIF) é lido pela API e descartado. */
async function prepararImagem(f) {
  if (!estado.local || !("createImageBitmap" in window)) return f;
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
  const itens = $$("#etapas li"); $("#etapas").hidden = false; let i = 0;
  const passo = () => { itens.forEach((li, j) => { li.className = j < i ? "feita" : j === i ? "atual" : ""; }); if (i < itens.length - 1) i++; };
  passo(); const id = setInterval(passo, 1300);
  return (ok) => { clearInterval(id); itens.forEach((li) => { li.className = ok ? "feita" : ""; }); if (!ok) $("#etapas").hidden = true; };
}

$("#form-relato").addEventListener("submit", async (e) => {
  e.preventDefault();
  const botao = $("#enviar"), rotulo = botao.textContent;
  botao.disabled = true; botao.textContent = estado.modo === "foto" ? "Analisando…" : "Registrando…"; mostrarErro("");
  const fim = estado.modo === "foto" ? animarEtapas() : () => {};
  try {
    if (estado.modo === "foto") {
      const d = new FormData();
      d.append("imagem", await prepararImagem(estado.arquivo));
      d.append("origem", estado.sensores ? "robo" : "cidadao");
      d.append("retornar_imagem", "true");
      d.append("incluir_orientacao", "true");
      if (estado.local) {
        d.append("latitude", estado.local.lat); d.append("longitude", estado.local.lon);
        if (estado.local.endereco) d.append("endereco", estado.local.endereco);
      }
      if (estado.sensores) {
        d.append("sensor_lux", estado.sensores.lux); d.append("sensor_distancia_cm", estado.sensores.dist);
        if (estado.sensores.alertas.length) d.append("alerta", estado.sensores.alertas.join(","));
      }
      const a = await api("/v1/analisar", { method: "POST", body: d });
      fim(true); mostrarAnalise(a);
    } else {
      const corpo = { latitude: estado.local.lat, longitude: estado.local.lon, endereco: estado.local.endereco || undefined,
        problema: $$('input[name="problema"]:checked').map((c) => c.value) };
      mostrarSuspeita(await api("/v1/relatos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) }));
    }
  } catch (err) { fim(false); mostrarErro(`Não deu certo: ${err.message}`); }
  finally { botao.textContent = rotulo; atualizarBotaoEnviar(); }
});

function desenhar(a) {
  const canvas = $("#canvas-resultado"), ctx = canvas.getContext("2d"), img = new Image();
  img.onload = () => {
    canvas.width = img.naturalWidth; canvas.height = img.naturalHeight; ctx.drawImage(img, 0, 0);
    const e = Math.max(3, Math.round(Math.max(img.naturalWidth, img.naturalHeight) / 260));
    ctx.font = `700 ${e * 6}px Inter, system-ui, sans-serif`;
    for (const d of a.deteccoes) {
      const [x1, y1, x2, y2] = d.bbox, [nome, cor] = CLASSES[d.classe] || [d.classe, "#8fd2a7"];
      ctx.lineWidth = e; ctx.strokeStyle = cor; ctx.shadowColor = cor; ctx.shadowBlur = e * 4;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1); ctx.shadowBlur = 0;
      const rot = `${nome} ${Math.round(d.confianca * 100)}%`, w = ctx.measureText(rot).width + e * 3, h = e * 8, y = y1 - h < 0 ? y1 : y1 - h;
      ctx.fillStyle = cor; ctx.fillRect(x1, y, w, h); ctx.fillStyle = "#0a1e13"; ctx.fillText(rot, x1 + e * 1.5, y + h - e * 2);
    }
  };
  img.src = a.imagem_anonimizada_base64 ? `data:image/jpeg;base64,${a.imagem_anonimizada_base64}` : URL.createObjectURL(estado.arquivo);
}
function veredito(classe, icone, titulo, sub) {
  const v = $("#veredito"); v.className = `veredito ${classe}`;
  v.replaceChildren(el("span", { class: "icone" }, icone), el("div", {}, el("strong", {}, titulo), el("small", {}, sub)));
}
function prioridade(p) {
  $("#bloco-prioridade").hidden = p.nivel === "nenhuma";
  $("#prioridade-nivel").textContent = `${NIVEIS[p.nivel] || p.nivel} · ${p.pontuacao}/100`;
  $("#prioridade-barra").style.width = "0";
  requestAnimationFrame(() => requestAnimationFrame(() => { $("#prioridade-barra").style.width = `${p.pontuacao}%`; }));
  lista($("#prioridade-fatores"), p.fatores);
}
function mostrarProtocolo(c) {
  $("#protocolo-caixa").hidden = !c;
  if (!c) return;
  $("#protocolo").textContent = c.protocolo;
  $("#ir-acompanhar").setAttribute("href", `#acompanhar/${c.protocolo}`);
}

function mostrarAnalise(a) {
  $("#resultado").hidden = false; $("#resultado-imagem").hidden = false; desenhar(a);
  const tipos = a.fusao?.tipos_chamado || [], r = a.resumo, abre = a.validacao.abrir_chamado;
  if (abre) veredito("abre", "🚨", "Chamado aberto", tipos.length ? `Setor: ${nomeTipos(tipos)}` : "Encaminhado à prefeitura");
  else if (!a.validacao.foto_valida) veredito("invalida", "📷", "A foto não serviu de prova", a.validacao.motivos[0] || "tente outra foto");
  else veredito("ok", "✨", "Rua iluminada", "Nenhuma falha encontrada: nenhum chamado necessário");
  prioridade(a.prioridade);
  $("#info-trecho").textContent = TRECHOS[r.status_trecho] || r.status_trecho;
  $("#info-postes").textContent = `${r.postes_acesos} aceso${r.postes_acesos === 1 ? "" : "s"} · ${r.postes_apagados} apagado${r.postes_apagados === 1 ? "" : "s"}`;
  $("#info-setor").textContent = tipos.length ? nomeTipos(tipos) : "—";
  const loc = a.localizacao;
  $("#endereco-resultado").textContent = loc ? `📍 ${loc.endereco || `${loc.latitude.toFixed(5)}, ${loc.longitude.toFixed(5)}`}${loc.fonte === "exif" ? " (GPS da foto)" : ""}` : "📍 Sem localização: marque o local para a prefeitura achar o poste.";
  lista($("#lista-motivos"), [...a.validacao.motivos, ...(a.fusao?.motivos || [])]);
  orientar(a, abre);
  lista($("#selos"), ["🔒 Foto não armazenada", a.privacidade.rostos_borrados ? `🙂 ${a.privacidade.rostos_borrados} rosto(s) borrado(s)` : "🙂 Nenhum rosto na foto", "🧭 EXIF descartado", `🧠 modelo ${a.modelo.versao}`]);
  let c = null;
  if (abre) c = base.adicionar({
    id: a.id_captura, protocolo: protocoloDe(a.id_captura), ts: a.timestamp, origem: estado.sensores ? "robo+foto" : "cidadao",
    lat: loc?.latitude, lon: loc?.longitude, endereco: loc?.endereco,
    nivel: a.prioridade.nivel, pontos: a.prioridade.pontuacao, tipos, trecho: r.status_trecho,
    fatores: a.prioridade.fatores, motivos: [...a.validacao.motivos, ...(a.fusao?.motivos || [])].slice(0, 6),
    status: "recebido", historico: [{ status: "recebido", ts: a.timestamp, nota: "IA validou a evidência" }],
  });
  mostrarProtocolo(c);
  if (estado.sensores) desvincular();
  $("#resultado").scrollIntoView({ behavior: "smooth", block: "start" });
}

function mostrarSuspeita(r) {
  $("#resultado").hidden = false; $("#resultado-imagem").hidden = true;
  veredito("suspeita", "📍", "Relato registrado", r.proximo_passo);
  prioridade(r.prioridade_previa);
  $("#info-trecho").textContent = "A confirmar";
  $("#info-postes").textContent = "sem foto";
  $("#info-setor").textContent = nomeTipos(r.alertas.map((x) => `suspeita_${x}`));
  $("#endereco-resultado").textContent = `📍 ${r.localizacao.endereco || `${r.localizacao.latitude}, ${r.localizacao.longitude}`}`;
  lista($("#lista-motivos"), r.prioridade_previa.fatores);
  $("#orientacao").hidden = true;
  lista($("#selos"), ["🔒 Nenhuma foto enviada", "📍 Só o local é registrado"]);
  mostrarProtocolo(base.adicionar({
    id: r.id_alerta, protocolo: protocoloDe(r.id_alerta), ts: r.timestamp, origem: "relato",
    lat: r.localizacao.latitude, lon: r.localizacao.longitude, endereco: r.localizacao.endereco,
    nivel: r.prioridade_previa.nivel, pontos: r.prioridade_previa.pontuacao, tipos: r.alertas.map((x) => `suspeita_${x}`), trecho: "suspeita",
    fatores: r.prioridade_previa.fatores, motivos: [], status: "suspeita",
    historico: [{ status: "suspeita", ts: r.timestamp, nota: "relato do cidadão, aguardando foto" }],
  }));
  $("#resultado").scrollIntoView({ behavior: "smooth", block: "start" });
}

function orientar(a, abre) {
  const box = $("#orientacao");
  if (!abre) { box.hidden = true; return; }
  const ok = (a.orientacao || []).find((o) => o.status === "ok");
  box.hidden = false;
  box.replaceChildren(...(ok
    ? [el("strong", {}, "⏱️ Prazo oficial: "), ok.resposta, ok.trecho_citado && el("blockquote", {}, `Fonte (${ok.citacao}): ${ok.trecho_citado}`), el("small", {}, ok.aviso || "")]
    : [el("strong", {}, "📞 Canal oficial: "), "em São Paulo, iluminação pública pelo telefone 156 ou pelo portal SP156. Prazo usual: até 24 horas.",
       el("small", {}, "Orientação fixa nesta demonstração; com o assistente de IA generativa ligado, o prazo vem citado da fonte oficial.")]));
}

/* ================================================================== acompanhar */
function abrirAcompanhar(protocolo) {
  const recentes = base.todos().sort((a, b) => b.ts.localeCompare(a.ts)).slice(0, 8);
  $("#meus-protocolos").replaceChildren(...(recentes.length ? [el("small", { style: "color:var(--texto-3)" }, "Recentes: "),
    ...recentes.map((c) => el("button", { type: "button", onclick: () => { location.hash = `#acompanhar/${c.protocolo}`; } }, c.protocolo))] : []));
  if (protocolo) { $("#campo-protocolo").value = protocolo; mostrarLinhaTempo(protocolo); } else $("#linha-tempo").hidden = true;
}
$("#form-protocolo").addEventListener("submit", (e) => { e.preventDefault(); location.hash = `#acompanhar/${$("#campo-protocolo").value.trim().toUpperCase()}`; });

function mostrarLinhaTempo(protocolo) {
  const c = base.porProtocolo(protocolo), box = $("#linha-tempo"); box.hidden = false;
  if (!c) { box.replaceChildren(el("p", {}, "Protocolo não encontrado neste navegador."), el("small", { style: "color:var(--texto-3)" }, "Na demonstração, os chamados ficam salvos no navegador onde foram feitos.")); return; }
  const fluxo = c.status === "recusado" ? [...c.historico.map((h) => h.status)] : c.historico[0].status === "suspeita" ? ["suspeita", ...FLUXO.slice(1)] : FLUXO;
  const feitos = new Map(c.historico.map((h) => [h.status, h])), atual = fluxo.indexOf(c.status);
  box.replaceChildren(
    el("div", { class: "cabeca" },
      el("div", {}, el("p", { class: "sobretitulo" }, c.protocolo), el("h2", {}, nomeTipos(c.tipos)),
        el("p", { class: "endereco-resultado" }, `📍 ${c.endereco || (Number.isFinite(c.lat) ? `${c.lat.toFixed(5)}, ${c.lon.toFixed(5)}` : "sem localização")}`)),
      el("div", {}, el("span", { class: `pts ${c.nivel}`, style: "display:inline-grid;place-items:center;width:52px;height:52px;border-radius:14px;font-weight:800;color:#0a1e13" }, c.pontos),
        " ", el("small", {}, `prioridade ${(NIVEIS[c.nivel] || "").toLowerCase()}`))),
    el("ol", { class: "passos-status" }, fluxo.map((s, i) => {
      const h = feitos.get(s);
      return el("li", { class: i < atual || (i === atual && ["resolvido", "recusado"].includes(s)) ? "feito" : i === atual ? "feito atual" : "" },
        STATUS[s], el("small", {}, h ? `${dataHora(h.ts)}${h.nota ? ` · ${h.nota}` : ""}` : "aguardando"));
    })));
}

/* ================================================================== robô */
const lux = $("#lux"), dist = $("#dist");
function posicaoRobo(i = 0) {
  const p = estado.local || PAULISTA;
  return { latitude: +(p.lat + i * 0.0002).toFixed(6), longitude: +p.lon.toFixed(6) };
}
function atualizarSensores() {
  $("#lux-valor").textContent = `${Number(lux.value).toFixed(1)} lux`; $("#dist-valor").textContent = `${dist.value} cm`;
  $("#json-robo").textContent = JSON.stringify({ origem: "robo", ...posicaoRobo(), sensor_lux: +lux.value, sensor_distancia_cm: +dist.value }, null, 2);
}
[lux, dist].forEach((i) => i.addEventListener("input", atualizarSensores));
const CENARIOS = { normal: [30, 8], escuro: [2, 8], buraco: [35, 26], ambos: [2.5, 24] };
$$("[data-cenario]").forEach((b) => b.addEventListener("click", () => { [lux.value, dist.value] = CENARIOS[b.dataset.cenario]; atualizarSensores(); enviarAlerta(); }));

async function enviarAlerta(leitura = { ...posicaoRobo(), sensor_lux: +lux.value, sensor_distancia_cm: +dist.value }) {
  const corpo = { origem: "robo", ...leitura };
  $("#json-robo").textContent = JSON.stringify(corpo, null, 2);
  try {
    const r = await api("/v1/alerta-robo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
    $("#led").dataset.acao = r.acao_robo;
    $("#robo-led").setAttribute("class", `led-robo ${r.acao_robo}`);
    const suspeita = r.status === "suspeita";
    $("#robo-resposta").replaceChildren(
      el("strong", {}, suspeita ? `Suspeita registrada · prioridade ${(NIVEIS[r.prioridade_previa.nivel] || "").toLowerCase()} (${r.prioridade_previa.pontuacao})` : "Tudo normal neste ponto"),
      el("span", {}, suspeita ? r.proximo_passo : "Nenhum sensor disparou."));
    lista($("#robo-fatores"), suspeita ? r.prioridade_previa.fatores : []);
    const conf = $("#confirmar-foto"); conf.hidden = !suspeita; conf.onclick = () => vincular(corpo, r.alertas);
    if (suspeita) base.adicionar({
      id: r.id_alerta, protocolo: protocoloDe(r.id_alerta), ts: r.timestamp, origem: "robo", lat: corpo.latitude, lon: corpo.longitude,
      nivel: r.prioridade_previa.nivel, pontos: r.prioridade_previa.pontuacao, tipos: r.alertas.map((x) => `suspeita_${x}`), trecho: "suspeita",
      fatores: r.prioridade_previa.fatores, motivos: [], status: "suspeita",
      historico: [{ status: "suspeita", ts: r.timestamp, nota: `robô: ${corpo.sensor_lux} lux, ${corpo.sensor_distancia_cm} cm` }],
    });
    return r;
  } catch (e) { $("#robo-resposta").replaceChildren(el("strong", {}, "Falha ao falar com a API"), el("span", {}, e.message)); return null; }
}
$("#enviar-alerta").addEventListener("click", () => enviarAlerta());
$("#patrulha").addEventListener("click", async () => {
  const b = $("#patrulha"), trilha = $("#trilha"); b.disabled = true;
  trilha.replaceChildren(...Array.from({ length: 12 }, () => el("span")));
  for (let i = 0; i < 12; i++) {
    const escuro = i >= 6 && i < 10;
    const l = { ...posicaoRobo(i), sensor_lux: escuro ? +(0.8 + Math.random() * 3).toFixed(1) : +(12 + Math.random() * 25).toFixed(1), sensor_distancia_cm: i === 8 ? 24 : +(6 + Math.random() * 3).toFixed(1) };
    lux.value = l.sensor_lux; dist.value = l.sensor_distancia_cm; atualizarSensores();
    const r = await enviarAlerta(l);
    if (r) trilha.children[i].dataset.acao = r.acao_robo;
    await new Promise((ok) => setTimeout(ok, 650));
  }
  b.disabled = false;
});
function vincular(corpo, alertas) {
  estado.sensores = { lux: corpo.sensor_lux, dist: corpo.sensor_distancia_cm, alertas };
  $("#sensores-resumo").textContent = `${corpo.sensor_lux} lux · ${corpo.sensor_distancia_cm} cm · ${alertas.join(" + ")}`;
  $("#sensores-vinculados").hidden = false;
  trocarModo("foto"); location.hash = "#reportar";
  if (!estado.local) setTimeout(() => definirLocal(corpo.latitude, corpo.longitude, { fonte: "robô" }), 100);
}
function desvincular() { estado.sensores = null; $("#sensores-vinculados").hidden = true; }
$("#desvincular").addEventListener("click", desvincular);

/* ================================================================== central */
const fsStatus = $("#filtro-status");
fsStatus.append(...Object.entries(STATUS).map(([k, v]) => el("option", { value: k }, v)));
["#filtro-prioridade", "#filtro-status", "#filtro-origem"].forEach((s) => $(s).addEventListener("change", abrirCentral));
$("#limpar-fila").addEventListener("click", () => { if (confirm("Apagar todos os chamados desta demonstração?")) { base.salvar([]); abrirCentral(); } });
const fechado = (c) => ["resolvido", "recusado"].includes(c.status);

function abrirCentral() {
  const todos = base.todos(), abertos = todos.filter((c) => !fechado(c));
  $("#kpi-abertos").textContent = abertos.length;
  $("#kpi-alta").textContent = abertos.filter((c) => c.nivel === "alta").length;
  $("#kpi-suspeitas").textContent = todos.filter((c) => c.status === "suspeita").length;
  $("#kpi-resolvidos").textContent = todos.filter((c) => c.status === "resolvido").length;
  const fp = $("#filtro-prioridade").value, fs = fsStatus.value, fo = $("#filtro-origem").value;
  const fila = todos.filter((c) => (!fp || c.nivel === fp) && (!fs || c.status === fs) && (!fo || c.origem === fo))
    .sort((a, b) => (fechado(a) - fechado(b)) || b.pontos - a.pontos || b.ts.localeCompare(a.ts));
  $("#fila-vazia").hidden = fila.length > 0;
  $("#lista-chamados").replaceChildren(...fila.map((c) => el("li", {}, el("button", { class: "chamado", type: "button", onclick: () => abrirDetalhe(c.id) },
    el("span", { class: `pts ${c.nivel}` }, c.pontos),
    el("div", {}, nomeTipos(c.tipos), el("small", {}, `${c.protocolo} · ${dataHora(c.ts)} · ${ORIGENS[c.origem] || c.origem}`), c.endereco && el("small", {}, `📍 ${c.endereco}`)),
    el("span", { class: `etiqueta ${c.status}` }, ETIQUETAS[c.status] || c.status)))));

  if (!window.L) return;
  if (!estado.mapas.central) {
    estado.mapas.central = L.map("mapa-central").setView([PAULISTA.lat, PAULISTA.lon], 13);
    camadaOSM().addTo(estado.mapas.central);
    estado.camadaCentral = L.layerGroup().addTo(estado.mapas.central);
  }
  setTimeout(() => estado.mapas.central.invalidateSize(), 60);
  estado.camadaCentral.clearLayers();
  const cor = { alta: "#ff7a6b", media: "#f2d27a", baixa: "#74b08e", nenhuma: "#74b08e" };
  const pontos = fila.filter((c) => Number.isFinite(c.lat) && Number.isFinite(c.lon));
  for (const [i, c] of pontos.entries()) {
    const k = c.status === "resolvido" ? "#ffc86b" : cor[c.nivel];
    const desloc = pontos.slice(0, i).filter((o) => o.lat === c.lat && o.lon === c.lon).length * 0.00008; // separa pinos no mesmo ponto
    L.circleMarker([c.lat + desloc, c.lon + desloc], { radius: 7 + c.pontos / 12, color: k, fillColor: k, fillOpacity: c.status === "resolvido" ? 0.9 : 0.5, weight: 2 })
      .bindPopup(el("div", {}, el("strong", {}, `${c.protocolo} · ${c.pontos} pts`), el("br"), nomeTipos(c.tipos), el("br"),
        el("a", { href: "#central", onclick: (e) => { e.preventDefault(); abrirDetalhe(c.id); } }, "ver detalhes")))
      .addTo(estado.camadaCentral);
  }
  if (pontos.length) estado.mapas.central.fitBounds(L.latLngBounds(pontos.map((c) => [c.lat, c.lon])).pad(0.35), { maxZoom: 16 });
}

const PROXIMO = {
  suspeita: [["confirmado", "Confirmar (vistoria)"], ["recusado", "Recusar"]],
  recebido: [["confirmado", "Confirmar chamado"], ["recusado", "Recusar"]],
  confirmado: [["encaminhado", "Encaminhar à equipe (RPA)"]],
  encaminhado: [["em_reparo", "Equipe em campo"]],
  em_reparo: [["resolvido", "Resolvido · luz acesa"]],
};
function abrirDetalhe(id) {
  const c = base.todos().find((x) => x.id === id); if (!c) return;
  const dlg = $("#detalhe");
  $("#detalhe-corpo").replaceChildren(
    el("p", { class: "sobretitulo" }, `${c.protocolo} · ${ORIGENS[c.origem] || c.origem}`),
    el("h2", {}, nomeTipos(c.tipos)),
    el("p", { class: "endereco-resultado" }, `📍 ${c.endereco || (Number.isFinite(c.lat) ? `${c.lat.toFixed(5)}, ${c.lon.toFixed(5)}` : "sem localização")}`),
    el("div", { class: "linha-info" },
      el("div", {}, el("span", {}, "Prioridade"), el("strong", {}, `${NIVEIS[c.nivel] || c.nivel} · ${c.pontos}`)),
      el("div", {}, el("span", {}, "Trecho"), el("strong", {}, TRECHOS[c.trecho] || c.trecho)),
      el("div", {}, el("span", {}, "Status"), el("strong", {}, ETIQUETAS[c.status] || c.status))),
    c.fatores?.length && el("div", {}, el("strong", {}, "Por que essa prioridade"), el("ul", { class: "fatores" }, c.fatores.map((f) => el("li", {}, f)))),
    c.motivos?.length && el("details", { class: "motivos" }, el("summary", {}, "Evidência analisada pela IA"), el("ul", {}, c.motivos.map((m) => el("li", {}, m)))),
    el("div", { class: "detalhe-acoes" },
      ...(PROXIMO[c.status] || []).map(([s, rot]) => el("button", { class: s === "recusado" ? "botao" : "botao primario", type: "button", onclick: () => {
        base.mudarStatus(c.id, s, s === "encaminhado" ? "RPA registrou no sistema da prefeitura" : "pelo atendente"); dlg.close(); abrirCentral();
      } }, rot)),
      el("button", { class: "botao fantasma", value: "fechar" }, "Fechar")),
  );
  dlg.showModal();
}

/* ================================================================== início */
atualizarSensores();
verificarApi();
irPara(location.hash.slice(1) || "inicio");
