"""Detecção em tempo real com rastreamento e painel de realidade aumentada.

    python scripts/tempo_real.py --fonte 0                       # webcam
    python scripts/tempo_real.py --fonte video.mp4 --salvar results/demo.mp4
    python scripts/tempo_real.py --fonte https://www.youtube.com/watch?v=XXXX --salvar results/demo.mp4
    python scripts/tempo_real.py --fonte video.mp4 --eventos results/eventos.jsonl --lux 2.5

Cada poste recebe um id (ByteTrack) e é contado UMA vez no trajeto, pela classe que mais
apareceu nos frames em que foi visto (voto da maioria: evita contar errado por um frame ruim).
Quando um poste novo é confirmado como apagado, gera um evento no formato do contrato
(o mesmo JSON da API) em --eventos e, se informado, envia para --webhook (backend/RPA).
Teclas: q = sair, espaço = pausar.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2

from _comum import RAIZ
from visao.config import CLASSE_ACESO, CLASSE_APAGADO
from visao.detector import YoloDetector
from visao.imagem import luminosidade_media
from visao.overlay import desenhar_deteccoes, desenhar_painel
from visao.pipeline import analisar_imagem
from visao.privacidade import BorradorRostos
from visao.regras import classificar_trecho

FRAMES_PARA_CONFIRMAR = 3


def abrir_fonte(fonte: str):
    if fonte.isdigit():
        return cv2.VideoCapture(int(fonte))
    if fonte.startswith("http"):
        from extrair_frames import baixar_youtube
        print("baixando vídeo...")
        fonte = str(baixar_youtube(fonte))
    return cv2.VideoCapture(fonte)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fonte", default="0", help="0 = webcam, caminho de vídeo ou URL do YouTube")
    ap.add_argument("--modelo", default=None, help="padrão: models/best.pt")
    ap.add_argument("--conf", type=float, default=None)
    ap.add_argument("--salvar", default=None, help="grava o vídeo com o painel (mp4)")
    ap.add_argument("--eventos", default=None, help="arquivo .jsonl com um chamado por poste apagado")
    ap.add_argument("--webhook", default=None, help="URL que recebe cada evento via POST (JSON)")
    ap.add_argument("--lux", type=float, default=None, help="leitura do sensor de luz (simula o robô)")
    ap.add_argument("--lat", type=float, default=None)
    ap.add_argument("--lon", type=float, default=None)
    ap.add_argument("--sem-janela", action="store_true", help="não abre janela (servidor/robô)")
    args = ap.parse_args()

    det = YoloDetector(args.modelo, conf=args.conf)
    borrador = BorradorRostos()
    cap = abrir_fonte(args.fonte)
    if not cap.isOpened():
        print(f"não consegui abrir a fonte {args.fonte}")
        return 1

    escritor = None
    votos: dict[int, Counter] = defaultdict(Counter)
    reportados: set[int] = set()
    arq_eventos = open(args.eventos, "a", encoding="utf-8") if args.eventos else None
    ultimo_chamado, t_ant, fps, pausado = None, time.time(), 0.0, False

    try:
        while True:
            if not pausado:
                ok, frame = cap.read()
                if not ok:
                    break
                deteccoes = det.rastrear(frame)
                for d in deteccoes:
                    if d.id_rastreio is not None:
                        votos[d.id_rastreio][d.classe] += 1

                confirmados = {i: c.most_common(1)[0][0] for i, c in votos.items()
                               if sum(c.values()) >= FRAMES_PARA_CONFIRMAR}
                unicos = (sum(v == CLASSE_ACESO for v in confirmados.values()),
                          sum(v == CLASSE_APAGADO for v in confirmados.values()))

                novos_apagados = [i for i, c in confirmados.items() if c == CLASSE_APAGADO and i not in reportados]
                if novos_apagados:
                    reportados.update(novos_apagados)
                    analise = analisar_imagem(frame, det, origem="robo" if args.lux is not None else "camera",
                                              latitude=args.lat, longitude=args.lon, sensor_lux=args.lux,
                                              borrador=borrador, deteccoes=deteccoes)
                    ultimo_chamado = (f"Chamado: prioridade {analise.prioridade.nivel.value.upper()} "
                                      f"({analise.prioridade.pontuacao})" if analise.validacao.abrir_chamado else None)
                    evento = analise.model_dump(mode="json")
                    if arq_eventos:
                        arq_eventos.write(json.dumps(evento, ensure_ascii=False) + "\n")
                        arq_eventos.flush()
                    if args.webhook:
                        try:
                            import httpx
                            httpx.post(args.webhook, json=evento, timeout=3)
                        except Exception as e:
                            print(f"[webhook] falhou: {e}")

                acesos = sum(d.classe == CLASSE_ACESO for d in deteccoes)
                apagados = sum(d.classe == CLASSE_APAGADO for d in deteccoes)
                lum = luminosidade_media(frame)
                status = classificar_trecho(acesos, apagados, lum)

                agora = time.time()
                fps = 0.9 * fps + 0.1 * (1 / max(agora - t_ant, 1e-6))
                t_ant = agora

                saida, _ = borrador.borrar(frame)  # o vídeo gravado também respeita a LGPD
                desenhar_deteccoes(saida, deteccoes)
                desenhar_painel(saida, status, acesos, apagados, lum, fps, unicos, ultimo_chamado)

                if args.salvar:
                    if escritor is None:
                        Path(args.salvar).parent.mkdir(parents=True, exist_ok=True)
                        h, w = saida.shape[:2]
                        fps_video = cap.get(cv2.CAP_PROP_FPS) or 30
                        escritor = cv2.VideoWriter(args.salvar, cv2.VideoWriter_fourcc(*"mp4v"), fps_video, (w, h))
                    escritor.write(saida)

            if not args.sem_janela:
                cv2.imshow("Ruas Escuras - Visao Computacional", saida)
                tecla = cv2.waitKey(1) & 0xFF
                if tecla == ord("q"):
                    break
                if tecla == ord(" "):
                    pausado = not pausado
    finally:
        cap.release()
        if escritor:
            escritor.release()
        if arq_eventos:
            arq_eventos.close()
        if not args.sem_janela:
            cv2.destroyAllWindows()

    print(f"Trajeto: {len(votos)} postes rastreados, {len(reportados)} apagados reportados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
