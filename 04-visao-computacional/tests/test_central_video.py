"""Central de chamados (servidor), encaminhamento, agrupamento em regiões e vídeo ao vivo."""
import os
import tempfile
from datetime import datetime, timedelta

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from conftest import DetectorFalso, cena, jpeg, poste
from visao.central import Central, RepositorioSQLite, TransicaoInvalida, encaminhar
from visao.regioes import agrupar, bairro_de, distancia_m
from visao.schemas import Chamado, EventoChamado, Evidencia, NivelLuz, StatusChamado


@pytest.fixture
def cliente():
    from api import main
    main._estado.update(detector=DetectorFalso([poste("poste_apagado")]), erro=None)
    with TestClient(main.app) as c:
        main._estado.update(detector=DetectorFalso([poste("poste_apagado")]), erro=None)
        yield c


def video_bytes(ext=".webm", cc="VP80", brilho=30, quadros=30, fps=10) -> bytes:
    caminho = os.path.join(tempfile.mkdtemp(), "v" + ext)
    w = cv2.VideoWriter(caminho, cv2.VideoWriter_fourcc(*cc), fps, (640, 480))
    rng = np.random.default_rng(1)
    for _ in range(quadros):
        q = np.clip(brilho + rng.integers(-25, 26, (480, 640, 3)), 0, 255).astype(np.uint8)
        w.write(q)
    w.release()
    with open(caminho, "rb") as f:
        return f.read()


# ------------------------------------------------------------------ encaminhamento
def test_poste_vai_para_iluminacao_e_apagao_para_distribuidora():
    assert "Iluminação pública" in encaminhar(["conserto_poste"])[0].orgao
    orgaos = [e.orgao for e in encaminhar(["falta_de_energia"])]
    assert any("Enel" in o for o in orgaos) and any("Defesa Civil" in o for o in orgaos)
    assert "Subprefeitura" in encaminhar(["buraco"])[0].orgao
    # mesmo órgão não se repete
    assert len(encaminhar(["conserto_poste", "trecho_sem_luz"])) == 1


# ------------------------------------------------------------------ API: foto -> central
def test_foto_com_falha_abre_chamado_na_central_e_da_para_acompanhar(cliente):
    r = cliente.post("/v1/analisar", files={"imagem": ("a.jpg", jpeg(cena(30)), "image/jpeg")},
                     data={"latitude": "-23.56", "longitude": "-46.65", "endereco": "Rua A, 1 · Bela Vista · São Paulo"})
    a = r.json()
    assert r.status_code == 200 and a["validacao"]["abrir_chamado"]
    assert a["protocolo"].startswith("VSP-") and a["encaminhar_para"]
    c = cliente.get(f"/v1/chamados/{a['protocolo']}").json()
    assert c["status"] == "recebido" and c["evidencia"] == "foto" and c["endereco"].startswith("Rua A")
    assert [x["protocolo"] for x in cliente.get("/v1/chamados").json()] == [a["protocolo"]]


def test_registrar_false_nao_grava(cliente):
    a = cliente.post("/v1/analisar", files={"imagem": ("a.jpg", jpeg(cena(30)), "image/jpeg")},
                     data={"registrar": "false"}).json()
    assert a["protocolo"] is None and cliente.get("/v1/chamados").json() == []


def test_status_segue_o_fluxo_e_nao_pula_etapa(cliente):
    p = cliente.post("/v1/analisar", files={"imagem": ("a.jpg", jpeg(cena(30)), "image/jpeg")}).json()["protocolo"]
    assert cliente.post(f"/v1/chamados/{p}/status", json={"status": "resolvido"}).status_code == 409
    for s in ["confirmado", "encaminhado", "em_reparo", "resolvido"]:
        r = cliente.post(f"/v1/chamados/{p}/status", json={"status": s, "nota": "teste"})
        assert r.status_code == 200, r.text
    c = cliente.get(f"/v1/chamados/{p.lower()}").json()   # protocolo sem diferenciar maiúsculas
    assert [h["status"] for h in c["historico"]] == ["recebido", "confirmado", "encaminhado", "em_reparo", "resolvido"]
    assert cliente.get("/v1/chamados/VSP-NAOEXISTE").status_code == 404


def test_relato_e_robo_viram_suspeita_na_central(cliente):
    r = cliente.post("/v1/relatos", json={"latitude": -23.5, "longitude": -46.6, "problema": ["escuro"]}).json()
    assert r["protocolo"] and "Iluminação" in r["encaminhar_para"][0]["orgao"]
    rb = cliente.post("/v1/alerta-robo", json={"latitude": -23.5, "longitude": -46.6, "sensor_lux": 2}).json()
    assert rb["protocolo"]
    origens = {c["origem"]: c["evidencia"] for c in cliente.get("/v1/chamados").json()}
    assert origens == {"relato": "relato", "robo": "sensores"}
    # leitura normal do robô não vira chamado
    assert cliente.post("/v1/alerta-robo", json={"latitude": -23.5, "longitude": -46.6, "sensor_lux": 40}).json()["protocolo"] is None


def test_central_fora_do_ar_nao_derruba_a_analise(cliente, monkeypatch):
    from api import main

    class Quebrada(Central):
        def __init__(self): pass
        def registrar_analise(self, *a, **k): raise OSError("disco cheio")
    main._estado["central"] = Quebrada()
    r = cliente.post("/v1/analisar", files={"imagem": ("a.jpg", jpeg(cena(30)), "image/jpeg")})
    assert r.status_code == 200 and r.json()["protocolo"] is None and r.json()["validacao"]["abrir_chamado"]


def test_limpar_exige_token(cliente, monkeypatch):
    assert cliente.post("/v1/central/limpar").status_code == 403
    monkeypatch.setenv("CENTRAL_TOKEN", "segredo")
    assert cliente.post("/v1/central/limpar", headers={"Authorization": "Bearer errado"}).status_code == 403
    assert cliente.post("/v1/central/limpar", headers={"Authorization": "Bearer segredo"}).json() == {"removidos": 0}


# ------------------------------------------------------------------ vídeo ao vivo
@pytest.mark.parametrize("ext,cc,tipo", [(".webm", "VP80", "video/webm"), (".mp4", "mp4v", "video/mp4")])
def test_video_ao_vivo_abre_chamado(cliente, ext, cc, tipo):
    r = cliente.post("/v1/analisar-video", files={"video": ("v" + ext, video_bytes(ext, cc), tipo + ";codecs=vp8")},
                     data={"latitude": "-23.56", "longitude": "-46.65"})
    a = r.json()
    assert r.status_code == 200, r.text
    assert a["video"]["quadros_analisados"] == 6        # 3 s, um quadro a cada 0,5 s
    assert a["video"]["apagados_max"] == 1 and a["validacao"]["motivos"][0].startswith("vídeo ao vivo")
    assert cliente.get(f"/v1/chamados/{a['protocolo']}").json()["evidencia"] == "video"


def test_video_limita_quadros_e_rejeita_lixo(cliente):
    a = cliente.post("/v1/analisar-video", files={"video": ("v.webm", video_bytes(quadros=150), "video/webm")}).json()
    assert a["video"]["quadros_analisados"] <= 16
    assert cliente.post("/v1/analisar-video", files={"video": ("v.webm", b"nao sou video", "video/webm")}).status_code == 422
    assert cliente.post("/v1/analisar-video", files={"video": ("v.gif", b"x", "image/gif")}).status_code == 415


def test_video_escolhe_o_quadro_com_poste_apagado():
    from visao.video import analisar_video_bytes

    class SoNoFim(DetectorFalso):   # só os quadros claros (fim do vídeo) mostram o poste apagado
        def detectar(self, img):
            return [poste("poste_apagado")] if img.mean() > 100 else []
    caminho = os.path.join(tempfile.mkdtemp(), "v.mp4")
    w = cv2.VideoWriter(caminho, cv2.VideoWriter_fourcc(*"mp4v"), 10, (640, 480))
    for i in range(40):
        w.write(np.full((480, 640, 3), 20 if i < 30 else 140, np.uint8))
    w.release()
    a = analisar_video_bytes(open(caminho, "rb").read(), "video/mp4", SoNoFim())
    assert a.video.quadro_escolhido_s >= 3.0 and a.resumo.postes_apagados == 1


# ------------------------------------------------------------------ regiões (apagão)
def chamado(n, lat, lon, *, apagao=False, minutos=10, tipos=("trecho_sem_luz",), endereco=None, status="recebido"):
    ts = (datetime.fromisoformat("2026-11-13T22:00:00-03:00") - timedelta(minutes=minutos)).isoformat()
    return Chamado(protocolo=f"VSP-{n:06d}", id=str(n), ts=ts, origem="cidadao", evidencia=Evidencia.foto,
                   latitude=lat, longitude=lon, endereco=endereco, nivel="alta", pontos=70, tipos=list(tipos),
                   trecho="escura", cena_nivel=NivelLuz.breu if apagao else NivelLuz.muito_escura,
                   possivel_apagao=apagao, status=status, historico=[EventoChamado(status=status, ts=ts)])


REF = "2026-11-13T22:00:00-03:00"


def test_tres_relatos_proximos_com_apagao_viram_regiao():
    end = "Rua X, 10 · Capão Redondo · São Paulo"
    cs = [chamado(1, -23.6600, -46.7700, apagao=True, endereco=end),
          chamado(2, -23.6610, -46.7705, apagao=True, endereco=end),
          chamado(3, -23.6605, -46.7690, tipos=("suspeita_escuro",)),
          chamado(4, -23.5000, -46.6000, apagao=True)]                 # longe: fica de fora
    [r] = agrupar(cs, REF)
    assert r.tipo == "apagao_regiao" and r.relatos == 3 and r.sinais_apagao == 2
    assert r.titulo == "Possível apagão em Capão Redondo"
    assert any("Enel" in e.orgao for e in r.encaminhar_para)


def test_breu_com_postes_acesos_nao_e_apagao():
    cs = [chamado(i, -23.66, -46.77, tipos=("conserto_poste",)) for i in range(3)]
    for c in cs:
        c.cena_nivel = NivelLuz.breu          # escuro, mas sem possivel_apagao: há luz na cena
    [r] = agrupar(cs, REF)
    assert r.tipo == "trecho_escuro_recorrente" and r.sinais_apagao == 0


def test_relatos_sem_sinal_de_apagao_viram_trecho_recorrente():
    cs = [chamado(i, -23.66 + i * 0.001, -46.77) for i in range(3)]
    [r] = agrupar(cs, REF)
    assert r.tipo == "trecho_escuro_recorrente" and "Iluminação" in r.encaminhar_para[0].orgao


def test_regiao_ignora_antigos_fechados_e_poucos():
    assert agrupar([chamado(i, -23.66, -46.77, minutos=60 * 8) for i in range(5)], REF) == []    # fora da janela
    assert agrupar([chamado(i, -23.66, -46.77, status="resolvido") for i in range(5)], REF) == []
    assert agrupar([chamado(i, -23.66, -46.77) for i in range(2)], REF) == []                    # só 2


def test_distancia_e_bairro():
    assert 1100 < distancia_m(-23.0, -46.0, -23.01, -46.0) < 1120
    assert bairro_de("Rua A, 1 · Bela Vista · São Paulo") == "Bela Vista"
    assert bairro_de(None) is None


def test_regioes_pela_api(cliente):
    for i in range(3):
        cliente.post("/v1/relatos", json={"latitude": -23.66 + i * 0.0005, "longitude": -46.77, "problema": ["escuro"]})
    [r] = cliente.get("/v1/regioes").json()
    assert r["relatos"] == 3 and r["tipo"] == "trecho_escuro_recorrente"


def test_transicao_invalida_e_repositorio(tmp_path):
    central = Central(RepositorioSQLite(str(tmp_path / "c.db")))
    c = chamado(9, -23.6, -46.6)
    central.repo.salvar(c)
    with pytest.raises(TransicaoInvalida):
        central.mudar_status(c.protocolo, StatusChamado.em_reparo)
    assert central.mudar_status(c.protocolo, StatusChamado.confirmado).status == "confirmado"
    assert central.limpar() == 1 and central.listar() == []
