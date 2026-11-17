/* Vésper · aba Indicadores: a camada Ouro do Big Data (pasta 02) dentro do MVP.
 * Lê GET /v1/indicadores (gerado da Ouro do Databricks por scripts/exportar_ouro_web.py) e desenha
 * KPIs, Centro × Periferia, top distritos, evolução por mês e a linhagem Bronze → Prata → Ouro.
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
    const total = d.camadas.prata_sp156, t = d.tempo_conserto;
    const validos = d.validos.find((v) => v.tipo === "valido") || { chamados: 0, pct: 0 };
    $("#ind-total").textContent = n(total);
    $("#ind-total-sub").textContent = `${d.periodo} · ${n(d.camadas.distritos)} distritos`;
    $("#ind-tempo").textContent = `${n(t.media_dias, 1)} dias`;
    $("#ind-tempo-sub").textContent = `mediana de ${n(t.mediana_dias, 0)} dia: a média é puxada pelos casos lentos`;
    $("#ind-final").textContent = `${n((100 * t.finalizados) / total, 0)}%`;
    $("#ind-final-sub").textContent = `${n(t.finalizados)} chamados finalizados`;
    $("#ind-validos").textContent = `${n(validos.pct, 1)}%`;
    $("#ind-validos-sub").textContent = `${n(validos.chamados)} com distrito e data; o resto foi descartado na Ouro`;

    // Centro × Periferia (uma medida, duas zonas)
    const zonas = d.impacto_zona, maxZ = Math.max(...zonas.map((z) => z.chamados_por_mil_hab));
    $("#ind-zonas").replaceChildren(...zonas.map((z) => el("div", {
      class: "linha-zona", title: `${z.zona}: ${n(z.chamados)} chamados · ${n(z.populacao)} habitantes · ${n(z.chamados_por_mil_hab, 2)} por mil`,
    }, el("span", { class: "nome" }, z.zona),
      el("span", { class: "trilho" }, el("i", { style: `width:${(100 * z.chamados_por_mil_hab) / maxZ}%;background:${COR[z.zona] || "#5f80cc"}` })),
      el("b", {}, n(z.chamados_por_mil_hab, 1)),
      el("small", {}, `${n(z.chamados)} chamados · ${n(z.populacao)} hab.`))));
    const c = zonas.find((z) => z.zona === "Centro"), p = zonas.find((z) => z.zona === "Periferia");
    if (c && p) $("#ind-impacto-txt").replaceChildren("O Centro registra ", el("strong", {}, `${n(c.chamados_por_mil_hab / p.chamados_por_mil_hab, 1)}× mais`),
      " chamados por mil moradores que a Periferia. A Periferia soma mais chamados no total (",
      el("strong", {}, n(p.chamados)), "), mas espalhados por muito mais gente.");

    // top distritos (barras horizontais, cor = zona, legenda + valor direto)
    $("#ind-legenda").replaceChildren(...Object.entries(COR).map(([z, cor]) => el("span", {}, el("i", { style: `background:${cor}` }), z)));
    const top = d.top_distritos, maxT = Math.max(...top.map((x) => x.chamados));
    $("#ind-top").replaceChildren(...top.map((x) => el("li", { title: `${x.distrito} (${x.zona}): ${n(x.chamados)} chamados` },
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

    // linhagem e qualidade
    const k = d.camadas;
    $("#ind-camadas").replaceChildren(
      el("li", { class: "bronze" }, el("strong", {}, "Bronze"), el("span", {}, `${n(k.bronze_sp156)} linhas brutas do SP156 + clima + IBGE (Airflow)`)),
      el("li", { class: "prata" }, el("strong", {}, "Prata"), el("span", {}, `${n(k.prata_sp156)} chamados limpos, tipados e sem duplicatas (MERGE)`)),
      el("li", { class: "ouro" }, el("strong", {}, "Ouro"), el("span", {}, `fato com ${n(k.fato_chamado)} chamados + dimensões de local e tempo → ${n(k.distritos)} distritos`)));
    $("#ind-qualidade").replaceChildren(...d.qualidade.map((q) => {
      const pct = (100 * q.ok) / (q.ok + q.falha);
      return el("li", { title: `${n(q.ok)} ok · ${n(q.falha)} com falha` }, el("span", {}, q.regra), el("b", {}, `${n(pct, 1)}% ok`));
    }));
    $("#ind-origem").textContent = `Fonte: ${d.fonte}. ${d.completo ? "Exportação completa da Ouro." : "Valores do notebook executado no Databricks."}`;

    // tabela da Ouro
    const cols = [["distrito", "Distrito"], ["zona", "Zona"], ["populacao", "População", 0], ["chamados", "Chamados", 0],
      ["chamados_por_mil_hab", "Por mil hab.", 1], ["tempo_medio_dias", "Dias até o conserto", 1], ["pct_finalizado", "% finalizado", 1]];
    $("#ind-tabela").replaceChildren(
      el("thead", {}, el("tr", {}, ...cols.map(([, t]) => el("th", { scope: "col" }, t)))),
      el("tbody", {}, ...d.mapa.map((r) => el("tr", {}, ...cols.map(([c2, , casas]) => el("td", {}, casas === undefined || r[c2] === null ? r[c2] ?? "--" : n(r[c2], casas)))))));
    $("#ind-tabela-nota").textContent = d.completo
      ? `${d.mapa.length} distritos (workspace.gs.ouro_mvp_mapa).`
      : `As ${d.mapa.length} primeiras linhas, como o notebook mostra; a tabela completa tem ${n(k.distritos)} distritos.`;
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

  new MutationObserver(() => { if (!tela.hidden) { abrir(); aoVivo(); } }).observe(tela, { attributes: true, attributeFilter: ["hidden"] });
  if (!tela.hidden) { abrir(); aoVivo(); }
})();
