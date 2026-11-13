"""Pranchas numeradas para rotular CENAS à mão (iluminada / trecho_escuro / apagao / fora).

    python scripts/pranchas_cena.py --origem data/bruto/web/openverse --saida data/cena/pranchas --lote web1

Cada prancha é uma grade 5x4 com o número de cada imagem; o índice (lote.csv) liga número -> arquivo.
Quem rotula olha a prancha e escreve num CSV "numero,classe". Depois, montar_dataset_cena.py copia
cada imagem para data/cena/<split>/<classe>/. Nada daqui vai para o Git (imagens de terceiros).
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

EXT = {".jpg", ".jpeg", ".png", ".webp"}
COLS, LINS, LADO = 5, 4, 256


def ler(p: Path):
    dados = np.fromfile(str(p), dtype=np.uint8)
    return cv2.imdecode(dados, cv2.IMREAD_COLOR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", action="append", default=[])
    ap.add_argument("--termo", action="append", default=[], help="imagens da web deste termo (manifesto.csv)")
    ap.add_argument("--saida", default="data/cena/pranchas")
    ap.add_argument("--lote", required=True)
    a = ap.parse_args()
    arquivos = sorted(p for o in a.origem for p in Path(o).rglob("*") if p.suffix.lower() in EXT)
    if a.termo:
        web = Path("data/bruto/web")
        with open(web / "manifesto.csv", encoding="utf-8") as f:
            arquivos += sorted({web / x["arquivo"] for x in csv.DictReader(f) if x["termo"] in a.termo})
        arquivos = [p for p in arquivos if p.exists()]
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    with open(saida / f"{a.lote}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["numero", "arquivo"])
        validos = []
        for p in arquivos:
            img = ler(p)
            if img is None:
                continue
            validos.append((p, img))
            w.writerow([len(validos), p.as_posix()])
    por = COLS * LINS
    for k in range(0, len(validos), por):
        folha = np.zeros((LINS * (LADO + 22), COLS * LADO, 3), np.uint8)
        for i, (p, img) in enumerate(validos[k:k + por]):
            h, w_ = img.shape[:2]
            e = LADO / max(h, w_)
            mini = cv2.resize(img, (int(w_ * e), int(h * e)), interpolation=cv2.INTER_AREA)
            y, x = (i // COLS) * (LADO + 22), (i % COLS) * LADO
            folha[y + 22:y + 22 + mini.shape[0], x:x + mini.shape[1]] = mini
            cv2.putText(folha, str(k + i + 1), (x + 4, y + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 255, 160), 2)
        cv2.imwrite(str(saida / f"{a.lote}_{k // por + 1:02d}.jpg"), folha, [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(len(validos), "imagens,", (len(validos) + por - 1) // por, "pranchas em", saida)


if __name__ == "__main__":
    main()
