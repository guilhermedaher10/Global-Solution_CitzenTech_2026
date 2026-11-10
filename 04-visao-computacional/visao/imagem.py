"""Medidas da imagem que não dependem do modelo: brilho, nitidez, tamanho."""
from __future__ import annotations

import cv2
import numpy as np


def luminosidade_media(img: np.ndarray) -> float:
    """Brilho médio da cena (canal V do HSV), de 0 a 255."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return round(float(hsv[..., 2].mean()), 1)


def nitidez(img: np.ndarray) -> float:
    """Variância do Laplaciano: quanto maior, mais nítida. Foto tremida fica perto de 0."""
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return round(float(cv2.Laplacian(cinza, cv2.CV_64F).var()), 1)


def lado_menor(img: np.ndarray) -> int:
    return int(min(img.shape[:2]))


def decodificar(dados: bytes) -> np.ndarray | None:
    """Bytes de JPEG/PNG/WebP -> imagem BGR. None se não for imagem válida."""
    arr = np.frombuffer(dados, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def codificar_jpeg(img: np.ndarray, qualidade: int = 85) -> bytes:
    """Reencoda para JPEG. O OpenCV não grava EXIF, então isso também limpa metadados."""
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, qualidade])
    if not ok:
        raise ValueError("falha ao codificar JPEG")
    return buf.tobytes()
