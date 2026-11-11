from datetime import date

from src import regras

HOJE = date(2026, 11, 9)


def ocorrencia(**kw) -> dict:
    base = {
        "id": "T-1", "poste_id": "P-101", "latitude": "-23.55", "longitude": "-46.63",
        "foto": "fotos/P-101.jpg", "confianca_ia": "0.90", "severidade": "moderada",
        "escola_proxima": "0", "ponto_onibus_proximo": "0", "status": "PENDENTE",
    }
    base.update(kw)
    return base


def test_sucesso_normal(cfg):
    d = regras.avaliar(ocorrencia(), [], HOJE, cfg)
    assert (d.acao, d.prioridade) == (regras.ENVIAR, "NORMAL")


def test_urgente_por_escola(cfg):
    d = regras.avaliar(ocorrencia(escola_proxima="1"), [], HOJE, cfg)
    assert (d.acao, d.prioridade) == (regras.ENVIAR, "URGENTE")


def test_urgente_por_ponto_de_onibus(cfg):
    d = regras.avaliar(ocorrencia(ponto_onibus_proximo="1"), [], HOJE, cfg)
    assert d.prioridade == "URGENTE"


def test_urgente_por_escuridao_severa(cfg):
    d = regras.avaliar(ocorrencia(severidade="severa"), [], HOJE, cfg)
    assert d.prioridade == "URGENTE"


def test_falha_sem_coordenada(cfg):
    d = regras.avaliar(ocorrencia(latitude="", longitude=""), [], HOJE, cfg)
    assert d.acao == regras.FALHA_DADOS
    assert "latitude ausente" in d.motivo


def test_falha_coordenada_fora_do_intervalo(cfg):
    d = regras.avaliar(ocorrencia(latitude="123"), [], HOJE, cfg)
    assert d.acao == regras.FALHA_DADOS


def test_falha_foto_inexistente(cfg):
    d = regras.avaliar(ocorrencia(foto="fotos/nao_existe.jpg"), [], HOJE, cfg)
    assert d.acao == regras.FALHA_DADOS


def test_duplicado_dentro_da_janela(cfg):
    anterior = ocorrencia(id="T-0", status="ENVIADO", data_envio="2026-10-25")
    d = regras.avaliar(ocorrencia(), [anterior], HOJE, cfg)
    assert d.acao == regras.DESCARTAR_DUPLICADO


def test_nao_duplicado_fora_da_janela(cfg):
    anterior = ocorrencia(id="T-0", status="ENVIADO", data_envio="2026-09-01")
    d = regras.avaliar(ocorrencia(), [anterior], HOJE, cfg)
    assert d.acao == regras.ENVIAR


def test_revisao_humana_por_baixa_confianca(cfg):
    d = regras.avaliar(ocorrencia(confianca_ia="0.55"), [], HOJE, cfg)
    assert d.acao == regras.REVISAO_HUMANA


def test_aprovado_ignora_limiar(cfg):
    d = regras.avaliar(ocorrencia(confianca_ia="0.55", status="APROVADO"), [], HOJE, cfg)
    assert d.acao == regras.ENVIAR
