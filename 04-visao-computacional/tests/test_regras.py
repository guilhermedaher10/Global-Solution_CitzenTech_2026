from visao.config import normalizar_classe
from visao.regras import classificar_trecho, priorizar, validar
from visao.schemas import NivelPrioridade, StatusTrecho


def test_aliases_de_datasets_publicos():
    assert normalizar_classe("OFF") == "poste_apagado"
    assert normalizar_classe(" street light off ") == "poste_apagado"
    assert normalizar_classe("on") == "poste_aceso"
    assert normalizar_classe("car") is None


def test_trecho():
    assert classificar_trecho(3, 0, 90) == StatusTrecho.iluminada
    assert classificar_trecho(3, 1, 90) == StatusTrecho.parcial
    assert classificar_trecho(1, 1, 90) == StatusTrecho.escura          # metade apagada
    assert classificar_trecho(3, 1, 20) == StatusTrecho.escura          # cena escura + apagado
    assert classificar_trecho(0, 0, 20) == StatusTrecho.escura
    assert classificar_trecho(0, 0, 90) == StatusTrecho.sem_postes_visiveis


def _validar(**kw):
    base = dict(origem="cidadao", acesos=0, apagados=1, luminosidade=30, nitidez=50,
                lado_menor=640, status=StatusTrecho.escura, sensor_lux=None)
    base.update(kw)
    return validar(**base)


def test_foto_boa_abre_chamado():
    v = _validar()
    assert v.foto_valida and v.falha_detectada and v.abrir_chamado


def test_foto_de_dia_nao_vale():
    v = _validar(luminosidade=180)
    assert not v.foto_valida and not v.abrir_chamado
    assert any("dia" in m for m in v.motivos)


def test_cidadao_precisa_mostrar_poste_mas_robo_nao():
    assert not _validar(apagados=0, status=StatusTrecho.escura).foto_valida
    robo = _validar(origem="robo", apagados=0, status=StatusTrecho.escura, sensor_lux=1.0)
    assert robo.foto_valida and robo.abrir_chamado


def test_tudo_aceso_nao_abre_chamado():
    v = _validar(acesos=3, apagados=0, luminosidade=90, status=StatusTrecho.iluminada)
    assert v.foto_valida and not v.falha_detectada and not v.abrir_chamado


def test_foto_pequena_ou_tremida():
    assert not _validar(lado_menor=200).foto_valida
    assert not _validar(nitidez=1).foto_valida


def test_prioridade_explicavel():
    p = priorizar(apagados=2, status=StatusTrecho.escura, sensor_lux=1.0, abrir_chamado=True)
    assert p.nivel == NivelPrioridade.alta and p.pontuacao == 100
    assert len(p.fatores) == 3
    baixa = priorizar(apagados=1, status=StatusTrecho.parcial, sensor_lux=None, abrir_chamado=True)
    assert baixa.nivel == NivelPrioridade.media and baixa.pontuacao == 40
    nada = priorizar(apagados=2, status=StatusTrecho.escura, sensor_lux=None, abrir_chamado=False)
    assert nada.nivel == NivelPrioridade.nenhuma and nada.pontuacao == 0
