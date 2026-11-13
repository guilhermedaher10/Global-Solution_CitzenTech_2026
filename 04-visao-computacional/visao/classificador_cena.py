"""Classificador de CENA (YOLO26-cls) + fusão explicável com as regras de cena.py.

As regras medem luz (índice de escuridão, fontes de luz). O classificador foi treinado em fotos rotuladas
por pessoas e enxerga o CONTEXTO: prédios inteiros apagados, rua só com faróis, semáforo desligado,
coisas que um limiar de brilho não vê. Cada um erra de um jeito; juntos, erram menos.

Classes: iluminada · trecho_escuro (falha de iluminação, há luz elétrica por perto) · apagao (falta de energia).

Fusão (limiar em configs/regras.yaml, seção classificador_cena), escolhida pela avaliação por cenário
(scripts/avaliar_cena.py, results/cena/):
  - veto da física nos dois sentidos: cena medida como ILUMINADA nunca vira apagão, e cena medida como
    MUITO ESCURA/BREU nunca vira "iluminada", diga o classificador o que disser;
  - classificador confiante (>= confianca_minima): vale o classificador;
  - classificador indeciso: valem as medidas de luz.
Sem o arquivo do modelo (models/cena.pt), tudo funciona só com as regras.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .config import regras
from .schemas import Cena

log = logging.getLogger("visao.cena")
RAIZ = Path(__file__).resolve().parent.parent
CLASSES = ("iluminada", "trecho_escuro", "apagao")


@dataclass
class LeituraCena:
    classe: str
    confianca: float
    fonte: str                      # "regras", "classificador" ou "regras+classificador"
    probabilidades: dict = field(default_factory=dict)
    motivo: str = ""


def classe_das_regras(c: Cena) -> str:
    if c.possivel_apagao:
        return "apagao"
    return "trecho_escuro" if c.nivel.value in ("muito_escura", "breu") else "iluminada"


def fundir_cena(c: Cena, probs: dict | None) -> LeituraCena:
    cfg = regras().get("classificador_cena", {})
    r = classe_das_regras(c)
    if not probs:
        return LeituraCena(r, 1.0, "regras", {}, "sem classificador: decisão pelas medidas de luz")
    ordem = sorted(probs, key=probs.get, reverse=True)
    top = ordem[0]
    # veto da física: cena medida como iluminada não é apagão, diga o classificador o que disser
    if top == "apagao" and c.nivel.value == "iluminada":
        top = ordem[1]
        return LeituraCena(top, probs[top], "regras+classificador", probs,
                           f"o classificador sugeriu apagão, mas a cena tem luz medida: {top.replace('_', ' ')}")
    # e o contrário: cena medida como muito escura ou breu não é "iluminada" (há falha de luz, ao menos local)
    if top == "iluminada" and c.nivel.value in ("muito_escura", "breu"):
        top = next(k for k in ordem if k != "iluminada")
        return LeituraCena(top, probs[top], "regras+classificador", probs,
                           f"o classificador viu luz, mas a cena medida está {c.nivel.value.replace('_', ' ')}: "
                           f"{top.replace('_', ' ')}")
    if probs[top] >= cfg.get("confianca_minima", 0.5):
        concorda = top == r
        return LeituraCena(top, probs[top], "regras+classificador" if concorda else "classificador", probs,
                           f"classificador {probs[top]:.0%} {top.replace('_', ' ')}"
                           + (" e as medidas de luz concordam" if concorda else f" (as medidas diziam {r.replace('_', ' ')})"))
    return LeituraCena(r, probs.get(r, 0.0), "regras", probs, "classificador indeciso: vale a medida de luz")


class ClassificadorCena:
    def __init__(self, caminho: str | None = None):
        self.caminho = Path(caminho or os.getenv("CENA_MODELO_PATH") or RAIZ / "models" / "cena.pt")
        self.modelo = None
        if self.caminho.exists():
            try:
                from ultralytics import YOLO
                self.modelo = YOLO(str(self.caminho), task="classify")
                log.info("classificador de cena carregado: %s", self.caminho)
            except Exception as e:   # sem classificador, as regras seguem sozinhas
                log.warning("classificador de cena indisponível: %s", e)

    @property
    def disponivel(self) -> bool:
        return self.modelo is not None

    def probabilidades(self, img: np.ndarray) -> dict | None:
        if self.modelo is None:
            return None
        r = self.modelo.predict(img, verbose=False, imgsz=regras().get("classificador_cena", {}).get("imgsz", 320))[0]
        return {self.modelo.names[i]: round(float(v), 4) for i, v in enumerate(r.probs.data.tolist())}

    def ler(self, img: np.ndarray, cena: Cena) -> LeituraCena:
        return fundir_cena(cena, self.probabilidades(img))


_padrao: ClassificadorCena | None = None


def classificador_padrao() -> ClassificadorCena:
    global _padrao
    if _padrao is None:
        _padrao = ClassificadorCena()
    return _padrao
