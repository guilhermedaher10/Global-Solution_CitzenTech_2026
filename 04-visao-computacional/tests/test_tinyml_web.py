"""A aba Robô roda a MESMA IA do carrinho do Maker Lab (07): o JSON do site segue o firmware."""
import json
import math
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
JSON_WEB = RAIZ / "web" / "tinyml-carrinho.json"


def _prever(m, x):
    z = [(x[i] - m["media"][i]) / m["escala"][i] for i in range(4)]
    h = [max(0.0, m["b1"][j] + sum(z[i] * m["w1"][i][j] for i in range(4))) for j in range(12)]
    lg = [m["b2"][k] + sum(h[j] * m["w2"][j][k] for j in range(12)) for k in range(4)]
    e = [math.exp(v - max(lg)) for v in lg]
    return [v / sum(e) for v in e]


def test_json_do_site_igual_ao_firmware():
    from scripts.exportar_tinyml_web import CABECALHO, ler_cabecalho
    if not CABECALHO.exists():
        pytest.skip("pasta 07-maker-lab ausente")
    assert json.loads(JSON_WEB.read_text(encoding="utf-8")) == ler_cabecalho(), \
        "rode: python scripts/exportar_tinyml_web.py"


def test_ia_do_carrinho_classifica_cenas_da_patrulha():
    m = json.loads(JSON_WEB.read_text(encoding="utf-8"))
    casos = {  # [média, mínimo, desvio, fração escura] de uma janela de 10 leituras
        "claro_livre": [300, 299, 0.5, 0.0], "escuro_livre": [300, 299, 0.5, 1.0],
        "claro_obstaculo": [18, 17, 0.8, 0.0], "escuro_obstaculo": [18, 17, 0.8, 1.0],
    }
    for esperado, x in casos.items():
        p = _prever(m, x)
        assert m["classes"][max(range(4), key=p.__getitem__)] == esperado
        assert max(p) >= m["escore_min"]
