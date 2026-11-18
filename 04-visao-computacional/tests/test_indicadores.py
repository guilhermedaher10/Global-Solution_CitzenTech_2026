"""Aba Indicadores: o site mostra a camada Ouro do Big Data (pasta 02), sem dado pessoal."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

JSON_WEB = Path(__file__).resolve().parents[1] / "web" / "ouro-bigdata.json"


@pytest.fixture
def cliente():
    from api import main
    from test_pipeline_api import _sem_lifespan

    main.app.router.lifespan_context = _sem_lifespan
    with TestClient(main.app) as c:
        yield c


def test_json_do_site_igual_ao_big_data():
    from scripts.exportar_ouro_web import NOTEBOOK, gerar
    if not NOTEBOOK.exists():
        pytest.skip("pasta 02-big-data ausente")
    assert json.loads(JSON_WEB.read_text(encoding="utf-8")) == gerar(), "rode: python scripts/exportar_ouro_web.py"


def test_rota_indicadores(cliente):
    r = cliente.get("/v1/indicadores")
    assert r.status_code == 200
    d = r.json()
    assert d["camadas"]["prata_sp156"] > 0 and d["camadas"]["distritos"] > 0
    zonas = {z["zona"]: z for z in d["impacto_zona"]}
    assert set(zonas) == {"Centro", "Periferia"}
    assert all(z["chamados_por_mil_hab"] > 0 for z in zonas.values())
    assert d["top_distritos"] and {"distrito", "zona", "chamados"} <= set(d["top_distritos"][0])
    # LGPD: só agregados, nenhum campo de endereço ou pessoa
    texto = json.dumps(d).lower()
    assert "logradouro" not in texto and "endereco" not in texto and "cep" not in texto
