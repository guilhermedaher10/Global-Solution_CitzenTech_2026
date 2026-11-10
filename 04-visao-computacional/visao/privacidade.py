"""Privacidade por padrão (LGPD).

- Lê do EXIF só o que serve ao chamado (GPS e hora da foto) e descarta o resto
  (modelo do celular, número de série etc.). A imagem que sai daqui não tem EXIF.
- Borra rostos antes de qualquer imagem sair do componente.
- Não guarda nada: quem decide armazenar evidência é o sistema da prefeitura, com base legal.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .config import RAIZ

_TAG_EXIF_IFD = 0x8769
_TAG_GPS_IFD = 0x8825
_TAG_DATA_ORIGINAL = 36867
_TAG_DATA = 306


@dataclass
class MetadadosFoto:
    latitude: float | None = None
    longitude: float | None = None
    hora_captura: str | None = None   # "AAAA-MM-DDTHH:MM:SS", sem fuso (o EXIF não guarda fuso)


def _graus(valor, ref: str) -> float:
    g, m, s = (float(x) for x in valor)
    decimal = g + m / 60 + s / 3600
    return -decimal if ref in ("S", "W") else decimal


def ler_metadados(dados: bytes) -> MetadadosFoto:
    """Extrai GPS e data/hora do EXIF. Qualquer erro = metadado ausente (nunca quebra a análise)."""
    meta = MetadadosFoto()
    try:
        exif = Image.open(io.BytesIO(dados)).getexif()
    except Exception:
        return meta

    try:
        data = exif.get_ifd(_TAG_EXIF_IFD).get(_TAG_DATA_ORIGINAL) or exif.get(_TAG_DATA)
        if data:
            d, h = str(data).strip().split(" ")
            meta.hora_captura = f"{d.replace(':', '-')}T{h}"
    except Exception:
        pass

    try:
        gps = exif.get_ifd(_TAG_GPS_IFD)
        if gps and 2 in gps and 4 in gps:
            lat = _graus(gps[2], gps.get(1, "N"))
            lon = _graus(gps[4], gps.get(3, "E"))
            if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat, lon) != (0.0, 0.0):
                meta.latitude, meta.longitude = round(lat, 6), round(lon, 6)
    except Exception:
        pass
    return meta


class BorradorRostos:
    """Usa o YuNet (mais preciso) se o arquivo existir em models/; senão, o Haar do OpenCV."""

    CAMINHO_YUNET = RAIZ / "models" / "face_detection_yunet_2023mar.onnx"

    def __init__(self) -> None:
        self._yunet = None
        self._haar = None
        if Path(self.CAMINHO_YUNET).exists() and hasattr(cv2, "FaceDetectorYN"):
            self._yunet = cv2.FaceDetectorYN.create(str(self.CAMINHO_YUNET), "", (320, 320), 0.7)
        else:
            caminho = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(caminho)
            self._haar = None if cascade.empty() else cascade

    @property
    def disponivel(self) -> bool:
        return self._yunet is not None or self._haar is not None

    def _rostos(self, img: np.ndarray) -> list[tuple[int, int, int, int]]:
        if self._yunet is not None:
            h, w = img.shape[:2]
            self._yunet.setInputSize((w, h))
            _, faces = self._yunet.detect(img)
            return [tuple(int(v) for v in f[:4]) for f in (faces if faces is not None else [])]
        if self._haar is not None:
            cinza = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
            return [tuple(int(v) for v in r) for r in
                    self._haar.detectMultiScale(cinza, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))]
        return []

    def borrar(self, img: np.ndarray) -> tuple[np.ndarray, int]:
        """Devolve (cópia com rostos borrados, quantidade de rostos)."""
        saida = img.copy()
        rostos = self._rostos(img)
        H, W = img.shape[:2]
        for x, y, w, h in rostos:
            # margem de 20% para cobrir cabelo e queixo
            mx, my = int(w * 0.2), int(h * 0.2)
            x1, y1 = max(0, x - mx), max(0, y - my)
            x2, y2 = min(W, x + w + mx), min(H, y + h + my)
            if x2 <= x1 or y2 <= y1:
                continue
            roi = saida[y1:y2, x1:x2]
            k = max(15, (min(roi.shape[:2]) // 2) | 1)
            saida[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)
        return saida, len(rostos)
