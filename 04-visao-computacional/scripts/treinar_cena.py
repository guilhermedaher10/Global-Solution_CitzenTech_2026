"""Treina o classificador de CENA (YOLO26-cls) no dataset de montar_dataset_cena.py.

    python scripts/treinar_cena.py                  # yolo26n-cls, 320 px
    python scripts/treinar_cena.py --modelo yolo26s-cls.pt --nome cls_s

Depois: python scripts/avaliar_cena.py --modelo runs/cena/<nome>/weights/best.pt
e, se for melhor, copie para models/cena.pt.
"""
import argparse
from pathlib import Path

from ultralytics import YOLO

RAIZ = Path(__file__).resolve().parent.parent

if __name__ == "__main__":   # obrigatório no Windows: os workers reimportam este arquivo
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="yolo26n-cls.pt")
    ap.add_argument("--nome", default="cls_n")
    ap.add_argument("--epocas", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=320)
    a = ap.parse_args()
    YOLO(a.modelo).train(data=str(RAIZ / "data/cena/dataset"), epochs=a.epocas, imgsz=a.imgsz, batch=32,
                         patience=20, project=str(RAIZ / "runs/cena"), name=a.nome, exist_ok=True,
                         seed=0, deterministic=True, workers=0, plots=True, verbose=False)
