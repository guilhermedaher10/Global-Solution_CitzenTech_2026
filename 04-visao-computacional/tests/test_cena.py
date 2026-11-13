"""Análise de cena: a região está no escuro? (não só "tem poste apagado?")."""
import cv2
import numpy as np

from conftest import DetectorFalso, cena, jpeg
from visao.cena import analisar_cena
from visao.pipeline import analisar_bytes
from visao.schemas import NivelLuz, TipoChamado


def _noite_com_luzes(n_luzes=6, base=18):
    img = cena(base)
    rng = np.random.default_rng(3)
    for _ in range(n_luzes):  # janelas, postes, letreiros
        x, y = int(rng.integers(20, 600)), int(rng.integers(20, 400))
        cv2.circle(img, (x, y), 9, (250, 250, 240), -1)
    return img


def test_rua_bem_iluminada():
    c = analisar_cena(cena(150))
    assert c.nivel == NivelLuz.iluminada and c.indice_escuridao < 30 and not c.possivel_apagao


def test_breu_sem_nenhuma_luz_e_possivel_apagao():
    c = analisar_cena(cena(12))
    assert c.nivel == NivelLuz.breu and c.fontes_de_luz == 0 and c.possivel_apagao
    assert any("falta de energia" in m for m in c.motivos)


def test_noite_escura_com_janelas_acesas_nao_e_apagao():
    c = analisar_cena(_noite_com_luzes())
    assert c.fontes_de_luz >= 3 and not c.possivel_apagao       # tem energia na região: é a rua que está escura
    assert c.nivel in (NivelLuz.muito_escura, NivelLuz.breu)


def test_grade_de_luz_mostra_onde_ha_luz():
    img = cena(15)
    img[:, 400:] = 200                                           # metade direita iluminada
    g = analisar_cena(img).grade_luz
    assert len(g) == 6 and len(g[0]) == 8
    assert g[3][7] > 150 and g[3][0] < 40


def test_apagao_entra_na_prioridade_e_no_setor():
    a = analisar_bytes(jpeg(cena(12)), DetectorFalso([]), origem="cidadao")
    assert a.cena.possivel_apagao
    assert TipoChamado.falta_de_energia in a.fusao.tipos_chamado
    assert any("possível apagão" in f for f in a.prioridade.fatores)


def test_poste_aceso_contra_o_ceu_sem_deteccao_nao_vira_chamado_por_escuridao():
    # foto apontada para cima: céu escuro + uma lâmpada forte. Há fonte de luz: não é "região no escuro".
    img = cena(14)
    cv2.circle(img, (320, 200), 40, (255, 255, 255), -1)
    a = analisar_bytes(jpeg(img), DetectorFalso([]), origem="cidadao")
    assert a.cena.fontes_de_luz >= 1 and not a.cena.possivel_apagao
