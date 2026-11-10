"""Junta imagens da web e dos frames, remove repetidas e pequenas, e prepara data/anotar/.

    python scripts/deduplicar.py
    python scripts/deduplicar.py --distancia 6 --lado-minimo 320

Usa hash perceptual (pHash): duas imagens com distância <= --distancia são consideradas a mesma
(mesmo que redimensionadas ou recomprimidas). Também descarta imagens que já estão nos datasets
do Roboflow, para a mesma foto não cair no treino e no teste ao mesmo tempo.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys

from PIL import Image

from _comum import BRUTO, DATA, listar_imagens

DESTINO = DATA / "anotar"


def phash(caminho):
    import imagehash
    try:
        with Image.open(caminho) as img:
            return imagehash.phash(img.convert("RGB")), min(img.size)
    except Exception:
        return None, 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--distancia", type=int, default=6)
    ap.add_argument("--lado-minimo", type=int, default=320)
    args = ap.parse_args()

    referencia = []
    for p in listar_imagens(BRUTO / "roboflow"):
        h, _ = phash(p)
        if h is not None:
            referencia.append(h)

    candidatos = listar_imagens(BRUTO / "web") + listar_imagens(BRUTO / "frames")
    DESTINO.mkdir(parents=True, exist_ok=True)
    mantidos, motivos = [], {"pequena": 0, "corrompida": 0, "repetida": 0, "ja_no_roboflow": 0}

    for p in candidatos:
        h, lado = phash(p)
        if h is None:
            motivos["corrompida"] += 1
            continue
        if lado < args.lado_minimo:
            motivos["pequena"] += 1
            continue
        if any(h - r <= args.distancia for r in referencia):
            motivos["ja_no_roboflow"] += 1
            continue
        if any(h - m <= args.distancia for m, _ in mantidos):
            motivos["repetida"] += 1
            continue
        mantidos.append((h, p))

    with open(DESTINO / "origem.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arquivo", "origem"])
        for _, p in mantidos:
            nome = f"{p.parent.name}__{p.name}"
            shutil.copy2(p, DESTINO / nome)
            w.writerow([nome, str(p.relative_to(BRUTO))])

    print(f"{len(candidatos)} candidatas -> {len(mantidos)} únicas em {DESTINO}")
    for k, v in motivos.items():
        print(f"  descartadas ({k}): {v}")
    print("\nPróximo passo: (opcional) python scripts/pre_anotar.py e depois anotar no Roboflow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
