import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from visao.schemas import Deteccao  # noqa: E402


class DetectorFalso:
    """Devolve sempre as mesmas detecções: testa regras/API sem GPU nem modelo treinado."""

    nome = "falso"
    versao = "teste"

    def __init__(self, deteccoes=None):
        self.deteccoes = deteccoes or []

    def detectar(self, img):
        return list(self.deteccoes)

    def rastrear(self, img):
        return list(self.deteccoes)


def poste(classe, conf=0.9, bbox=(100, 50, 140, 300)):
    return Deteccao(classe=classe, confianca=conf, bbox=list(bbox))


def cena(brilho: int, lado=640, textura=True) -> np.ndarray:
    """Imagem sintética com brilho médio controlado e alguma textura (para passar na nitidez)."""
    rng = np.random.default_rng(0)
    img = np.full((lado, lado, 3), brilho, dtype=np.uint8)
    if textura:
        ruido = rng.integers(-25, 26, size=img.shape)
        img = np.clip(img.astype(int) + ruido, 0, 255).astype(np.uint8)
    return img


def jpeg(img) -> bytes:
    return cv2.imencode(".jpg", img)[1].tobytes()


@pytest.fixture
def detector_falso():
    return DetectorFalso


@pytest.fixture(autouse=True)
def central_isolada(tmp_path, monkeypatch):
    """Cada teste com a sua central (SQLite temporário): nunca toca a central de verdade."""
    monkeypatch.delenv("CENTRAL_TABELA_URL", raising=False)
    monkeypatch.setenv("CENTRAL_DB", str(tmp_path / "central.db"))
    mod = sys.modules.get("api.main")
    if mod is not None:
        mod._estado["central"] = None
    yield
    mod = sys.modules.get("api.main")
    if mod is not None:
        mod._estado["central"] = None
