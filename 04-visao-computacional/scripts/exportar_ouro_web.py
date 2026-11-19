"""Leva a camada OURO do Big Data (pasta 02) para a aba Indicadores do site.

Fontes (as duas são do Big Data, nada é digitado à mão):
  1. os resultados SALVOS no notebook 02-big-data/databricks/gs_pipeline.ipynb: escopo, prova do incremental da
     Bronze, regras da Prata e as 5 consultas da Ouro, exatamente como o Databricks exibiu;
  2. 02-big-data/amostras/ouro_mvp_mapa.json: a tabela ouro_mvp_mapa completa (1 linha por distrito, com o
     centro do distrito para o mapa), exportada pelo próprio notebook.

Grava web/ouro-bigdata.json, servido por GET /v1/indicadores. Rode de novo quando o Big Data mudar:

    python scripts/exportar_ouro_web.py

O teste tests/test_indicadores.py falha se o JSON do site ficar diferente do que este script gera.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BIGDATA = RAIZ.parent / "02-big-data"
NOTEBOOK = BIGDATA / "databricks" / "gs_pipeline.ipynb"
MAPA = BIGDATA / "amostras" / "ouro_mvp_mapa.json"
SAIDA = RAIZ / "web" / "ouro-bigdata.json"


def _num(v: str):
    v = v.strip()
    if v.lower() in ("null", "none", ""):
        return None
    for tipo in (int, float):
        try:
            return tipo(v)
        except ValueError:
            pass
    return v


class _Tabela(HTMLParser):
    """Lê a tabela HTML que o display() do Databricks salva no notebook."""

    def __init__(self):
        super().__init__()
        self.linhas, self._linha, self._cel = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._linha = []
        elif tag in ("td", "th") and self._linha is not None:
            self._cel = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cel is not None:
            self._linha.append(self._cel.strip())
            self._cel = None
        elif tag == "tr" and self._linha:
            self.linhas.append(self._linha)
            self._linha = None

    def handle_data(self, data):
        if self._cel is not None:
            self._cel += data


def _tabela_html(html: str) -> list[dict]:
    p = _Tabela()
    p.feed(html)
    cab, *linhas = p.linhas
    return [{k: _num(v) for k, v in zip(cab, l)} for l in linhas]


def _celulas(nb: dict) -> dict[str, tuple[str, list[list[dict]]]]:
    """Título (1ª linha do código) → (texto impresso, tabelas exibidas)."""
    out = {}
    for c in nb["cells"]:
        if c["cell_type"] != "code" or not c["source"]:
            continue
        texto, tabelas = "", []
        for o in c.get("outputs", []):
            texto += "".join(o.get("text", []))
            if "text/html" in o.get("data", {}):
                tabelas.append(_tabela_html("".join(o["data"]["text/html"])))
        out["".join(c["source"]).splitlines()[0]] = (texto, tabelas)
    return out


def do_notebook(caminho: Path = NOTEBOOK) -> dict:
    celulas = _celulas(json.loads(caminho.read_text(encoding="utf-8")))

    def celula(prefixo: str) -> tuple[str, list[list[dict]]]:
        for titulo, conteudo in celulas.items():
            if titulo.startswith(prefixo):
                return conteudo
        raise ValueError(f"célula '{prefixo}' não encontrada no notebook")

    def inteiro(padrao: str, txt: str) -> int:
        m = re.search(padrao, txt)
        if not m:
            raise ValueError(f"não achei '{padrao}'")
        return int(m.group(1))

    escopo = re.findall(r"'([^']+)'", celula("# CONFIG")[0])
    incremental = celula("# PROVA DO INCREMENTAL")[1][0]
    prata_txt, prata_tab = celula("# PRATA")
    fato_txt = celula("# OURO — dim_tempo")[0]
    mapa_txt = celula("# OURO_MVP_MAPA")[0]
    q2 = celula("# Q2")[1][0][0]
    bronze = max(l["linhas"] for l in incremental if l["tabela"] == "bronze_sp156")
    return {
        "fonte": "Big Data (02) · Databricks workspace.gs · camada Ouro",
        "origem": "02-big-data/databricks/gs_pipeline.ipynb + amostras/ouro_mvp_mapa.json",
        "periodo": "SP156 · jul–set/2026",
        "escopo": escopo,
        "camadas": {
            "bronze_sp156": bronze,
            "prata_sp156": inteiro(r"depois:\s*(\d+)", prata_txt),
            "fato_chamado": inteiro(r"fato_chamado \(escopo\):\s*(\d+)", fato_txt),
            "distritos": inteiro(r"ouro_mvp_mapa:\s*(\d+) distritos", mapa_txt),
        },
        "incremental": incremental,
        "qualidade": prata_tab[0],
        "top_distritos": celula("# Q1")[1][0],
        "tempo_conserto": {k: q2[k] for k in ("media_dias", "mediana_dias", "p90_dias", "finalizados")},
        "por_mes": celula("# Q3")[1][0],
        "validos": celula("# Q4")[1][0],
        "impacto_zona": celula("# Q5")[1][0],
    }


def gerar() -> dict:
    dados = do_notebook()
    mapa = json.loads(MAPA.read_text(encoding="utf-8"))
    dados["mapa"] = sorted(mapa, key=lambda r: (-r["chamados"], r["distrito"]))
    return dados


if __name__ == "__main__":
    SAIDA.write_text(json.dumps(gerar(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"gravado {SAIDA.relative_to(RAIZ)}")
