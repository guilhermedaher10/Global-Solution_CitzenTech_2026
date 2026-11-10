"""Envelope do YOLO (Ultralytics). O resto do código só conhece a interface `Detector`.

Isso permite trocar o modelo (YOLO26n, YOLO26s, ONNX no robô) sem mexer nas regras, e testar
tudo com um detector falso, sem GPU.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

import numpy as np

from .config import RAIZ, normalizar_classe, regras
from .schemas import Deteccao

MODELO_PADRAO = RAIZ / "models" / "best.pt"


class Detector(Protocol):
    nome: str
    versao: str

    def detectar(self, img: np.ndarray) -> list[Deteccao]: ...

    def rastrear(self, img: np.ndarray) -> list[Deteccao]: ...


class YoloDetector:
    def __init__(self, caminho: str | Path | None = None, conf: float | None = None,
                 device: str | None = None) -> None:
        from ultralytics import YOLO  # import tardio: a API sobe rápido e os testes não precisam de torch

        self.caminho = Path(caminho or os.getenv("MODELO_PATH", MODELO_PADRAO))
        if not self.caminho.exists():
            raise FileNotFoundError(
                f"Modelo não encontrado em {self.caminho}. Treine com scripts/treinar.py "
                "ou defina MODELO_PATH.")
        self.model = YOLO(str(self.caminho))
        cfg = regras()["deteccao"]
        self.conf = conf if conf is not None else cfg["confianca_minima"]
        self.iou = cfg["iou"]
        self.imgsz = cfg["tamanho_imagem"]
        self.device = device or os.getenv("VISAO_DEVICE") or None
        self.nome = os.getenv("MODELO_NOME", self.caminho.stem)
        self.versao = os.getenv("MODELO_VERSAO", "dev")

    def _converter(self, resultado, com_rastreio: bool) -> list[Deteccao]:
        saida: list[Deteccao] = []
        boxes = resultado.boxes
        if boxes is None:
            return saida
        ids = boxes.id.int().tolist() if (com_rastreio and boxes.id is not None) else [None] * len(boxes)
        for box, id_ in zip(boxes, ids):
            classe = normalizar_classe(resultado.names[int(box.cls)])
            if classe is None:
                continue
            x1, y1, x2, y2 = (int(round(v)) for v in box.xyxy[0].tolist())
            saida.append(Deteccao(classe=classe, confianca=round(float(box.conf), 3),
                                  bbox=[x1, y1, x2, y2], id_rastreio=id_))
        return saida

    def detectar(self, img: np.ndarray) -> list[Deteccao]:
        r = self.model.predict(img, conf=self.conf, iou=self.iou, imgsz=self.imgsz,
                               device=self.device, verbose=False)[0]
        return self._converter(r, com_rastreio=False)

    def rastrear(self, img: np.ndarray) -> list[Deteccao]:
        """Para vídeo: mantém o mesmo id para o mesmo poste entre frames (ByteTrack)."""
        r = self.model.track(img, conf=self.conf, iou=self.iou, imgsz=self.imgsz, device=self.device,
                             persist=True, tracker="bytetrack.yaml", verbose=False)[0]
        return self._converter(r, com_rastreio=True)
