"""Contrato 1.3: breu como evidência, filtro de sanidade das caixas, endereço e relato sem foto."""
import pytest
from fastapi.testclient import TestClient

from conftest import DetectorFalso, cena, jpeg, poste
from visao.pipeline import analisar_bytes
from visao.schemas import TipoChamado


def test_breu_sem_poste_visivel_vira_evidencia_de_trecho_sem_luz():
    a = analisar_bytes(jpeg(cena(12)), DetectorFalso([]), origem="cidadao")
    assert a.validacao.foto_valida and a.validacao.abrir_chamado
    assert a.fusao.tipos_chamado == [TipoChamado.trecho_sem_luz]
    assert any("breu" in m for m in a.validacao.motivos)


def test_noite_comum_sem_poste_continua_pedindo_para_enquadrar():
    a = analisar_bytes(jpeg(cena(40)), DetectorFalso([]), origem="cidadao")   # escuro, mas não breu
    assert not a.validacao.foto_valida
    assert any("enquadre" in m for m in a.validacao.motivos)


def test_foto_preta_sem_nada_nao_passa():
    a = analisar_bytes(jpeg(cena(3, textura=False)), DetectorFalso([]), origem="cidadao")
    assert not a.validacao.foto_valida                       # sem nitidez: celular no bolso


def test_caixa_do_tamanho_da_foto_e_descartada():
    gigante = poste("poste_apagado", bbox=(0, 0, 640, 600))   # defeito do modelo-base
    real = poste("poste_apagado", bbox=(300, 40, 340, 290))
    a = analisar_bytes(jpeg(cena(30)), DetectorFalso([gigante, real]), origem="cidadao")
    assert a.resumo.postes_apagados == 1 and a.deteccoes[0].bbox == [300, 40, 340, 290]


def test_endereco_vai_junto_com_a_localizacao():
    a = analisar_bytes(jpeg(cena(30)), DetectorFalso([poste("poste_apagado")]), latitude=-23.56, longitude=-46.65,
                       endereco="  Av. Paulista, 1578 - São Paulo  ")
    assert a.localizacao.endereco == "Av. Paulista, 1578 - São Paulo"


@pytest.fixture
def cliente():
    from api import main
    from test_pipeline_api import _sem_lifespan

    main._estado.update(detector=None, erro="sem modelo")   # relato funciona mesmo sem o YOLO
    main.app.router.lifespan_context = _sem_lifespan
    with TestClient(main.app) as c:
        yield c


def test_relato_sem_foto_vira_suspeita(cliente):
    r = cliente.post("/v1/relatos", json={"latitude": -23.5614, "longitude": -46.6559,
                                          "endereco": "Av. Paulista, 1578", "problema": ["escuro", "buraco"]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "suspeita" and j["prioridade_previa"]["nivel"] == "alta"
    assert j["localizacao"]["endereco"] == "Av. Paulista, 1578"
    assert "envie uma foto" in j["proximo_passo"]


def test_relato_valida_entrada(cliente):
    assert cliente.post("/v1/relatos", json={"latitude": 200, "longitude": 0}).status_code == 422
    assert cliente.post("/v1/relatos", json={"latitude": 0, "longitude": 0, "problema": []}).status_code == 422
    assert cliente.post("/v1/relatos", json={"latitude": 0, "longitude": 0, "endereco": "x" * 201}).status_code == 422


def test_relato_aparece_nas_metricas(cliente):
    cliente.post("/v1/relatos", json={"latitude": -23.5, "longitude": -46.6})
    assert 'visao_relatos_total{status="suspeita"}' in cliente.get("/metrics").text
