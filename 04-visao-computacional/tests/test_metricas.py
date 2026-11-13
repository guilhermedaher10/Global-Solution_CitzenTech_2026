"""GET /metrics: as 4 métricas de ouro + as do produto, e o token que protege o endpoint na nuvem."""
import re

import pytest
from fastapi.testclient import TestClient

from conftest import DetectorFalso, cena, jpeg, poste


@pytest.fixture
def cliente(monkeypatch):
    from api import main
    from test_pipeline_api import _sem_lifespan

    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    main._estado.update(detector=DetectorFalso([poste("poste_apagado")]), erro=None)
    main.app.router.lifespan_context = _sem_lifespan
    with TestClient(main.app) as c:
        yield c


def _valor(texto: str, serie: str) -> float:
    """Lê o valor de uma série no formato texto do Prometheus (0 se não existir)."""
    m = re.search(rf"^{re.escape(serie)} ([0-9.e+-]+)$", texto, re.M)
    return float(m.group(1)) if m else 0.0


def test_metricas_de_ouro_e_do_produto(cliente):
    antes = cliente.get("/metrics").text
    chamados_antes = _valor(antes, 'visao_chamados_total{prioridade="alta",tipo="conserto_poste"}')

    r = cliente.post("/v1/analisar", files={"imagem": ("rua.jpg", jpeg(cena(30)), "image/jpeg")},
                     data={"origem": "robo", "sensor_lux": "1"})
    assert r.status_code == 200 and r.json()["prioridade"]["nivel"] == "alta"
    cliente.post("/v1/alerta-robo", json={"latitude": -23.5, "longitude": -46.6, "sensor_lux": 1})

    m = cliente.get("/metrics")
    assert m.status_code == 200 and m.headers["content-type"].startswith("text/plain")
    t = m.text
    # tráfego/erros (rota pelo molde, nunca a URL crua) e latência
    assert 'http_requisicoes_total{metodo="POST",rota="/v1/analisar",status="200"}' in t
    assert 'http_duracao_segundos_bucket{le="0.5",rota="/v1/analisar"}' in t
    assert "http_requisicoes_em_andamento" in t
    # produto
    assert _valor(t, 'visao_chamados_total{prioridade="alta",tipo="conserto_poste"}') == chamados_antes + 1
    assert 'visao_alertas_robo_total{acao="led_amarelo",status="suspeita"}' in t
    assert _valor(t, "visao_modelo_carregado") == 1.0
    # o próprio /metrics não polui o tráfego do produto
    assert 'rota="/metrics"' not in t


def test_modelo_nao_carregado_aparece_no_gauge(cliente):
    from api import main

    main._estado["detector"] = None
    assert _valor(cliente.get("/metrics").text, "visao_modelo_carregado") == 0.0


def test_token_protege_o_metrics(cliente, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "segredo-de-teste")
    assert cliente.get("/metrics").status_code == 401
    assert cliente.get("/metrics", headers={"Authorization": "Bearer errado"}).status_code == 401
    assert cliente.get("/metrics", headers={"Authorization": "Bearer segredo-de-teste"}).status_code == 200


def test_metrics_fora_da_documentacao(cliente):
    assert "/metrics" not in cliente.get("/openapi.json").json()["paths"]
