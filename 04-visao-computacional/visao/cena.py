"""Análise de CENA: a região está no escuro? (não só "tem poste apagado?").

Uma rua escura pode não ter nenhum poste visível: apagão no bairro, postes fracos e espaçados, breu.
Aqui a foto inteira é medida de forma explicável (sem caixa-preta):

  luz no chão      brilho do terço de baixo, onde as pessoas andam
  fontes de luz    quantos pontos de luz existem (postes, janelas, faróis, letreiros) e quanto ocupam
  área iluminada   fração da imagem com luz útil
  grade de luz     a foto dividida em 6x8 blocos com o brilho de cada um (o "mapa de luz" do front)

Daí sai um índice de escuridão (0 a 100), um nível (iluminada, pouca_iluminacao, muito_escura,
breu) e o sinal de POSSÍVEL APAGÃO: cena escura sem nenhuma fonte de luz, nem janelas nem letreiros.
Apagão não é problema de poste: é falta de energia, e o chamado vai para a concessionária.
Limiares em configs/regras.yaml (seção cena).
"""
from __future__ import annotations

import cv2
import numpy as np

from .config import regras
from .schemas import Cena, NivelLuz

LINHAS, COLUNAS = 6, 8


def analisar_cena(img: np.ndarray) -> Cena:
    c = regras()["cena"]
    h, w = img.shape[:2]
    escala = min(1.0, 640 / max(h, w))
    if escala < 1:
        img = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    v = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 2]
    H, W = v.shape
    total = H * W

    media = float(v.mean())
    chao = float(v[int(H * 0.6):].mean())
    area_iluminada = float((v > c["limiar_iluminado"]).mean())

    # fontes de luz: regiões quase saturadas com tamanho mínimo (ruído e estrelas não contam)
    claro = (v >= c["limiar_fonte"]).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(claro, connectivity=8)
    minimo = max(4, int(total * c["area_minima_fonte"]))
    areas = [int(stats[i, cv2.CC_STAT_AREA]) for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= minimo]
    fontes = len(areas)
    area_fontes = sum(areas) / total

    # índice 0-100: mais escuro = maior. Pesos: chão (onde se anda) pesa mais
    luz = (0.5 * min(1.0, chao / c["chao_referencia"])
           + 0.3 * min(1.0, area_iluminada / c["area_referencia"])
           + 0.2 * min(1.0, media / c["media_referencia"]))
    indice = int(round(100 * (1 - luz)))

    if media < regras()["luminosidade"]["limiar_breu"] and area_iluminada < 0.03:
        nivel = NivelLuz.breu
    elif indice >= c["indice_muito_escura"]:
        nivel = NivelLuz.muito_escura
    elif indice >= c["indice_pouca_iluminacao"]:
        nivel = NivelLuz.pouca_iluminacao
    else:
        nivel = NivelLuz.iluminada

    apagao = (nivel in (NivelLuz.breu, NivelLuz.muito_escura)
              and fontes <= c["fontes_max_apagao"] and area_fontes < c["area_fontes_max_apagao"])

    motivos = [f"índice de escuridão {indice}/100 ({nivel.value.replace('_', ' ')})",
               f"luz no chão {chao:.0f}/255, área iluminada {area_iluminada:.0%}",
               f"{fontes} fonte(s) de luz visível(is)"]
    if apagao:
        motivos.append("nenhuma fonte de luz na cena (nem janelas, nem letreiros): possível falta de energia na região")

    grade = [[int(v[i * H // LINHAS:(i + 1) * H // LINHAS, j * W // COLUNAS:(j + 1) * W // COLUNAS].mean())
              for j in range(COLUNAS)] for i in range(LINHAS)]
    return Cena(indice_escuridao=indice, nivel=nivel, luz_no_chao=round(chao, 1),
                area_iluminada=round(area_iluminada, 3), fontes_de_luz=fontes, possivel_apagao=apagao,
                grade_luz=grade, motivos=motivos)
