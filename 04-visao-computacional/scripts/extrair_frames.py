"""Extrai frames de vídeos noturnos (arquivo local ou link do YouTube) para o dataset.

    python scripts/extrair_frames.py --fonte caminho/video.mp4 --a-cada 1.5
    python scripts/extrair_frames.py --fonte https://www.youtube.com/watch?v=XXXX --a-cada 2 --max 300
    python scripts/extrair_frames.py            # usa a lista `videos` de configs/fontes.yaml

Frames quase iguais ao anterior (carro parado no semáforo) são pulados.
Saída: data/bruto/frames/<nome-do-video>/  e o link vai para data/bruto/frames/manifesto.csv.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

from _comum import BRUTO, fontes

PASTA_VIDEOS = BRUTO / "videos"
PASTA_FRAMES = BRUTO / "frames"


def baixar_youtube(url: str) -> Path:
    import yt_dlp

    PASTA_VIDEOS.mkdir(parents=True, exist_ok=True)
    opcoes = {
        # arquivo único mp4 até 720p: não precisa de ffmpeg para juntar áudio e vídeo
        "format": "best[ext=mp4][height<=720]/best[ext=mp4]/best",
        "outtmpl": str(PASTA_VIDEOS / "%(id)s.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(url, download=True)
        return Path(ydl.prepare_filename(info))


def extrair(video: Path, a_cada: float, maximo: int | None, origem: str) -> int:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        print(f"não abriu: {video}")
        return 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    passo = max(1, int(round(fps * a_cada)))
    destino = PASTA_FRAMES / video.stem
    destino.mkdir(parents=True, exist_ok=True)

    salvos, i, anterior = 0, 0, None
    manifesto = PASTA_FRAMES / "manifesto.csv"
    novo = not manifesto.exists()
    with open(manifesto, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(["arquivo", "origem", "segundo"])
        while True:
            ok = cap.grab()
            if not ok:
                break
            if i % passo == 0:
                ok, frame = cap.retrieve()
                if not ok:
                    break
                mini = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (64, 36))
                if anterior is None or float(np.abs(mini.astype(int) - anterior).mean()) > 6:
                    nome = f"{video.stem}_{i:07d}.jpg"
                    cv2.imwrite(str(destino / nome), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                    w.writerow([f"{video.stem}/{nome}", origem, round(i / fps, 1)])
                    salvos += 1
                    anterior = mini.astype(int)
                    if maximo and salvos >= maximo:
                        break
            i += 1
    cap.release()
    print(f"{salvos:4d} frames  <- {origem}")
    return salvos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fonte", action="append", help="arquivo de vídeo ou URL (pode repetir)")
    ap.add_argument("--a-cada", type=float, default=1.5, help="segundos entre frames")
    ap.add_argument("--max", type=int, default=None, help="máximo de frames por vídeo")
    args = ap.parse_args()

    fontes_videos = args.fonte or fontes().get("videos") or []
    if not fontes_videos:
        print("Passe --fonte ou preencha `videos` em configs/fontes.yaml")
        return 1
    total = 0
    for fonte in fontes_videos:
        try:
            video = baixar_youtube(fonte) if fonte.startswith("http") else Path(fonte)
            total += extrair(video, args.a_cada, args.max, fonte)
        except Exception as e:
            print(f"falhou {fonte}: {e}")
    print(f"\n{total} frames em {PASTA_FRAMES}. Próximo passo: python scripts/deduplicar.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
