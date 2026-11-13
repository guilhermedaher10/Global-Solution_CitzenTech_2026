"""Vídeo curto gravado AO VIVO no navegador -> uma análise (a mesma resposta de /v1/analisar).

Num vídeo o cidadão pode girar o celular e mostrar a rua inteira: o poste apagado lá no fim, a esquina
escura. Aqui:
  1. o vídeo é gravado num arquivo temporário (o OpenCV precisa de um caminho) e APAGADO no fim;
  2. um quadro a cada `intervalo_s` (até `max_quadros`, nos primeiros `max_segundos`);
  3. o detector roda em cada quadro; o quadro mais evidente vira a prova: mais postes apagados,
     depois sinal de apagão, depois o mais nítido (prova borrada não convence ninguém);
  4. só esse quadro passa pelo resto do fluxo (cena, validação, prioridade, rostos borrados).
Limites em configs/regras.yaml, seção video. O vídeo nunca é guardado.
"""
from __future__ import annotations

import os
import tempfile

import cv2
import numpy as np

from . import imagem as im
from .cena import analisar_cena
from .config import CLASSE_APAGADO, regras
from .detector import Detector
from .pipeline import ImagemInvalida, analisar_imagem
from .schemas import Analise, Video

SUFIXOS = {"video/webm": ".webm", "video/mp4": ".mp4", "video/quicktime": ".mov", "video/x-matroska": ".mkv"}


def ler_quadros(caminho: str) -> tuple[list[tuple[float, np.ndarray]], float]:
    c = regras()["video"]
    cap = cv2.VideoCapture(caminho)
    if not cap.isOpened():
        raise ImagemInvalida("não consegui abrir o vídeo (use WebM ou MP4)")
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if 1 <= fps <= 240 else 30.0
    quadros, i, proximo, t = [], 0, 0.0, 0.0
    try:
        while True:
            if not cap.grab():
                break
            pos = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            t = pos if pos > 0 else i / fps   # WebM do navegador às vezes não informa a posição
            i += 1
            if t > c["max_segundos"]:
                break
            if t + 1e-6 >= proximo:
                ok, quadro = cap.retrieve()
                if ok and quadro is not None:
                    quadros.append((round(t, 2), quadro))
                proximo += c["intervalo_s"]
    finally:
        cap.release()
    if len(quadros) > c["max_quadros"]:   # espalha os escolhidos pelo vídeo inteiro
        idx = np.linspace(0, len(quadros) - 1, c["max_quadros"]).round().astype(int)
        quadros = [quadros[k] for k in idx]
    return quadros, round(t, 2)


def analisar_video_bytes(dados: bytes, tipo: str, detector: Detector, **kw) -> Analise:
    caminho = None
    try:
        with tempfile.NamedTemporaryFile(suffix=SUFIXOS.get(tipo, ".webm"), delete=False) as f:
            f.write(dados)
            caminho = f.name
        quadros, duracao = ler_quadros(caminho)
    finally:
        if caminho and os.path.exists(caminho):
            os.unlink(caminho)   # o vídeo não fica guardado
    if not quadros:
        raise ImagemInvalida("o vídeo não tem nenhum quadro legível")

    area_max = regras()["deteccao"].get("area_maxima", 0.5)
    avaliados = []
    for t, q in quadros:
        h, w = q.shape[:2]
        dets = [d for d in detector.detectar(q)
                if (d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1]) <= area_max * h * w]
        apagados = sum(d.classe == CLASSE_APAGADO for d in dets)
        apagao = analisar_cena(q).possivel_apagao
        avaliados.append({"t": t, "q": q, "dets": dets, "apagados": apagados, "apagao": apagao,
                          "chave": (apagados, apagao, im.nitidez(q))})
    melhor = max(avaliados, key=lambda a: a["chave"])

    analise = analisar_imagem(melhor["q"], detector, deteccoes=melhor["dets"], **kw)
    resumo = Video(quadros_analisados=len(avaliados), duracao_s=duracao, quadro_escolhido_s=melhor["t"],
                   apagados_max=max(a["apagados"] for a in avaliados),
                   quadros_com_apagado=sum(a["apagados"] > 0 for a in avaliados),
                   quadros_com_apagao=sum(a["apagao"] for a in avaliados))
    analise.video = resumo
    analise.validacao.motivos.insert(0, f"vídeo ao vivo: {resumo.quadros_analisados} quadros analisados em "
                                        f"{duracao:.1f} s; o quadro de {melhor['t']:.1f} s é a evidência mais forte")
    return analise
