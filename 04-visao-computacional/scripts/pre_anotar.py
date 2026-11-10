"""Usa o modelo atual para sugerir caixas nas imagens de data/anotar/ (pré-anotação).

    python scripts/pre_anotar.py --conf 0.25

Gera data/anotar_yolo/ (images/ + labels/ + data.yaml). Suba essa pasta no Roboflow:
as caixas aparecem prontas e você só corrige. Corta o tempo de anotação pela metade.
Primeiro treine um modelo-base só com os datasets do Roboflow.
"""
from __future__ import annotations

import argparse
import shutil
import sys

import cv2
import yaml

from _comum import DATA, listar_imagens
from visao.config import classes
from visao.detector import YoloDetector


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", default=None, help="padrão: models/best.pt")
    ap.add_argument("--conf", type=float, default=0.25)
    args = ap.parse_args()

    origem = DATA / "anotar"
    destino = DATA / "anotar_yolo"
    (destino / "images").mkdir(parents=True, exist_ok=True)
    (destino / "labels").mkdir(parents=True, exist_ok=True)
    det = YoloDetector(args.modelo, conf=args.conf)
    nossas = classes()

    n_img = n_cx = 0
    for p in listar_imagens(origem):
        img = cv2.imread(str(p))
        if img is None:
            continue
        h, w = img.shape[:2]
        linhas = []
        for d in det.detectar(img):
            x1, y1, x2, y2 = d.bbox
            linhas.append(f"{nossas.index(d.classe)} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} "
                          f"{(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
        shutil.copy2(p, destino / "images" / p.name)
        (destino / "labels" / f"{p.stem}.txt").write_text("\n".join(linhas))
        n_img += 1
        n_cx += len(linhas)

    with open(destino / "data.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump({"names": nossas, "nc": len(nossas)}, f, allow_unicode=True)
    print(f"{n_img} imagens, {n_cx} caixas sugeridas em {destino}. Suba no Roboflow e revise TODAS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
