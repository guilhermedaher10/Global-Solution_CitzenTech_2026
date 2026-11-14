from src import regras


def chamado(**kw) -> dict:
    base = {
        "id_captura": "T-1", "latitude": "-23.55", "longitude": "-46.63",
        "foto": "fotos/C-001.jpg", "prioridade_nivel": "alta", "prioridade_pontuacao": "90",
        "tipos_chamado": "conserto_poste",
    }
    base.update(kw)
    return base


def test_dados_validos(cfg):
    assert regras.avaliar(chamado(), cfg).acao == regras.ENVIAR


def test_falha_sem_coordenada(cfg):
    d = regras.avaliar(chamado(latitude="", longitude=""), cfg)
    assert d.acao == regras.FALHA_DADOS
    assert "latitude ausente" in d.motivo and "longitude ausente" in d.motivo


def test_falha_coordenada_fora_do_intervalo(cfg):
    assert regras.avaliar(chamado(latitude="123"), cfg).acao == regras.FALHA_DADOS


def test_falha_coordenada_nao_numerica(cfg):
    assert regras.avaliar(chamado(longitude="abc"), cfg).acao == regras.FALHA_DADOS


def test_falha_foto_ausente(cfg):
    d = regras.avaliar(chamado(foto=""), cfg)
    assert d.acao == regras.FALHA_DADOS and "foto ausente" in d.motivo


def test_falha_foto_inexistente(cfg):
    d = regras.avaliar(chamado(foto="fotos/nao_existe.jpg"), cfg)
    assert d.acao == regras.FALHA_DADOS and "nao encontrado" in d.motivo


def test_falha_foto_fora_da_pasta_de_dados(cfg):
    d = regras.avaliar(chamado(foto="../fora.jpg"), cfg)
    assert d.acao == regras.FALHA_DADOS and "fora da pasta" in d.motivo


def test_falha_nivel_de_prioridade_invalido(cfg):
    assert regras.avaliar(chamado(prioridade_nivel="urgentissima"), cfg).acao == regras.FALHA_DADOS
    assert regras.avaliar(chamado(prioridade_nivel=""), cfg).acao == regras.FALHA_DADOS


def test_falha_pontuacao_invalida(cfg):
    assert regras.avaliar(chamado(prioridade_pontuacao="muito"), cfg).acao == regras.FALHA_DADOS


def test_falha_id_com_caminho(cfg):
    # id_captura vira nome de arquivo (PDF, e-mail): nao pode carregar "../"
    assert regras.avaliar(chamado(id_captura="../x"), cfg).acao == regras.FALHA_DADOS
    assert regras.avaliar(chamado(id_captura=""), cfg).acao == regras.FALHA_DADOS


def test_tipos_sem_informacao_valem_geral():
    assert regras.tipos({"tipos_chamado": ""}) == {"geral"}
    assert regras.tipos({"tipos_chamado": "conserto_poste|buraco"}) == {"conserto_poste", "buraco"}


def test_pontuacao_em_branco_vale_zero():
    assert regras.pontuacao({"prioridade_pontuacao": ""}) == 0
    assert regras.pontuacao({"prioridade_pontuacao": "87.0"}) == 87
