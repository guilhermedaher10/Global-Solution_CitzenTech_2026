"""Leva a camada OURO do Big Data (pasta 02) para a aba Indicadores do site.

Fonte, em ordem de preferência:
  1. 02-big-data/ouro/ouro_mvp.json  - exportação completa da Ouro (ouro_mvp_mapa com os 96 distritos + resumo),
     quando o pipeline do Databricks gravar esse arquivo;
  2. os resultados SALVOS no notebook 02-big-data/databricks/gs_pipeline.ipynb (as 5 consultas da Ouro, as
     contagens das camadas e as regras de qualidade, exatamente como o Databricks imprimiu).

Grava web/ouro-bigdata.json, servido por GET /v1/indicadores. Rode de novo quando o Big Data mudar:

    python scripts/exportar_ouro_web.py

O teste tests/test_indicadores.py falha se o JSON do site ficar diferente do que este script gera.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BIGDATA = RAIZ.parent / "02-big-data"
NOTEBOOK = BIGDATA / "databricks" / "gs_pipeline.ipynb"
EXPORTACAO = BIGDATA / "ouro" / "ouro_mvp.json"
SAIDA = RAIZ / "web" / "ouro-bigdata.json"


def _num(v: str):
    v = v.strip()
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def _tabelas(texto: str) -> list[list[dict]]:
    """Lê as tabelas do DataFrame.show() do Spark (+---+ / |a|b|)."""
    tabelas, atual, cab = [], None, None
    for linha in texto.splitlines():
        if linha.startswith("|"):
            cels = [c.strip() for c in linha.strip().strip("|").split("|")]
            if cab is None:
                cab, atual = cels, []
            else:
                atual.append({k: _num(v) for k, v in zip(cab, cels)})
        elif linha.startswith("+") and cab is not None and atual:
            tabelas.append(atual)
            cab, atual = None, None
    return tabelas


def _saidas(nb: dict) -> list[tuple[str, str]]:
    out = []
    for c in nb["cells"]:
        if c["cell_type"] != "code":
            continue
        txt = "".join("".join(o.get("text", [])) or "".join(o.get("data", {}).get("text/plain", []))
                      for o in c.get("outputs", []))
        out.append(("".join(c["source"]).splitlines()[0] if c["source"] else "", txt))
    return out


def do_notebook(caminho: Path = NOTEBOOK) -> dict:
    nb = json.loads(caminho.read_text(encoding="utf-8"))
    celulas = _saidas(nb)

    def celula(prefixo: str) -> str:
        for titulo, txt in celulas:
            if titulo.startswith(prefixo):
                return txt
        raise ValueError(f"célula '{prefixo}' não encontrada no notebook")

    def inteiro(padrao: str, txt: str) -> int:
        m = re.search(padrao, txt)
        if not m:
            raise ValueError(f"não achei '{padrao}'")
        return int(m.group(1))

    prata = celula("# prata_sp156")
    qual = celula("# 3 regras de qualidade")
    fato = celula("# fato_chamado")
    regras = [{"regra": m.group(1).strip(), "ok": int(m.group(2)), "falha": int(m.group(3))}
              for m in re.finditer(r"R\d \| (.+?):\s+(\d+) ok \|\s+(\d+) falha", qual)]
    q2 = _tabelas(celula("# Q2"))[0][0]
    mvp = celula("# Bloco 7")
    return {
        "fonte": "Big Data (02) · Databricks workspace.gs · camada Ouro",
        "origem": "resultados salvos em 02-big-data/databricks/gs_pipeline.ipynb",
        "completo": False,
        "periodo": "SP156 · jul–set/2026",
        "camadas": {
            "bronze_sp156": inteiro(r"bronze_sp156 linhas:\s*(\d+)", prata),
            "prata_sp156": inteiro(r"prata_sp156\s+linhas:\s*(\d+)", prata),
            "fato_chamado": inteiro(r"linhas fato_chamado:\s*(\d+)", fato),
            "distritos": inteiro(r"ouro_mvp_mapa .*?:\s*(\d+) distritos", mvp),
        },
        "qualidade": regras,
        "top_distritos": _tabelas(celula("# Q1"))[0],
        "tempo_conserto": {"media_dias": q2["media_dias"], "mediana_dias": q2["mediana_dias"],
                           "finalizados": q2["finalizados"]},
        "por_mes": _tabelas(celula("# Q3"))[0],
        "validos": _tabelas(celula("# Q4"))[0],
        "impacto_zona": _tabelas(celula("# Q5"))[0],
        "mapa": _tabelas(mvp)[0],   # ouro_mvp_mapa: o notebook mostra só as 5 primeiras linhas
    }


def gerar() -> dict:
    if EXPORTACAO.exists():
        dados = json.loads(EXPORTACAO.read_text(encoding="utf-8"))
        base = do_notebook()
        base.update({"origem": "02-big-data/ouro/ouro_mvp.json (exportação da Ouro)", "completo": True,
                     "mapa": dados["mapa"]})
        return base
    return do_notebook()


if __name__ == "__main__":
    SAIDA.write_text(json.dumps(gerar(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"gravado {SAIDA.relative_to(RAIZ)}")
