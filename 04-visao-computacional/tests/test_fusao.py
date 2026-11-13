"""Fusão sensor (robô: LDR + ultrassônico) + visão (foto)."""
from fastapi.testclient import TestClient

from conftest import DetectorFalso, cena, jpeg, poste
from visao.fusao import fundir, ler_sensores, triar_alerta
from visao.pipeline import analisar_bytes
from visao.schemas import AlertaRobo, Confirmacao, StatusTrecho, TipoAlerta, TipoChamado


# ---------------------------------------------------------------- leitura dos sensores
def test_alerta_explicito_e_deduzido_das_leituras():
    assert ler_sensores(alerta=["escuro"]).alertas == [TipoAlerta.escuro]
    s = ler_sensores(sensor_lux=2.0, sensor_distancia_cm=30)          # sem lista: deduz
    assert s.escuro and s.buraco and len(s.motivos) == 2
    assert ler_sensores(sensor_lux=50, sensor_distancia_cm=5).alertas == []
    assert ler_sensores(sensor_lux=1, alerta=["escuro"]).alertas == [TipoAlerta.escuro]  # sem duplicar


# ---------------------------------------------------------------- tipo de chamado
def _fundir(alertas, acesos=0, apagados=0, buracos=0, status=StatusTrecho.escura):
    return fundir(ler_sensores(alerta=alertas), acesos=acesos, apagados=apagados, buracos=buracos,
                  status=status)


def test_escuro_mais_poste_apagado_e_conserto_confirmado():
    f = _fundir(["escuro"], apagados=1)
    assert f.tipos_chamado == [TipoChamado.conserto_poste]
    assert f.confirmacao == Confirmacao.confirmado


def test_escuro_sem_poste_e_pedido_de_instalacao():
    f = _fundir(["escuro"])
    assert TipoChamado.instalacao_iluminacao in f.tipos_chamado
    assert f.confirmacao == Confirmacao.confirmado


def test_escuro_com_poste_aceso_e_poda():
    f = _fundir(["escuro"], acesos=2, status=StatusTrecho.iluminada)
    assert f.tipos_chamado == [TipoChamado.poda_ou_obstrucao]
    assert f.confirmacao == Confirmacao.nao_confirmado


def test_buraco_so_no_sensor_fica_como_suspeita():
    f = _fundir(["escuro", "buraco"], apagados=1)
    assert f.confirmacao == Confirmacao.parcial
    assert TipoChamado.buraco not in f.tipos_chamado


def test_buraco_confirmado_pela_foto():
    f = _fundir(["escuro", "buraco"], apagados=1, buracos=1)
    assert f.confirmacao == Confirmacao.confirmado
    assert set(f.tipos_chamado) == {TipoChamado.conserto_poste, TipoChamado.buraco}


def test_foto_invalida_nao_sugere_tipo_de_chamado():
    f = fundir(ler_sensores(alerta=["escuro"]), acesos=1, apagados=0, buracos=0,
               status=StatusTrecho.iluminada, foto_valida=False)
    assert f.tipos_chamado == [] and f.confirmacao == Confirmacao.nao_confirmado
    assert "continua aberta" in f.motivos[0]


def test_foto_de_cidadao_sem_sensor():
    assert _fundir([], apagados=1).confirmacao == Confirmacao.sem_sensor


# ---------------------------------------------------------------- pipeline completo
def test_pipeline_buraco_no_escuro_e_prioridade_maxima():
    det = DetectorFalso([poste("poste_apagado"), poste("buraco", bbox=(200, 400, 400, 500))])
    a = analisar_bytes(jpeg(cena(30)), det, origem="robo", sensor_lux=1.0, sensor_distancia_cm=25,
                       alerta=["escuro", "buraco"])
    assert a.resumo.buracos == 1
    assert a.fusao.confirmacao == Confirmacao.confirmado
    assert a.prioridade.pontuacao == 100 and a.prioridade.nivel.value == "alta"
    assert any("risco de queda" in f for f in a.prioridade.fatores)


def test_cidadao_sem_poste_vale_se_o_robo_marcou_escuro():
    a = analisar_bytes(jpeg(cena(30)), DetectorFalso([]), origem="cidadao", alerta=["escuro"])
    assert a.validacao.foto_valida and a.validacao.abrir_chamado
    assert TipoChamado.trecho_sem_luz in a.fusao.tipos_chamado        # região muito escura sem poste


# ---------------------------------------------------------------- alerta só de sensores
def test_triagem_do_alerta_sem_foto():
    r = triar_alerta(AlertaRobo(latitude=-23.55, longitude=-46.63, sensor_lux=3.2,
                                sensor_distancia_cm=12, alerta=["escuro", "buraco"]))
    assert r.status == "suspeita" and r.acao_robo.value == "led_vermelho"
    assert r.prioridade_previa.pontuacao == 85
    so_escuro = triar_alerta(AlertaRobo(latitude=-23.55, longitude=-46.63, sensor_lux=2))
    assert so_escuro.acao_robo.value == "led_amarelo" and so_escuro.alertas == [TipoAlerta.escuro]
    nada = triar_alerta(AlertaRobo(latitude=-23.55, longitude=-46.63, sensor_lux=80))
    assert nada.status == "descartado" and nada.acao_robo.value == "nenhuma"


def test_api_alerta_robo_funciona_sem_modelo():
    from api import main
    from test_pipeline_api import _sem_lifespan

    main._estado["detector"], main._estado["erro"] = None, "sem best.pt"
    main.app.router.lifespan_context = _sem_lifespan
    with TestClient(main.app) as c:
        r = c.post("/v1/alerta-robo", json={"origem": "robo", "latitude": -23.55, "longitude": -46.63,
                                             "sensor_lux": 3.2, "sensor_distancia_cm": 12,
                                             "alerta": ["escuro", "buraco"]})
        assert r.status_code == 200, r.text
        assert r.json()["acao_robo"] == "led_vermelho"
        assert c.post("/v1/alerta-robo", json={"latitude": 200, "longitude": 0}).status_code == 422
        assert c.post("/v1/alerta-robo", json={"latitude": 0, "longitude": 0,
                                                "alerta": ["fogo"]}).status_code == 422


def test_api_analisar_com_campos_do_robo():
    from api import main
    from test_pipeline_api import _sem_lifespan

    main._estado["detector"], main._estado["erro"] = DetectorFalso([poste("poste_apagado")]), None
    main.app.router.lifespan_context = _sem_lifespan
    with TestClient(main.app) as c:
        arq = {"imagem": ("rua.jpg", jpeg(cena(30)), "image/jpeg")}
        r = c.post("/v1/analisar", files=arq, data={"origem": "robo", "sensor_distancia_cm": "20",
                                                    "alerta": "escuro,buraco"})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["sensor_distancia_cm"] == 20
        assert j["fusao"]["confirmacao"] == "parcial"     # escuro confirmado, buraco não aparece
        r = c.post("/v1/analisar", files=arq, data={"alerta": "fogo"})
        assert r.status_code == 422
