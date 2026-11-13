"""Front do MVP servido pela própria API (mesma URL pública)."""
import pytest
from fastapi.testclient import TestClient

from conftest import DetectorFalso, poste


@pytest.fixture
def cliente():
    from api import main
    from test_pipeline_api import _sem_lifespan

    main._estado.update(detector=DetectorFalso([poste("poste_apagado")]), erro=None)
    main.app.router.lifespan_context = _sem_lifespan
    with TestClient(main.app) as c:
        yield c


def test_pagina_inicial_e_estaticos(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "Vésper" in r.text and 'id="tela-reportar"' in r.text and "/static/app.js" in r.text
    for arquivo in ("/static/app.js", "/static/app.css", "/static/icone.svg", "/static/vendor/leaflet/leaflet.js",
                    "/static/fontes/inter-latin-400-normal.woff2"):
        assert cliente.get(arquivo).status_code == 200, arquivo


def test_cabecalhos_de_seguranca_na_pagina(cliente):
    h = cliente.get("/").headers
    assert "script-src 'self'" in h["content-security-policy"]
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert "https://nominatim.openstreetmap.org" in h["content-security-policy"]
    assert h["x-content-type-options"] == "nosniff"
    assert "geolocation=(self)" in h["permissions-policy"]


def test_docs_continua_funcionando_sem_csp(cliente):
    r = cliente.get("/docs")
    assert r.status_code == 200 and "content-security-policy" not in r.headers
    assert "/" not in cliente.get("/openapi.json").json()["paths"]
