"""Camada de realidade aumentada para o vídeo: caixas, etiquetas e painel do trecho."""
from __future__ import annotations

import cv2
import numpy as np

from .config import CLASSE_APAGADO
from .schemas import Deteccao, StatusTrecho

VERDE = (80, 200, 80)
VERMELHO = (40, 40, 230)
AMARELO = (0, 200, 255)
BRANCO = (255, 255, 255)
PRETO = (0, 0, 0)

COR_STATUS = {
    StatusTrecho.iluminada: VERDE,
    StatusTrecho.parcial: AMARELO,
    StatusTrecho.escura: VERMELHO,
    StatusTrecho.sem_postes_visiveis: (180, 180, 180),
}


def _texto(img, txt, org, cor=BRANCO, escala=0.55, esp=1):
    cv2.putText(img, txt, org, cv2.FONT_HERSHEY_SIMPLEX, escala, PRETO, esp + 2, cv2.LINE_AA)
    cv2.putText(img, txt, org, cv2.FONT_HERSHEY_SIMPLEX, escala, cor, esp, cv2.LINE_AA)


def desenhar_deteccoes(img: np.ndarray, deteccoes: list[Deteccao]) -> np.ndarray:
    for d in deteccoes:
        x1, y1, x2, y2 = d.bbox
        apagado = d.classe == CLASSE_APAGADO
        cor = VERMELHO if apagado else VERDE
        cv2.rectangle(img, (x1, y1), (x2, y2), cor, 2)
        rotulo = ("APAGADO" if apagado else "aceso") + f" {d.confianca:.0%}"
        if d.id_rastreio is not None:
            rotulo = f"#{d.id_rastreio} " + rotulo
        _texto(img, rotulo, (x1, max(18, y1 - 6)), cor)
    return img


def desenhar_painel(img: np.ndarray, status: StatusTrecho, acesos: int, apagados: int,
                    luminosidade: float, fps: float | None = None,
                    total_unicos: tuple[int, int] | None = None, chamado: str | None = None,
                    regiao: str | None = None) -> np.ndarray:
    """Painel no canto superior esquerdo. total_unicos = (acesos, apagados) contados no trajeto."""
    linhas = [f"Trecho: {status.value.upper()}",
              f"No quadro: {acesos} aceso(s) | {apagados} apagado(s)",
              f"Luminosidade: {luminosidade:.0f}/255"]
    if total_unicos is not None:
        linhas.append(f"No trajeto: {total_unicos[0]} aceso(s) | {total_unicos[1]} apagado(s)")
    if regiao:
        linhas.append(regiao)
    if chamado:
        linhas.append(chamado)
    if fps is not None:
        linhas.append(f"{fps:.0f} FPS")

    largura, altura = 430, 24 * len(linhas) + 14
    sub = img[0:altura, 0:largura]
    img[0:altura, 0:largura] = cv2.addWeighted(sub, 0.35, np.zeros_like(sub), 0.65, 0)
    cv2.rectangle(img, (0, 0), (6, altura), COR_STATUS[status], -1)
    for i, linha in enumerate(linhas):
        cor = COR_STATUS[status] if i == 0 else BRANCO
        _texto(img, linha, (16, 26 + 24 * i), cor, 0.6 if i == 0 else 0.5, 2 if i == 0 else 1)
    return img
