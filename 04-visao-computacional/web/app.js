/* Vésper · front do MVP (da escuridão à luz).
 * Fala com a API da própria Visão (mesma origem) e, só para endereço, com o Nominatim (OpenStreetMap).
 * Texto vindo de fora entra sempre por textContent. Os chamados ficam na CENTRAL do servidor (/v1/chamados),
 * compartilhada entre aparelhos; o navegador guarda só a lista dos protocolos que ele abriu. Foto e vídeo
 * nunca são guardados, nem aqui nem no servidor. */
"use strict";

/* ================================================================== constantes */
const PAULISTA = { lat: -23.5614, lon: -46.6559 };
const MEUS = "vesper:meus";
const NOMINATIM = "https://nominatim.openstreetmap.org";
const TIPOS = {
  conserto_poste: "Conserto de poste",
  instalacao_iluminacao: "Instalação de iluminação",
  poda_ou_obstrucao: "Poda / obstrução",
  buraco: "Buraco na via",
  trecho_sem_luz: "Trecho sem luz (inspeção)",
  falta_de_energia: "Falta de energia (concessionária)",
  suspeita_escuro: "Suspeita: rua escura",
  suspeita_buraco: "Suspeita: buraco",
};
const TRECHOS = { iluminada: "Iluminado", parcial: "Parcialmente escuro", escura: "Escuro", sem_postes_visiveis: "Sem postes visíveis", suspeita: "A confirmar" };
const NIVEIS = { alta: "Alta", media: "Média", baixa: "Baixa", nenhuma: "Nenhuma" };
const CLASSES = { poste_aceso: ["aceso", "#ffc86b"], poste_apagado: ["apagado", "#ff7a6b"], buraco: ["buraco", "#f2d27a"] };
const STATUS = {
  suspeita: "Suspeita registrada", recebido: "Recebido e validado pela IA", confirmado: "Confirmado pela central",
  encaminhado: "Encaminhado ao responsável", em_reparo: "Equipe em campo", resolvido: "Resolvido: luz acesa", recusado: "Recusado",
};
const ETIQUETAS = { suspeita: "suspeita", recebido: "recebido", confirmado: "confirmado", encaminhado: "encaminhado", em_reparo: "em reparo", resolvido: "resolvido", recusado: "recusado" };
const FLUXO = ["recebido", "confirmado", "encaminhado", "em_reparo", "resolvido"];
const ORIGENS = { cidadao: "Foto", relato: "Relato sem imagem", robo: "Robô", "robo+foto": "Robô + foto" };

const $ = (s, raiz = document) => raiz.querySelector(s);
const $$ = (s, raiz = document) => [...raiz.querySelectorAll(s)];
const estado = { modo: "foto", arquivo: null, video: null, gps: null, fila: [], local: null, sensores: null, mapas: {}, marcadorLocal: null, camadaCentral: null, analise: null, mapaLuz: false };
const NIVEIS_LUZ = { iluminada: "Iluminada", pouca_iluminacao: "Pouca iluminação", muito_escura: "Muito escura", breu: "Breu" };

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

/* ================================================================== central (servidor) */
const JSON_POST = (corpo) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
const central = {
  listar: () => api("/v1/chamados?limite=300", {}, 45000),
  regioes: () => api("/v1/regioes", {}, 45000),
  obter: (p) => api(`/v1/chamados/${encodeURIComponent(p)}`, {}, 45000),
  mudar: (p, status, nota) => api(`/v1/chamados/${encodeURIComponent(p)}/status`, JSON_POST({ status, nota })),
};
const norm = (c) => ({ ...c, lat: c.latitude ?? undefined, lon: c.longitude ?? undefined });
/* "meus protocolos": só os números, para o cidadão achar o chamado de novo neste aparelho */
const meus = {
  todos() { try { return JSON.parse(localStorage.getItem(MEUS)) || []; } catch { return []; } },
  guardar(p) {
    if (!p) return;
    try { localStorage.setItem(MEUS, JSON.stringify([p, ...meus.todos().filter((x) => x !== p)].slice(0, 20))); } catch { /* sem armazenamento */ }
  },
};
const origemDe = (c) => (c.evidencia === "video" ? "Vídeo ao vivo" : ORIGENS[c.origem] || c.origem);
/* ícone de linha do sprite do index.html (padrão Lucide): sempre o mesmo traço */
function icone(nome) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "ic"); svg.setAttribute("aria-hidden", "true");
  const u = document.createElementNS("http://www.w3.org/2000/svg", "use");
  u.setAttribute("href", `#i-${nome}`); svg.append(u);
  return svg;
}
const rotular = (b, nome, texto) => b.replaceChildren(icone(nome), texto);
const textoLocal = (lat, lon, endereco) => endereco || (Number.isFinite(lat) ? `${lat.toFixed(5)}, ${lon.toFixed(5)}` : "Sem localização");

/* ================================================================== rotas */
function irPara(rota) {
  const [nome, param] = (rota || "inicio").split("/");
  if (nome === "agora") { irPara("reportar"); novoRelato(); trocarModo("foto"); abrirCamera(); return; }
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
  const d = el("div", { style: "width:22px;height:22px;border-radius:50%;background:#ffc86b;box-shadow:0 0 0 6px rgba(255, 200, 107,.25),0 0 24px #ffc86b;border:3px solid #070b16" });
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
  if (!l) { p.className = "endereco-escolhido"; p.textContent = "Nenhum local marcado."; return; }
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

/* Devolve uma promessa (true/false): a câmera ao vivo espera por ela antes de enviar sozinha. */
function pedirGps() {
  const b = $("#usar-gps"), chip = $("#camera-gps");
  if (!("geolocation" in navigator)) { rotular(b, "nav", "Navegador sem GPS"); chip.textContent = "Sem GPS: marque no mapa depois"; return Promise.resolve(false); }
  b.disabled = true; rotular(b, "nav", "Localizando…"); chip.textContent = "Localizando…";
  estado.gps = new Promise((ok) => navigator.geolocation.getCurrentPosition(
    (p) => {
      b.disabled = false; rotular(b, "nav", `Localização obtida (±${Math.round(p.coords.accuracy)} m)`); chip.textContent = `GPS ±${Math.round(p.coords.accuracy)} m`;
      definirLocal(p.coords.latitude, p.coords.longitude, { fonte: "GPS" }); ok(true);
    },
    () => { b.disabled = false; rotular(b, "nav", "Sem permissão de localização"); chip.textContent = "Sem GPS: marque o local depois"; ok(false); },
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 },
  )).finally(() => { estado.gps = null; });
  return estado.gps;
}
$("#usar-gps").addEventListener("click", pedirGps);

/* ================================================================== reportar */
function abrirReportar() {
  if (!estado.mapas.local && window.L) {
    const m = L.map("mapa-local").setView([PAULISTA.lat, PAULISTA.lon], 13);
    camadaOSM().addTo(m);
    m.on("click", (e) => definirLocal(e.latlng.lat, e.latlng.lng, { mover: false }));
    estado.mapas.local = m;
    const l = estado.local; // local que chegou antes do mapa (QR de cartaz, GPS da câmera)
    if (l && !estado.marcadorLocal) definirLocal(l.lat, l.lon, { endereco: l.endereco, fonte: l.fonte });
  }
  setTimeout(() => estado.mapas.local?.invalidateSize(), 60);
}
function trocarModo(modo) {
  estado.modo = modo;
  $$(".modo").forEach((b) => { const ativo = b.dataset.modo === modo; b.classList.toggle("ativo", ativo); b.setAttribute("aria-checked", String(ativo)); });
  $("#area-foto").hidden = modo !== "foto";
  $("#area-relato").hidden = modo !== "relato";
  $("#enviar span").textContent = modo === "foto" ? "Analisar e abrir chamado" : "Registrar relato";
  atualizarBotaoEnviar();
}
$$(".modo").forEach((b) => b.addEventListener("click", () => trocarModo(b.dataset.modo)));
function atualizarBotaoEnviar() {
  const relatoOk = estado.local && $$('input[name="problema"]:checked').length > 0;
  $("#enviar").disabled = estado.modo === "foto" ? !(estado.arquivo || estado.video) : !relatoOk;
}
$$('input[name="problema"]').forEach((c) => c.addEventListener("change", atualizarBotaoEnviar));

function escolherArquivo(f) {
  if (!f) return;
  if (!/^image\/(jpeg|png|webp)$/.test(f.type)) { mostrarErro("Use uma foto JPEG, PNG ou WebP. No iPhone, ajuste a câmera para \"Mais compatível\"."); return; }
  estado.arquivo = f; estado.video = null; $("#previa-video").hidden = true;
  const previa = $("#previa"); previa.src = URL.createObjectURL(f); previa.hidden = false;
  $("#soltar-texto").hidden = true; mostrarErro(""); atualizarBotaoEnviar();
}
function escolherVideo(blob) {
  estado.video = blob; estado.arquivo = null; $("#previa").hidden = true;
  const v = $("#previa-video"); v.src = URL.createObjectURL(blob); v.hidden = false; v.play().catch(() => {});
  $("#soltar-texto").hidden = true; mostrarErro(""); atualizarBotaoEnviar();
}

/* ================================================================== câmera ao vivo */
/* getUserMedia na câmera traseira. Foto: um quadro do vídeo vira JPEG. Vídeo: MediaRecorder, até 10 s.
 * Ao capturar, se o local já estiver marcado (GPS), o chamado é enviado sozinho: imediatismo. */
const cam = { stream: null, gravador: null, pedacos: [], relogio: null, inicio: 0, salvar: true };
const MAX_VIDEO_S = 10;
async function abrirCamera() {
  const dlg = $("#camera"), erro = $("#camera-erro");
  erro.hidden = true; $("#camera-dica").hidden = false;
  if (!dlg.open) dlg.showModal();
  if (!estado.local && !estado.gps) pedirGps();
  else if (estado.local) $("#camera-gps").textContent = "Local marcado";
  if (!navigator.mediaDevices?.getUserMedia) {
    erro.textContent = "Este navegador não abre a câmera por aqui. Feche e escolha uma foto da galeria."; erro.hidden = false; return;
  }
  try {
    cam.stream = await navigator.mediaDevices.getUserMedia({ audio: false,
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } } });
    if (!dlg.open) { pararCamera(); return; }
    $("#camera-video").srcObject = cam.stream;
  } catch (e) {
    erro.textContent = e.name === "NotAllowedError"
      ? "Sem permissão para usar a câmera. Libere nas configurações do navegador ou escolha uma foto da galeria."
      : "Não consegui abrir a câmera deste aparelho. Escolha uma foto da galeria.";
    erro.hidden = false;
  }
}
function pararCamera() {
  if (cam.gravador?.state === "recording") { cam.salvar = false; cam.gravador.stop(); }
  clearInterval(cam.relogio);
  cam.stream?.getTracks().forEach((t) => t.stop()); cam.stream = null;
  $("#camera-video").srcObject = null; $("#camera-tempo").hidden = true;
  $("#camera-gravar").classList.remove("ativo"); $("#camera-gravar small").textContent = "Gravar";
  if (location.hash === "#agora") history.replaceState(null, "", "#reportar");
}
$("#camera").addEventListener("close", pararCamera);
$("#camera-fechar").addEventListener("click", () => $("#camera").close());
$("#abrir-camera").addEventListener("click", abrirCamera);

$("#camera-foto").addEventListener("click", async () => {
  const v = $("#camera-video");
  if (!cam.stream || !v.videoWidth) return;
  const c = el("canvas"); c.width = v.videoWidth; c.height = v.videoHeight;
  c.getContext("2d").drawImage(v, 0, 0);
  const blob = await new Promise((ok) => c.toBlob(ok, "image/jpeg", 0.9));
  if (!blob) return;
  escolherArquivo(new File([blob], "ao-vivo.jpg", { type: "image/jpeg" }));
  $("#camera").close(); aposCaptura();
});

function formatoVideo() {
  if (!window.MediaRecorder) return null;
  return ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm", "video/mp4"].find((t) => MediaRecorder.isTypeSupported(t)) || "";
}
$("#camera-gravar").addEventListener("click", () => {
  if (cam.gravador?.state === "recording") { if (Date.now() - cam.inicio > 1000) cam.gravador.stop(); return; }
  const tipo = formatoVideo();
  if (!cam.stream || tipo === null) { const e = $("#camera-erro"); e.textContent = "Este navegador não grava vídeo; use a foto."; e.hidden = false; return; }
  cam.pedacos = []; cam.salvar = true;
  cam.gravador = new MediaRecorder(cam.stream, { ...(tipo ? { mimeType: tipo } : {}), videoBitsPerSecond: 2_500_000 });
  cam.gravador.ondataavailable = (e) => { if (e.data.size) cam.pedacos.push(e.data); };
  cam.gravador.onstop = () => {
    clearInterval(cam.relogio);
    if (!cam.salvar || !cam.pedacos.length) return;
    escolherVideo(new Blob(cam.pedacos, { type: (cam.gravador.mimeType || tipo || "video/webm").split(";")[0] }));
    $("#camera").close(); aposCaptura();
  };
  cam.gravador.start(500); cam.inicio = Date.now();
  $("#camera-gravar").classList.add("ativo"); $("#camera-gravar small").textContent = "Parar";
  $("#camera-dica").hidden = true;
  const tempo = $("#camera-tempo"); tempo.hidden = false;
  cam.relogio = setInterval(() => {
    const s = (Date.now() - cam.inicio) / 1000;
    tempo.textContent = `Gravando ${Math.floor(s)} s de ${MAX_VIDEO_S}`;
    if (s >= MAX_VIDEO_S && cam.gravador.state === "recording") cam.gravador.stop();
  }, 250);
});

async function aposCaptura() {
  if (!estado.local && estado.gps) await Promise.race([estado.gps, new Promise((ok) => setTimeout(ok, 8000))]);
  if (estado.local) { $("#form-relato").requestSubmit(); return; }
  mostrarErro("Falta só o local: use sua localização, busque o endereço ou toque no mapa. Depois é só enviar.");
  $("#passo-local").scrollIntoView({ behavior: "smooth", block: "center" });
}

/* QR Code: abre o site direto na câmera ao vivo */
$("#abrir-qr").addEventListener("click", () => $("#qr").showModal());
$("#arquivo").addEventListener("change", (e) => escolherArquivo(e.target.files[0]));
$("#arquivo-camera").addEventListener("change", (e) => escolherArquivo(e.target.files[0]));
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
  const botao = $("#enviar"), texto = $("#enviar span"), rotulo = texto.textContent;
  botao.disabled = true; texto.textContent = estado.modo === "foto" ? "Analisando…" : "Registrando…"; mostrarErro("");
  $("#etapa-detectar").textContent = estado.video ? "Analisando os quadros do vídeo" : "Procurando postes acesos e apagados";
  const fim = estado.modo === "foto" ? animarEtapas() : () => {};
  try {
    if (estado.modo === "foto" && estado.video) {
      const d = new FormData(), v = estado.video;
      d.append("video", v, v.type.includes("mp4") ? "ao-vivo.mp4" : "ao-vivo.webm");
      d.append("retornar_imagem", "true"); d.append("incluir_orientacao", "true");
      if (estado.local) {
        d.append("latitude", estado.local.lat); d.append("longitude", estado.local.lon);
        if (estado.local.endereco) d.append("endereco", estado.local.endereco);
      }
      const a = await api("/v1/analisar-video", { method: "POST", body: d }, 180000);
      fim(true); mostrarAnalise(a);
    } else if (estado.modo === "foto") {
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
      mostrarSuspeita(await api("/v1/relatos", JSON_POST(corpo)));
    }
  } catch (err) { fim(false); mostrarErro(`Não deu certo: ${err.message}`); }
  finally { texto.textContent = rotulo; atualizarBotaoEnviar(); }
});

/* Mapa de luz: a grade 6x8 da análise de cena pintada sobre a foto (breu = verde-noite, luz = âmbar). */
function pintarMapaLuz(ctx, grade, w, h) {
  const L = grade.length, C = grade[0].length, cw = w / C, ch = h / L;
  const max = Math.max(30, ...grade.flat()); // relativo à própria foto: o bloco mais claro brilha
  for (let i = 0; i < L; i++) for (let j = 0; j < C; j++) {
    const v = grade[i][j] / max;
    ctx.fillStyle = v < 0.4 ? `rgba(7, 11, 22, ${0.8 - v * 1.2})` : `rgba(255, 200, 107, ${0.18 + (v - 0.4) * 0.6})`;
    ctx.fillRect(j * cw, i * ch, Math.ceil(cw), Math.ceil(ch));
    ctx.fillStyle = "rgba(234, 238, 247, .85)";
    ctx.font = `600 ${Math.max(11, Math.round(ch / 6))}px Inter, system-ui, sans-serif`;
    ctx.fillText(String(grade[i][j]), j * cw + 6, i * ch + Math.max(14, ch / 5));
  }
  ctx.strokeStyle = "rgba(255, 200, 107, .25)"; ctx.lineWidth = 1;
  for (let j = 1; j < C; j++) { ctx.beginPath(); ctx.moveTo(j * cw, 0); ctx.lineTo(j * cw, h); ctx.stroke(); }
  for (let i = 1; i < L; i++) { ctx.beginPath(); ctx.moveTo(0, i * ch); ctx.lineTo(w, i * ch); ctx.stroke(); }
}
$("#ver-mapa-luz").addEventListener("click", () => {
  estado.mapaLuz = !estado.mapaLuz;
  $("#ver-mapa-luz").setAttribute("aria-pressed", String(estado.mapaLuz));
  if (estado.analise) desenhar(estado.analise);
});

function desenhar(a) {
  estado.analise = a;
  $("#ver-mapa-luz").hidden = !a.cena;
  const canvas = $("#canvas-resultado"), ctx = canvas.getContext("2d"), img = new Image();
  img.onload = () => {
    canvas.width = img.naturalWidth; canvas.height = img.naturalHeight; ctx.drawImage(img, 0, 0);
    if (estado.mapaLuz && a.cena) pintarMapaLuz(ctx, a.cena.grade_luz, img.naturalWidth, img.naturalHeight);
    const e = Math.max(3, Math.round(Math.max(img.naturalWidth, img.naturalHeight) / 260));
    ctx.font = `700 ${e * 6}px Inter, system-ui, sans-serif`;
    for (const d of a.deteccoes) {
      const [x1, y1, x2, y2] = d.bbox, [nome, cor] = CLASSES[d.classe] || [d.classe, "#ffc86b"];
      ctx.lineWidth = e; ctx.strokeStyle = cor; ctx.shadowColor = cor; ctx.shadowBlur = e * 4;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1); ctx.shadowBlur = 0;
      const rot = `${nome} ${Math.round(d.confianca * 100)}%`, w = ctx.measureText(rot).width + e * 3, h = e * 8, y = y1 - h < 0 ? y1 : y1 - h;
      ctx.fillStyle = cor; ctx.fillRect(x1, y, w, h); ctx.fillStyle = "#070b16"; ctx.fillText(rot, x1 + e * 1.5, y + h - e * 2);
    }
  };
  if (a.imagem_anonimizada_base64) img.src = `data:image/jpeg;base64,${a.imagem_anonimizada_base64}`;
  else if (estado.arquivo) img.src = URL.createObjectURL(estado.arquivo);
}
function veredito(classe, nomeIcone, titulo, sub) {
  const v = $("#veredito"); v.className = `veredito ${classe}`;
  v.replaceChildren(el("span", { class: "icone" }, icone(nomeIcone)), el("div", {}, el("strong", {}, titulo), el("small", {}, sub)));
}
function selos(itens) {
  $("#selos").replaceChildren(...itens.filter(Boolean).map(([nome, texto]) => el("li", {}, icone(nome), texto)));
}
/* depois da análise: o formulário sai e o resultado ocupa a tela (imagem | resultado) */
function mostrarResultado(comImagem) {
  $("#form-relato").hidden = true;
  $("#resultado").hidden = false;
  $("#grade-reportar").classList.add("com-resultado");
  $("#grade-reportar").classList.toggle("sem-imagem", !comImagem);
  $("#resultado-imagem").hidden = !comImagem;
}
function novoRelato() {
  $("#form-relato").hidden = false; $("#resultado").hidden = true;
  $("#grade-reportar").classList.remove("com-resultado", "sem-imagem");
  estado.arquivo = null; estado.video = null; estado.analise = null;
  $("#previa").hidden = true; $("#previa-video").hidden = true; $("#soltar-texto").hidden = false;
  ["#arquivo", "#arquivo-camera"].forEach((s) => { $(s).value = ""; });
  $("#etapas").hidden = true; mostrarErro(""); atualizarBotaoEnviar();
  setTimeout(() => estado.mapas.local?.invalidateSize(), 60);
}
function prioridade(p) {
  $("#bloco-prioridade").hidden = p.nivel === "nenhuma";
  $("#prioridade-nivel").textContent = `${NIVEIS[p.nivel] || p.nivel} · ${p.pontuacao}/100`;
  $("#prioridade-barra").style.width = "0";
  requestAnimationFrame(() => requestAnimationFrame(() => { $("#prioridade-barra").style.width = `${p.pontuacao}%`; }));
  lista($("#prioridade-fatores"), p.fatores);
}
function mostrarProtocolo(protocolo) {
  $("#protocolo-caixa").hidden = !protocolo;
  if (!protocolo) return;
  meus.guardar(protocolo);
  $("#protocolo").textContent = protocolo;
  $("#ir-acompanhar").setAttribute("href", `#acompanhar/${protocolo}`);
}
function mostrarEncaminhamento(lista) {
  const box = $("#encaminhamento");
  box.hidden = !lista?.length;
  if (!lista?.length) return;
  box.replaceChildren(el("strong", {}, icone("send"), "Para onde o chamado vai"),
    el("ul", {}, lista.map((e) => el("li", {}, el("b", {}, e.orgao), el("span", {}, e.canal), el("small", {}, e.motivo)))));
}

function mostrarAnalise(a) {
  mostrarResultado(true); desenhar(a);
  const tipos = a.fusao?.tipos_chamado || [], r = a.resumo, abre = a.validacao.abrir_chamado;
  if (abre) veredito("abre", "alert", "Chamado aberto", nomeTipos(tipos));
  else if (!a.validacao.foto_valida) veredito("invalida", "camera", "A imagem não serviu de prova", a.validacao.motivos[0] || "Tente outra imagem.");
  else veredito("ok", "sun", "Rua iluminada", "Nenhuma falha encontrada. Nenhum chamado necessário.");
  prioridade(a.prioridade);
  mostrarCena(a.cena);
  $("#info-trecho").textContent = TRECHOS[r.status_trecho] || r.status_trecho;
  $("#info-postes").textContent = `${r.postes_acesos} aceso${r.postes_acesos === 1 ? "" : "s"} · ${r.postes_apagados} apagado${r.postes_apagados === 1 ? "" : "s"}`;
  $("#info-setor").textContent = tipos.length ? nomeTipos(tipos) : "—";
  const loc = a.localizacao;
  $("#endereco-resultado").replaceChildren(icone("pin"), loc ? `${textoLocal(loc.latitude, loc.longitude, loc.endereco)}${loc.fonte === "exif" ? " (GPS da foto)" : ""}` : "Sem localização. Marque o local para a equipe achar o poste.");
  lista($("#lista-motivos"), [...a.validacao.motivos, ...(a.fusao?.motivos || [])]);
  orientar(a, abre);
  mostrarEncaminhamento(a.encaminhar_para);
  const v = a.video;
  selos([v && ["video", `${v.quadros_analisados} quadros analisados`], ["lock", v ? "Vídeo não guardado" : "Imagem não guardada"],
    ["face", a.privacidade.rostos_borrados ? `${a.privacidade.rostos_borrados} rosto(s) borrado(s)` : "Nenhum rosto"], ["cpu", `Modelo ${a.modelo.versao}`]]);
  mostrarProtocolo(a.protocolo);
  if (abre && !a.protocolo) mostrarErro("A IA confirmou a falha, mas a central não respondeu agora. Tente enviar de novo em instantes.");
  if (estado.sensores) desvincular();
  $("#tela-reportar").scrollIntoView({ behavior: "smooth", block: "start" });
}

function mostrarCena(c) {
  const box = $("#cena");
  box.hidden = !c;
  if (!c) return;
  box.dataset.nivel = c.nivel;
  box.replaceChildren(...[
    el("div", { class: "cena-topo" }, el("span", {}, "Leitura da região"), el("strong", {}, `${NIVEIS_LUZ[c.nivel] || c.nivel} · escuridão ${c.indice_escuridao}/100`)),
    el("div", { class: "medidor", title: "luz que sobra na cena" }, el("span", { style: `width:${Math.max(2, 100 - c.indice_escuridao)}%` })),
    el("div", { class: "cena-dados" },
      el("span", {}, `${c.fontes_de_luz} fonte${c.fontes_de_luz === 1 ? "" : "s"} de luz`),
      el("span", {}, `luz no chão ${Math.round(c.luz_no_chao)}/255`),
      el("span", {}, `${Math.round(c.area_iluminada * 100)}% iluminada`)),
    c.possivel_apagao && el("p", { class: "apagao" }, icone("zap"), el("span", {}, el("strong", {}, "Possível apagão na região. "),
      "Nenhuma luz elétrica na cena. O chamado também vai para a distribuidora de energia.")),
  ].filter(Boolean)); // sem apagão, o "false" do && não pode virar texto na tela
}

function mostrarSuspeita(r) {
  mostrarResultado(false); $("#cena").hidden = true;
  veredito("suspeita", "pin", "Relato registrado", r.proximo_passo);
  prioridade(r.prioridade_previa);
  $("#info-trecho").textContent = "A confirmar";
  $("#info-postes").textContent = "sem imagem";
  $("#info-setor").textContent = nomeTipos(r.alertas.map((x) => `suspeita_${x}`));
  $("#endereco-resultado").replaceChildren(icone("pin"), textoLocal(r.localizacao.latitude, r.localizacao.longitude, r.localizacao.endereco));
  lista($("#lista-motivos"), r.prioridade_previa.fatores);
  $("#orientacao").hidden = true;
  selos([["lock", "Nenhuma imagem enviada"], ["pin", "Só o local é registrado"]]);
  mostrarEncaminhamento(r.encaminhar_para);
  mostrarProtocolo(r.protocolo);
  $("#tela-reportar").scrollIntoView({ behavior: "smooth", block: "start" });
}
$("#novo-relato").addEventListener("click", () => { novoRelato(); window.scrollTo(0, 0); });

function orientar(a, abre) {
  const box = $("#orientacao");
  if (!abre) { box.hidden = true; return; }
  const ok = (a.orientacao || []).find((o) => o.status === "ok");
  box.hidden = false;
  box.replaceChildren(...(ok
    ? [el("strong", {}, icone("clock"), "Prazo oficial: "), ok.resposta, ok.trecho_citado && el("blockquote", {}, `Fonte (${ok.citacao}): ${ok.trecho_citado}`), el("small", {}, ok.aviso || "")]
    : [el("strong", {}, icone("phone-call"), "Canal oficial: "), "em São Paulo, telefone 156 ou portal SP156. Prazo usual: até 24 horas.",
       el("small", {}, "Com o assistente de IA generativa ligado, o prazo vem citado da fonte oficial.")]));
}

/* ================================================================== acompanhar */
function abrirAcompanhar(protocolo) {
  const recentes = meus.todos().slice(0, 8);
  $("#meus-protocolos").replaceChildren(...(recentes.length ? [el("small", {}, "Seus protocolos:"),
    ...recentes.map((p) => el("button", { type: "button", onclick: () => { location.hash = `#acompanhar/${p}`; } }, p))] : []));
  if (protocolo) { $("#campo-protocolo").value = protocolo; mostrarLinhaTempo(protocolo); } else $("#linha-tempo").hidden = true;
}
$("#form-protocolo").addEventListener("submit", (e) => { e.preventDefault(); location.hash = `#acompanhar/${$("#campo-protocolo").value.trim().toUpperCase()}`; });

async function mostrarLinhaTempo(protocolo) {
  const box = $("#linha-tempo"); box.hidden = false; box.replaceChildren(el("p", { class: "carregando" }, "Buscando na central…"));
  let c, todos = [], regs = [];
  try {
    c = norm(await central.obter(protocolo));
    [todos, regs] = await Promise.all([central.listar().catch(() => []), central.regioes().catch(() => [])]);
  } catch (e) {
    box.replaceChildren(el("p", { class: "aviso-busca" }, /não encontrado/.test(e.message) ? "Protocolo não encontrado. Confira as letras e os números." : `Não consegui consultar a central: ${e.message}`));
    return;
  }
  const fluxo = c.status === "recusado" ? [...c.historico.map((h) => h.status)] : c.historico[0].status === "suspeita" ? ["suspeita", ...FLUXO.slice(1)] : FLUXO;
  const feitos = new Map(c.historico.map((h) => [h.status, h])), atual = fluxo.indexOf(c.status);
  // vizinhos: outros chamados abertos a até 500 m; e se ele faz parte de um alerta de região
  const regiao = regs.find((r) => r.protocolos.includes(c.protocolo));
  const vizinhos = Number.isFinite(c.lat) ? todos.filter((o) => o.protocolo !== c.protocolo && !fechado(o)
    && Number.isFinite(o.latitude) && distanciaM(c.lat, c.lon, o.latitude, o.longitude) <= 500).length : 0;

  const mapa = el("div", { class: "mapa-acompanhar", "aria-label": "Local do chamado no mapa" });
  box.replaceChildren(
    el("header", { class: "cabeca" },
      el("div", {}, el("p", { class: "sobretitulo" }, c.protocolo), el("h2", {}, nomeTipos(c.tipos)),
        el("p", { class: "endereco-resultado" }, icone("pin"), textoLocal(c.lat, c.lon, c.endereco))),
      el("div", { class: "selo-prioridade" }, el("span", { class: `pts ${c.nivel}` }, c.pontos), el("small", {}, `prioridade ${(NIVEIS[c.nivel] || "").toLowerCase()}`))),
    el("div", { class: "acompanhar-grade" },
      el("section", { class: "cartao" }, el("h3", {}, "Andamento"),
        el("ol", { class: "passos-status" }, fluxo.map((s, i) => {
          const h = feitos.get(s);
          return el("li", { class: i < atual || (i === atual && ["resolvido", "recusado"].includes(s)) ? "feito" : i === atual ? "feito atual" : "" },
            STATUS[s], el("small", {}, h ? `${dataHora(h.ts)}${h.nota ? ` · ${h.nota}` : ""}` : "aguardando"));
        }))),
      el("div", { class: "acompanhar-lado" },
        el("section", { class: "cartao info" }, el("h3", {}, icone("send"), "Encaminhado para"),
          ...(c.encaminhar_para?.length ? c.encaminhar_para.map((e) => el("p", {}, el("strong", {}, e.orgao), el("span", {}, e.canal)))
            : [el("p", {}, "Definido quando a central confirmar.")])),
        el("section", { class: "cartao info" }, el("h3", {}, icone("users"), "Na sua região"),
          el("p", { class: "numero" }, el("strong", {}, String(vizinhos)), el("span", {}, vizinhos === 1 ? "outro relato a até 500 m" : "outros relatos a até 500 m")),
          regiao && el("p", { class: `alerta-regiao ${regiao.tipo}` }, icone(regiao.tipo === "apagao_regiao" ? "zap" : "moon"), regiao.titulo)),
        el("section", { class: "cartao info mapa-info" }, mapa))));
  if (estado.mapas.acompanhar) { estado.mapas.acompanhar.remove(); estado.mapas.acompanhar = null; }
  if (window.L && Number.isFinite(c.lat)) {
    const m = L.map(mapa, { zoomControl: false, attributionControl: true }).setView([c.lat, c.lon], 16);
    camadaOSM().addTo(m);
    L.marker([c.lat, c.lon], { icon: iconeLocal() }).addTo(m);
    estado.mapas.acompanhar = m;
    setTimeout(() => m.invalidateSize(), 60);
  } else mapa.replaceChildren(el("p", { class: "dica" }, "Sem localização registrada."));
}
function distanciaM(lat1, lon1, lat2, lon2) {
  const r = 6371000, rad = Math.PI / 180, a = Math.sin((lat2 - lat1) * rad / 2) ** 2
    + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin((lon2 - lon1) * rad / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
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
    const r = await api("/v1/alerta-robo", JSON_POST(corpo));
    $("#led").dataset.acao = r.acao_robo;
    $("#robo-led").setAttribute("class", `led-robo ${r.acao_robo}`);
    const suspeita = r.status === "suspeita";
    $("#robo-resposta").replaceChildren(
      el("strong", {}, suspeita ? `Suspeita registrada · prioridade ${(NIVEIS[r.prioridade_previa.nivel] || "").toLowerCase()} (${r.prioridade_previa.pontuacao})` : "Tudo normal neste ponto"),
      el("span", {}, suspeita ? r.proximo_passo : "Nenhum sensor disparou."));
    lista($("#robo-fatores"), suspeita ? r.prioridade_previa.fatores : []);
    const conf = $("#confirmar-foto"); conf.hidden = !suspeita; conf.onclick = () => vincular(corpo, r.alertas);
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
$("#filtro-origem").append(el("option", { value: "video" }, "Vídeo ao vivo"));
["#filtro-prioridade", "#filtro-status", "#filtro-origem"].forEach((s) => $(s).addEventListener("change", () => desenharCentral()));
$("#atualizar-fila").addEventListener("click", () => abrirCentral());
const fechado = (c) => ["resolvido", "recusado"].includes(c.status);
setInterval(() => { if (!$("#tela-central").hidden && !$("#detalhe").open && !document.hidden) abrirCentral(); }, 15000);

function avisoCentral(msg) {
  let p = $("#erro-central");
  if (!p) { p = el("p", { class: "erro", id: "erro-central", role: "alert" }); $(".fila").prepend(p); }
  p.textContent = msg; p.hidden = !msg;
}
async function abrirCentral() {
  try {
    const [todos, regs] = await Promise.all([central.listar(), central.regioes()]);
    estado.fila = todos.map(norm); estado.regioes = regs; avisoCentral("");
  } catch (e) { avisoCentral(`Não consegui falar com a central: ${e.message}`); }
  desenharCentral();
}
function desenharRegioes(regs) {
  $("#kpi-regioes").textContent = regs.length;
  const box = $("#regioes"); box.hidden = !regs.length;
  box.replaceChildren(...regs.map((r) => {
    const apagao = r.tipo === "apagao_regiao";
    return el("article", { class: `regiao ${r.tipo}` },
      el("strong", {}, icone(apagao ? "zap" : "moon"), r.titulo),
      el("span", {}, `${r.relatos} chamados num raio de ${r.raio_m} m · ${r.sinais_apagao} sem nenhuma luz · desde ${dataHora(r.primeiro)}`),
      el("small", {}, `Encaminhar para: ${r.encaminhar_para.map((e) => `${e.orgao} (${e.canal})`).join(" · ")}`));
  }));
}
function desenharCentral() {
  const todos = estado.fila, abertos = todos.filter((c) => !fechado(c));
  desenharRegioes(estado.regioes || []);
  $("#kpi-abertos").textContent = abertos.length;
  $("#kpi-alta").textContent = abertos.filter((c) => c.nivel === "alta").length;
  $("#kpi-suspeitas").textContent = todos.filter((c) => c.status === "suspeita").length;
  $("#kpi-resolvidos").textContent = todos.filter((c) => c.status === "resolvido").length;
  const fp = $("#filtro-prioridade").value, fs = fsStatus.value, fo = $("#filtro-origem").value;
  const fila = todos.filter((c) => (!fp || c.nivel === fp) && (!fs || c.status === fs) && (!fo || c.origem === fo || (fo === "video" && c.evidencia === "video")))
    .sort((a, b) => (fechado(a) - fechado(b)) || b.pontos - a.pontos || b.ts.localeCompare(a.ts));
  $("#fila-vazia").hidden = fila.length > 0;
  $("#lista-chamados").replaceChildren(...fila.map((c) => el("li", {}, el("button", { class: "chamado", type: "button", onclick: () => abrirDetalhe(c.protocolo) },
    el("span", { class: `pts ${c.nivel}` }, c.pontos),
    el("div", {}, nomeTipos(c.tipos), el("small", {}, `${c.protocolo} · ${dataHora(c.ts)} · ${origemDe(c)}`), c.endereco && el("small", {}, c.endereco)),
    el("span", { class: `etiqueta ${c.status}` }, ETIQUETAS[c.status] || c.status)))));

  if (!window.L) return;
  if (!estado.mapas.central) {
    estado.mapas.central = L.map("mapa-central").setView([PAULISTA.lat, PAULISTA.lon], 13);
    camadaOSM().addTo(estado.mapas.central);
    estado.camadaCentral = L.layerGroup().addTo(estado.mapas.central);
  }
  setTimeout(() => estado.mapas.central.invalidateSize(), 60);
  estado.camadaCentral.clearLayers();
  for (const r of estado.regioes || []) {
    const k = r.tipo === "apagao_regiao" ? "#ff7a6b" : "#f2d27a";
    L.circle([r.latitude, r.longitude], { radius: r.raio_m, color: k, weight: 2, dashArray: "6 6", fillColor: k, fillOpacity: 0.1 })
      .bindPopup(el("div", {}, el("strong", {}, r.titulo), el("br"), `${r.relatos} chamados · ${r.sinais_apagao} sem nenhuma luz`))
      .addTo(estado.camadaCentral);
  }
  const cor = { alta: "#ff7a6b", media: "#f2d27a", baixa: "#a6b0c8", nenhuma: "#a6b0c8" };
  const pontos = fila.filter((c) => Number.isFinite(c.lat) && Number.isFinite(c.lon));
  for (const [i, c] of pontos.entries()) {
    const k = c.status === "resolvido" ? "#4ade80" : cor[c.nivel];
    const desloc = pontos.slice(0, i).filter((o) => o.lat === c.lat && o.lon === c.lon).length * 0.00008; // separa pinos no mesmo ponto
    L.circleMarker([c.lat + desloc, c.lon + desloc], { radius: 7 + c.pontos / 12, color: k, fillColor: k, fillOpacity: c.status === "resolvido" ? 0.9 : 0.5, weight: 2 })
      .bindPopup(el("div", {}, el("strong", {}, `${c.protocolo} · ${c.pontos} pts`), el("br"), nomeTipos(c.tipos), el("br"),
        el("a", { href: "#central", onclick: (e) => { e.preventDefault(); abrirDetalhe(c.protocolo); } }, "ver detalhes")))
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
function abrirDetalhe(protocolo) {
  const c = estado.fila.find((x) => x.protocolo === protocolo); if (!c) return;
  const dlg = $("#detalhe");
  $("#detalhe-corpo").replaceChildren(
    el("p", { class: "sobretitulo" }, `${c.protocolo} · ${origemDe(c)}`),
    el("h2", {}, nomeTipos(c.tipos)),
    el("p", { class: "endereco-resultado" }, icone("pin"), textoLocal(c.lat, c.lon, c.endereco)),
    el("div", { class: "linha-info" },
      el("div", {}, el("span", {}, "Prioridade"), el("strong", {}, `${NIVEIS[c.nivel] || c.nivel} · ${c.pontos}`)),
      el("div", {}, el("span", {}, "Trecho"), el("strong", {}, TRECHOS[c.trecho] || c.trecho)),
      el("div", {}, el("span", {}, "Status"), el("strong", {}, ETIQUETAS[c.status] || c.status))),
    c.fatores?.length && el("div", {}, el("strong", {}, "Por que essa prioridade"), el("ul", { class: "fatores" }, c.fatores.map((f) => el("li", {}, f)))),
    c.encaminhar_para?.length && el("div", { class: "encaminhamento" }, el("strong", {}, icone("send"), "Encaminhar para"),
      el("ul", {}, c.encaminhar_para.map((e) => el("li", {}, el("b", {}, e.orgao), el("span", {}, e.canal), el("small", {}, e.motivo))))),
    c.motivos?.length && el("details", { class: "motivos" }, el("summary", {}, "Evidência analisada pela IA"), el("ul", {}, c.motivos.map((m) => el("li", {}, m)))),
    el("div", { class: "detalhe-acoes" },
      ...(PROXIMO[c.status] || []).map(([s, rot]) => el("button", { class: s === "recusado" ? "botao" : "botao primario", type: "button", onclick: async (e) => {
        e.preventDefault(); e.target.disabled = true;
        const nota = s === "encaminhado" ? `RPA enviou a ${c.encaminhar_para?.[0]?.orgao || "equipe responsável"}` : "pelo atendente";
        try { await central.mudar(c.protocolo, s, nota); dlg.close(); abrirCentral(); }
        catch (err) { e.target.disabled = false; alert(`Não deu certo: ${err.message}`); }
      } }, rot)),
      el("button", { class: "botao fantasma", value: "fechar" }, "Fechar")),
  );
  dlg.showModal();
}

/* cartões vivos: um holofote acompanha o mouse dentro do cartão (o CSS cuida da subida e da sombra) */
const CARTOES_VIVOS = ".porta, .jornada li, .garantias li, .disc, .kpi, .opcao, .cartao.info, .regiao, .chamado, .faixa-numeros div";
document.addEventListener("pointermove", (e) => {
  if (e.pointerType !== "mouse") return;
  const c = e.target.closest?.(CARTOES_VIVOS);
  if (!c) return;
  const r = c.getBoundingClientRect();
  c.style.setProperty("--x", `${e.clientX - r.left}px`);
  c.style.setProperty("--y", `${e.clientY - r.top}px`);
}, { passive: true });

/* ================================================================== início */
/* QR de cartaz: ?lat=..&lon=..&ref=.. já marca o local (o cidadão só filma e envia) */
(() => {
  const q = new URLSearchParams(location.search), lat = parseFloat(q.get("lat")), lon = parseFloat(q.get("lon"));
  if (Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180) {
    definirLocal(lat, lon, { endereco: (q.get("ref") || "").slice(0, 120) || null, fonte: "QR do local" });
  }
})();
atualizarSensores();
verificarApi();
irPara(location.hash.slice(1) || "inicio");
