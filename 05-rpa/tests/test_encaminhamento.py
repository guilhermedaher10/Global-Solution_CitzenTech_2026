"""Encaminhamento dos tipos que a Visão passou a emitir depois do contrato v1.1."""
from src import chamado
from src.config import SETOR_PADRAO


def _o(tipos: str) -> dict:
    return {"tipos_chamado": tipos}


def test_falta_de_energia_vai_para_a_distribuidora_e_nao_para_a_zeladoria():
    setores = chamado.setores(_o("falta_de_energia"))
    assert setores != [SETOR_PADRAO]
    assert "Enel" in setores[0] and "0800 72 72 196" in setores[0] and "Defesa Civil" in setores[0]


def test_trecho_sem_luz_vai_para_a_iluminacao_publica():
    assert chamado.setores(_o("trecho_sem_luz"))[0].startswith("Iluminação pública")


def test_apagao_com_trecho_escuro_tem_os_dois_setores_e_os_dois_fundamentos():
    o = _o("falta_de_energia|trecho_sem_luz")
    assert len(chamado.setores(o)) == 2 and SETOR_PADRAO not in chamado.setores(o)
    texto = chamado.fundamento(o)
    assert "art. 21, XII, b" in texto and "art. 149-A" in texto


def test_tipo_desconhecido_continua_na_zeladoria_geral():
    assert chamado.setores(_o("pichacao")) == [SETOR_PADRAO]
