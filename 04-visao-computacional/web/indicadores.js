/* Vésper · aba Indicadores: a camada Ouro do Big Data (pasta 02) dentro do MVP.
 * Lê GET /v1/indicadores (gerado da Ouro do Databricks por scripts/exportar_ouro_web.py) e desenha
 * KPIs, Centro × Periferia, top distritos, evolução por mês, mapa por distrito e a linhagem Bronze → Prata → Ouro.
 * Cores validadas (dataviz, fundo escuro): Centro #b98536 · Periferia #5f80cc. Usa $ e el do app.js. */
"use strict";
(() => {
  const tela = $("#tela-indicadores");
  if (!tela) return;
  const COR = { Centro: "#b98536", Periferia: "#5f80cc" };
  const n = (v, d = 0) => Number(v).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
  let carregado = false;

  async function abrir() {
    if (carregado) return;
    try {
      const r = await fetch("/v1/indicadores");
      if (!r.ok) throw new Error(`erro ${r.status}`);
      desenhar(await r.json());
      carregado = true;
    } catch (e) {
      const p = $("#ind-erro"); p.hidden = false; p.textContent = `Não consegui carregar os indicadores: ${e.message}`;
    }
  }

  function desenhar(d) {
    const k = d.camadas, t = d.tempo_conserto, total = k.fato_chamado;
    const validos = d.validos.find((v) => v.tipo === "valido") || { chamados: 0, pct: 0 };
    const avaliadas = d.validos.reduce((s, v) => s + v.chamados, 0);
    const fechados = d.mapa.reduce((s, r) => s + Math.round((r.pct_finalizado * r.chamados) / 100), 0);
    $("#ind-escopo").textContent = `O SP156 não tem o serviço "lâmpada apagada". Usamos como indicador da infraestrutura de iluminação: ${d.escopo.map((e) => `"${e}"`).join(" e ")}. É essa lacuna que o relato do cidadão no Vésper cobre.`;
    $("#ind-total").textContent = n(total);
    $("#ind-total-sub").textContent = `${d.periodo} · ${n(k.distritos)} distritos`;
    $("#ind-tempo").textContent = `${n(t.media_dias, 1)} dias`;
    $("#ind-tempo-sub").textContent = `mediana de ${n(t.mediana_dias, 0)} dias; 10% passam de ${n(t.p90_dias, 0)}. Fechamento no SP156, não o reparo em campo`;
    $("#ind-final").textContent = `${n((100 * fechados) / total, 0)}%`;
    $("#ind-final-sub").textContent = `${n(fechados)} de ${n(total)} chamados fechados até set/2026`;
    $("#ind-validos").textContent = `${n(validos.pct, 1)}%`;
    $("#ind-validos-sub").textContent = `${n(validos.chamados)} de ${n(avaliadas)} chamados do SP156 passam nas 3 regras`;

    // Centro × Periferia (uma medida, duas zonas)
    const zonas = d.impacto_zona, maxZ = Math.max(...zonas.map((z) => z.chamados_por_100mil_hab));
    $("#ind-zonas").replaceChildren(...zonas.map((z) => el("div", {
      class: "linha-zona", title: `${z.zona}: ${n(z.chamados)} chamados · ${n(z.populacao)} habitantes · ${n(z.chamados_por_100mil_hab, 1)} por 100 mil`,
    }, el("span", { class: "nome" }, z.zona),
      el("span", { class: "trilho" }, el("i", { style: `width:${(100 * z.chamados_por_100mil_hab) / maxZ}%;background:${COR[z.zona] || "#5f80cc"}` })),
      el("b", {}, n(z.chamados_por_100mil_hab, 1)),
      el("small", {}, `${n(z.chamados)} chamados · ${n(z.populacao)} hab.`))));
    const c = zonas.find((z) => z.zona === "Centro"), p = zonas.find((z) => z.zona === "Periferia");
    if (c && p) $("#ind-impacto-txt").replaceChildren("O Centro registra ", el("strong", {}, `${n(c.chamados_por_100mil_hab / p.chamados_por_100mil_hab, 1)}× mais`),
      " chamados por morador que a Periferia, que soma mais chamados no total (", el("strong", {}, n(p.chamados)),
      "). A conta usa a população residente (IBGE 2022): o Centro recebe muita gente de fora, então parte da diferença é circulação.");

    // top distritos (barras horizontais, cor = zona, legenda + valor direto)
    $("#ind-legenda").replaceChildren(...Object.entries(COR).map(([z, cor]) => el("span", {}, el("i", { style: `background:${cor}` }), z)));
    const top = d.top_distritos, maxT = Math.max(...top.map((x) => x.chamados));
    $("#ind-top").replaceChildren(...top.map((x) => el("li", { title: `${x.distrito} (${x.zona}): ${n(x.chamados)} chamados · ${n(x.pct, 1)}% do total` },
      el("span", { class: "nome" }, x.distrito),
      el("span", { class: "trilho" }, el("i", { style: `width:${(100 * x.chamados) / maxT}%;background:${COR[x.zona] || "#5f80cc"}` })),
      el("b", {}, n(x.chamados)))));

    // por mês (uma série: colunas)
    const meses = d.por_mes, maxM = Math.max(...meses.map((m) => m.chamados));
    const variacao = meses.length > 1 ? (100 * (meses.at(-1).chamados - meses[0].chamados)) / meses[0].chamados : 0;
    $("#ind-mes-sub").textContent = meses.length > 1
      ? `${variacao >= 0 ? "+" : ""}${n(variacao, 1)}% de ${meses[0].nome_mes} a ${meses.at(-1).nome_mes}/${meses.at(-1).ano}` : "";
    $("#ind-meses").replaceChildren(...meses.map((m) => el("div", { class: "coluna", title: `${m.nome_mes}/${m.ano}: ${n(m.chamados)} chamados` },
      el("b", {}, n(m.chamados)),
      el("span", { class: "col-barra" }, el("i", { style: `height:${(100 * m.chamados) / maxM}%` })),
      el("span", { class: "mes" }, m.nome_mes))));

    // linhagem, qualidade e prova do incremental
    $("#ind-camadas").replaceChildren(
      el("li", { class: "bronze" }, el("strong", {}, "Bronze"), el("span", {}, `${n(k.bronze_sp156)} linhas brutas do SP156 + clima + IBGE (Airflow, COPY INTO em 2 lotes)`)),
      el("li", { class: "prata" }, el("strong", {}, "Prata"), el("span", {}, `${n(k.prata_sp156)} chamados válidos, tipados e sem duplicatas (MERGE)`)),
      el("li", { class: "ouro" }, el("strong", {}, "Ouro"), el("span", {}, `fato com ${n(k.fato_chamado)} chamados de poste e fiação + dimensões de local e tempo → ${n(k.distritos)} distritos`)));
    const ROT_REGRA = { R1_data_abertura_valida: "R1 · data de abertura válida", R2_fim_depois_do_inicio: "R2 · fechamento depois da abertura",
      R3_distrito_preenchido: "R3 · distrito preenchido" };
    $("#ind-qualidade").replaceChildren(...d.qualidade.filter((q) => ROT_REGRA[q.regra]).map((q) =>
      el("li", { title: `${n(q.avaliadas)} avaliadas · ${n(q.barradas)} barradas` }, el("span", {}, ROT_REGRA[q.regra]),
        el("b", {}, `${n(q.barradas)} barradas (${n(q.pct_barrado, 1)}%)`))));
    const ROT_ETAPA = { 1: "só o lote 1", 2: "chega o lote 2", 3: "roda de novo, sem arquivo novo" };
    $("#ind-incremental").replaceChildren(...d.incremental.filter((x) => x.tabela === "bronze_sp156").map((x) =>
      el("li", {}, el("span", {}, ROT_ETAPA[String(x.etapa)[0]] || x.etapa), el("b", {}, `${n(x.linhas)} linhas · ${n(x.arquivos)} arq.`))));
    $("#ind-origem").textContent = `Fonte: ${d.fonte}. Valores do notebook executado no Databricks e da tabela ouro_mvp_mapa.`;

    // tabela da Ouro
    const cols = [["distrito", "Distrito"], ["zona", "Zona"], ["populacao", "População", 0], ["chamados", "Chamados", 0],
      ["chamados_por_100mil_hab", "Por 100 mil hab.", 1], ["tempo_medio_dias", "Dias até fechar", 1], ["pct_finalizado", "% fechado", 1]];
    $("#ind-tabela").replaceChildren(
      el("thead", {}, el("tr", {}, ...cols.map(([, t2]) => el("th", { scope: "col" }, t2)))),
      el("tbody", {}, ...d.mapa.map((r) => el("tr", {}, ...cols.map(([c2, , casas]) => el("td", {}, casas === undefined || r[c2] === null ? r[c2] ?? "--" : n(r[c2], casas)))))));
    $("#ind-tabela-nota").textContent = `${d.mapa.length} distritos (workspace.gs.ouro_mvp_mapa), ordenados por número de chamados.`;
    dados = d;
    desenharMapa();
  }

  // mapa por distrito: círculo no centro dos chamados, área proporcional à taxa por 100 mil habitantes
  let dados = null, mapa = null;
  function desenharMapa() {
    if (!dados || mapa || tela.hidden || typeof L === "undefined") return;
    mapa = L.map("ind-mapa", { scrollWheelZoom: false }).setView([-23.6, -46.62], 10);
    camadaOSM().addTo(mapa);
    const pontos = dados.mapa.filter((r) => r.lat !== null && r.lon !== null);
    const maxTaxa = Math.max(...pontos.map((r) => r.chamados_por_100mil_hab));
    pontos.sort((a, b) => b.chamados_por_100mil_hab - a.chamados_por_100mil_hab).forEach((r) => {
      L.circleMarker([r.lat, r.lon], {
        radius: 4 + 16 * Math.sqrt(r.chamados_por_100mil_hab / maxTaxa), color: "#0d1426", weight: 1,
        fillColor: COR[r.zona] || "#5f80cc", fillOpacity: 0.78,
      }).bindTooltip(`<strong>${r.distrito}</strong> (${r.zona})<br>${n(r.chamados)} chamados · ${n(r.chamados_por_100mil_hab, 1)} por 100 mil hab.`
        + (r.tempo_medio_dias !== null ? `<br>${n(r.tempo_medio_dias, 1)} dias até fechar` : "")).addTo(mapa);
    });
    if (pontos.length) mapa.fitBounds(pontos.map((r) => [r.lat, r.lon]), { padding: [20, 20] });
  }

  /* ---------------------------------------------------------------- o Vésper agora (central ao vivo) */
  const ROT_ORIGEM = { cidadao: "Foto", video: "Vídeo ao vivo", robo: "Robô", relato: "Relato", "robo+foto": "Robô + foto" };
  const ROT_PRIO = { alta: "Alta", media: "Média", baixa: "Baixa", nenhuma: "Sem prioridade" };
  const ROT_STATUS = { suspeita: "Suspeita", recebido: "Recebido", confirmado: "Confirmado", encaminhado: "Encaminhado",
    em_reparo: "Em reparo", resolvido: "Resolvido", recusado: "Recusado" };
  function contar(lista, chave, rotulos) {
    const m = new Map();
    lista.forEach((c) => { const k = chave(c); m.set(k, (m.get(k) || 0) + 1); });
    return [...m].sort((a, b) => b[1] - a[1]).map(([k, v]) => el("li", { class: `v-${k}` }, el("span", {}, rotulos[k] || k), el("b", {}, n(v))));
  }
  async function aoVivo() {
    try {
      const r = await fetch("/v1/chamados?limite=300");
      if (!r.ok) throw new Error(`erro ${r.status}`);
      const todos = await r.json();
      $("#viv-total").textContent = n(todos.length);
      $("#viv-origem").replaceChildren(...contar(todos, (c) => (c.evidencia === "video" ? "video" : c.origem), ROT_ORIGEM));
      $("#viv-prio").replaceChildren(...contar(todos, (c) => c.nivel || "nenhuma", ROT_PRIO));
      $("#viv-status").replaceChildren(...contar(todos, (c) => c.status, ROT_STATUS));
      $("#viv-hora").textContent = `central de chamados ao vivo · ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`;
    } catch (e) {
      $("#viv-hora").textContent = `central indisponível: ${e.message}`;
    }
  }
  setInterval(() => { if (!tela.hidden && !document.hidden) aoVivo(); }, 15000);

  new MutationObserver(() => { if (!tela.hidden) { abrir(); aoVivo(); desenharMapa(); mapa?.invalidateSize(); } }).observe(tela, { attributes: true, attributeFilter: ["hidden"] });
  if (!tela.hidden) { abrir(); aoVivo(); }
})();
