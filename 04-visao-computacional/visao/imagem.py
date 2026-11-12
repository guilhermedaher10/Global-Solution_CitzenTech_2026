"""Medidas da imagem que não dependem do modelo: brilho, nitidez, tamanho."""
from __future__ import annotations

import cv2
import numpy as np


def luminosidade_media(img: np.ndarray) -> float:
    """Brilho médio da cena (canal V do HSV), de 0 a 255."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return round(float(hsv[..., 2].mean()), 1)


def nitidez(img: np.ndarray, lado: int = 640) -> float:
    """Nitidez independente de resolução e de brilho. Foto tremida fica perto de 0.

    Variância do Laplaciano medida com o lado menor reduzido a `lado` px e dividida pelo contraste
    da imagem (x1000). Sem isso, foto de celular (4000 px) e foto noturna (escura) pareciam
    tremidas. Medido em 45 fotos noturnas: boas >= 8, as mesmas borradas <= 2.6.
    """
    h, w = img.shape[:2]
    escala = lado / min(h, w)
    if escala < 1:
        img = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float64)
    return round(float(cv2.Laplacian(cinza, cv2.CV_64F).var() / (cinza.var() + 1) * 1000), 1)


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
