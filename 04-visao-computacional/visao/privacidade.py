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
_TAG_EXPOSICAO, _TAG_ABERTURA, _TAG_ISO, _TAG_FLASH = 33434, 33437, 34855, 37385


@dataclass
class MetadadosFoto:
    latitude: float | None = None
    longitude: float | None = None
    hora_captura: str | None = None   # "AAAA-MM-DDTHH:MM:SS", sem fuso (o EXIF não guarda fuso)
    exposicao_s: float | None = None  # tempo de exposição (s)
    abertura: float | None = None     # número f
    iso: float | None = None
    flash: bool | None = None         # o flash disparou?

    @property
    def ev100(self) -> float | None:
        """Exposição normalizada para ISO 100: quanto MENOR, mais escura estava a cena de verdade
        (rua iluminada à noite ~ 4 a 7; breu ~ 0 ou menos; dia ~ 12 a 15)."""
        import math
        if not (self.exposicao_s and self.abertura and self.iso) or min(self.exposicao_s, self.abertura, self.iso) <= 0:
            return None
        return round(math.log2(self.abertura ** 2 / self.exposicao_s) - math.log2(self.iso / 100), 1)


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

    try:   # exposição: separa "câmera ruim" de "escuro de verdade" (visao/cena.py)
        ifd = exif.get_ifd(_TAG_EXIF_IFD)
        iso = ifd.get(_TAG_ISO)
        iso = iso[0] if isinstance(iso, (tuple, list)) else iso
        meta.exposicao_s = float(ifd[_TAG_EXPOSICAO]) if _TAG_EXPOSICAO in ifd else None
        meta.abertura = float(ifd[_TAG_ABERTURA]) if _TAG_ABERTURA in ifd else None
        meta.iso = float(iso) if iso else None
        meta.flash = bool(int(ifd[_TAG_FLASH]) & 1) if _TAG_FLASH in ifd else None
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
    LADO_MAX_YUNET = 1280

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
            # foto de celular (4000+ px) é reduzida para detectar rápido; as caixas voltam à escala original
            h, w = img.shape[:2]
            escala = min(1.0, self.LADO_MAX_YUNET / max(h, w))
            menor = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA) if escala < 1 else img
            self._yunet.setInputSize((menor.shape[1], menor.shape[0]))
            _, faces = self._yunet.detect(menor)
            return [tuple(int(v / escala) for v in f[:4]) for f in (faces if faces is not None else [])]
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
