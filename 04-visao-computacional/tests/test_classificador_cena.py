"""Classificador de cena (YOLO26-cls) e a fusão com as medidas de luz."""
from pathlib import Path

import pytest

from conftest import DetectorFalso, cena
from visao import classificador_cena as cc
from visao.cena import analisar_cena
from visao.pipeline import analisar_imagem

MODELO = Path(__file__).resolve().parent.parent / "models" / "cena.pt"


def test_cena_iluminada_nunca_vira_apagao():
    c = analisar_cena(cena(150))                       # bem clara
    assert c.nivel.value == "iluminada"
    r = cc.fundir_cena(c, {"apagao": 0.9, "iluminada": 0.07, "trecho_escuro": 0.03})
    assert r.classe == "iluminada" and "luz medida" in r.motivo


def test_classificador_confiante_decide_e_indeciso_devolve_as_regras():
    c = analisar_cena(cena(20))                        # breu, sem fonte de luz: regras dizem apagão
    assert cc.classe_das_regras(c) == "apagao"
    assert cc.fundir_cena(c, {"apagao": 0.1, "iluminada": 0.1, "trecho_escuro": 0.8}).classe == "trecho_escuro"
    assert cc.fundir_cena(c, {"apagao": 0.4, "iluminada": 0.3, "trecho_escuro": 0.3}).classe == "apagao"
    assert cc.fundir_cena(c, None).fonte == "regras"


def test_pipeline_usa_a_leitura_fundida(monkeypatch):
    class Falso:
        def ler(self, img, c):
            return cc.fundir_cena(c, {"apagao": 0.92, "iluminada": 0.03, "trecho_escuro": 0.05})
    monkeypatch.setattr("visao.pipeline.classificador_padrao", lambda: Falso())
    a = analisar_imagem(cena(20), DetectorFalso())
    assert a.cena.classe == "apagao" and a.cena.possivel_apagao and a.cena.probabilidades["apagao"] == 0.92
    assert "falta_de_energia" in [t.value for t in a.fusao.tipos_chamado]


def test_sem_modelo_tudo_segue_pelas_regras():
    c = cc.ClassificadorCena("nao_existe.pt")
    assert not c.disponivel and c.ler(cena(20), analisar_cena(cena(20))).fonte == "regras"


@pytest.mark.skipif(not MODELO.exists(), reason="models/cena.pt não incluído")
def test_modelo_real_carrega_e_devolve_as_3_classes():
    pytest.importorskip("ultralytics")   # o CI de testes não instala o PyTorch (fica leve)
    c = cc.ClassificadorCena(str(MODELO))
    p = c.probabilidades(cena(30))
    assert set(p) == {"iluminada", "trecho_escuro", "apagao"} and abs(sum(p.values()) - 1) < 0.01


# ------------------------------------------------------------------ EXIF de exposição
def jpeg_com_exif(img, exposicao, abertura, iso, flash=0):
    import io
    import cv2
    from PIL import Image
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    exif = Image.Exif()
    ifd = exif.get_ifd(0x8769)
    ifd.update({33434: exposicao, 33437: abertura, 34855: iso, 37385: flash})
    buf = io.BytesIO()
    pil.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_ev100_le_o_exif():
    from visao.privacidade import ler_metadados
    m = ler_metadados(jpeg_com_exif(cena(20), 0.25, 1.8, 3200))     # 1/4 s, f/1.8, ISO 3200
    assert m.iso == 3200 and m.ev100 == -1.3    # log2(1,8²/0,25) - log2(3200/100): breu de verdade


def test_camera_subexposta_nao_vira_apagao():
    from visao.pipeline import analisar_bytes
    dados = jpeg_com_exif(cena(20), 1 / 2000, 8.0, 100)             # exposição de dia: EV ~17
    a = analisar_bytes(dados, DetectorFalso())
    assert a.cena.ev100 > 8 and not a.cena.possivel_apagao
    assert any("subexposta" in m for m in a.cena.motivos)


def test_escuro_de_verdade_fica_explicado():
    from visao.pipeline import analisar_bytes
    a = analisar_bytes(jpeg_com_exif(cena(20), 0.25, 1.8, 3200, flash=1), DetectorFalso())
    assert a.cena.possivel_apagao and any("escuro de verdade" in m for m in a.cena.motivos)
    assert any("flash" in m for m in a.cena.motivos)


def test_poste_aceso_veta_apagao(monkeypatch):
    from conftest import poste

    class Falso:
        def ler(self, img, c):
            return cc.fundir_cena(c, {"apagao": 0.9, "iluminada": 0.05, "trecho_escuro": 0.05})
    monkeypatch.setattr("visao.pipeline.classificador_padrao", lambda: Falso())
    a = analisar_imagem(cena(20), DetectorFalso([poste("poste_aceso"), poste("poste_apagado", bbox=(300, 50, 340, 300))]))
    assert a.cena.classe == "trecho_escuro" and not a.cena.possivel_apagao
    assert "falta_de_energia" not in [t.value for t in a.fusao.tipos_chamado]
    assert any("rede tem energia" in m for m in a.cena.motivos)
