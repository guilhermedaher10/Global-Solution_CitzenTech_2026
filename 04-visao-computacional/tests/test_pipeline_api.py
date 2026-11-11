import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from conftest import DetectorFalso, cena, jpeg, poste
from visao.pipeline import ImagemInvalida, analisar_bytes
from visao.privacidade import ler_metadados
from visao.schemas import VERSAO_CONTRATO


def _jpeg_com_exif(img_bgr, lat=(23, 33, 1.8), lon=(46, 38, 0.0)) -> bytes:
    pil = Image.fromarray(img_bgr[..., ::-1])
    exif = Image.Exif()
    exif[306] = "2026:11:12 22:41:07"
    gps = {1: "S", 2: lat, 3: "W", 4: lon}
    exif[0x8825] = gps
    buf = io.BytesIO()
    pil.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_pipeline_noturna_com_poste_apagado():
    det = DetectorFalso([poste("poste_apagado"), poste("poste_aceso", bbox=(300, 40, 340, 290))])
    a = analisar_bytes(jpeg(cena(30)), det, origem="cidadao", latitude=-23.55, longitude=-46.63)
    assert a.resumo.status_trecho.value == "escura"
    assert a.validacao.abrir_chamado
    assert a.prioridade.nivel.value in ("alta", "media")
    assert a.localizacao.fonte == "informada"
    assert a.privacidade.imagem_armazenada is False
    assert a.imagem_anonimizada_base64 is None


def test_exif_vira_localizacao_e_hora_e_e_removido():
    dados = _jpeg_com_exif(cena(30))
    meta = ler_metadados(dados)
    assert meta.latitude == pytest.approx(-23.5505, abs=1e-3)
    assert meta.hora_captura == "2026-11-12T22:41:07"

    a = analisar_bytes(dados, DetectorFalso([poste("poste_apagado")]), retornar_imagem=True)
    assert a.localizacao.fonte == "exif"
    assert a.hora_captura == "2026-11-12T22:41:07"
    saida = base64.b64decode(a.imagem_anonimizada_base64)
    assert len(Image.open(io.BytesIO(saida)).getexif()) == 0   # nada de EXIF na imagem que sai


def test_bytes_invalidos():
    with pytest.raises(ImagemInvalida):
        analisar_bytes(b"nao sou imagem", DetectorFalso())


@pytest.fixture
def cliente():
    from api import main

    main._estado["detector"] = DetectorFalso([poste("poste_apagado")])
    main._estado["erro"] = None
    app = main.app
    app.router.lifespan_context = _sem_lifespan  # não tenta carregar o YOLO de verdade
    with TestClient(app) as c:
        yield c


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def _sem_lifespan(app):
    yield


def test_api_saude(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200 and r.json()["modelo_carregado"] is True


def test_api_analisar(cliente):
    r = cliente.post("/v1/analisar", files={"imagem": ("rua.jpg", jpeg(cena(30)), "image/jpeg")},
                     data={"origem": "robo", "sensor_lux": "1.5", "latitude": "-23.55", "longitude": "-46.63"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["versao_contrato"] == VERSAO_CONTRATO
    assert j["origem"] == "robo"
    assert j["validacao"]["abrir_chamado"] is True
    assert j["prioridade"]["nivel"] == "alta"


def test_api_rejeita_tipo_e_lixo(cliente):
    r = cliente.post("/v1/analisar", files={"imagem": ("a.txt", b"oi", "text/plain")})
    assert r.status_code == 415
    r = cliente.post("/v1/analisar", files={"imagem": ("a.jpg", b"oi", "image/jpeg")})
    assert r.status_code == 422


def test_api_sem_modelo_responde_503():
    from api import main

    main._estado["detector"], main._estado["erro"] = None, "sem best.pt"
    main.app.router.lifespan_context = _sem_lifespan
    with TestClient(main.app) as c:
        assert c.get("/saude").json()["status"] == "degradado"
        r = c.post("/v1/analisar", files={"imagem": ("rua.jpg", jpeg(cena(30)), "image/jpeg")})
        assert r.status_code == 503
