"""Prepara a foto que vai anexada ao chamado (LGPD).

- Sempre: reencoda a imagem, o que descarta EXIF (inclui GPS e modelo do aparelho).
- Se opencv estiver instalado: desfoca rostos e placas detectados (rede de seguranca).

Importante: o desfoque Haar do OpenCV e basico (nao e treinado para placas brasileiras).
O ideal e o componente de visao computacional do grupo (YOLO) ja entregar a foto anonimizada;
este passo e uma segunda barreira, nao a unica.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image


def _desfocar(im: Image.Image) -> tuple[Image.Image, int | None]:
    """Retorna (imagem, regioes_desfocadas). None = opencv indisponivel."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return im, None

    try:
        cv2.setLogLevel(0)  # silencia o ruido do opencv quando as cascatas nao existem
    except Exception:  # noqa: BLE001
        pass
    try:
        base = cv2.data.haarcascades
    except AttributeError:  # algumas builds do opencv nao trazem os arquivos de cascata
        return im, None
    classificadores = []
    for nome in ("haarcascade_frontalface_default.xml", "haarcascade_russian_plate_number.xml"):
        clf = cv2.CascadeClassifier(base + nome)
        if clf.empty():  # arquivo ausente: trata como "desfoque indisponivel", nao como erro
            return im, None
        classificadores.append(clf)

    arr = np.array(im)[:, :, ::-1].copy()
    cinza = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    total = 0
    for clf in classificadores:
        for (x, y, w, h) in clf.detectMultiScale(cinza, 1.1, 4):
            arr[y:y + h, x:x + w] = cv2.GaussianBlur(arr[y:y + h, x:x + w], (51, 51), 0)
            total += 1
    return Image.fromarray(arr[:, :, ::-1]), total


def preparar_foto(origem: Path, destino: Path) -> int | None:
    """Grava a foto limpa em `destino`. Devolve regioes desfocadas (None se opencv ausente)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(origem) as bruta:
        im = bruta.convert("RGB")
    im, regioes = _desfocar(im)
    im.thumbnail((1280, 1280))
    limpa = Image.new("RGB", im.size)
    limpa.paste(im)  # imagem nova: nenhum metadado herdado
    limpa.save(destino, "JPEG", quality=85)
    return regioes
