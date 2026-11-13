"""Monta o dataset do CLASSIFICADOR DE CENA a partir dos rótulos feitos nas pranchas.

    python scripts/montar_dataset_cena.py

Entrada: data/cena/pranchas/<lote>.csv (número -> arquivo) + data/cena/rotulos/<lote>.csv (número -> classe).
Saída (formato de classificação do Ultralytics):
    data/cena/dataset/{train,val,test}/{iluminada,trecho_escuro,apagao}/
    data/cena/teste_equipe/{...}/      fotos da equipe: o "mundo real", NUNCA entram no treino

Regras contra vazamento e sujeira:
  - duplicatas por hash perceptual (dHash 64 bits, distância <= 6): a mesma foto em dois lotes vira uma só;
    se os rótulos discordarem, a imagem sai (rótulo duvidoso não ensina nada);
  - o split usa o hash da imagem (estável): rodar de novo dá o mesmo split;
  - fotos da equipe (lote "equipe") só no teste; as que têm marca d'água de jornal nem foram rotuladas.
"""
from __future__ import annotations

import csv
import hashlib
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path("data/cena")
CLASSES = ["iluminada", "trecho_escuro", "apagao"]
LOTES_TESTE = {"equipe"}


def dhash(caminho: Path) -> int | None:
    img = cv2.imdecode(np.fromfile(str(caminho), np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    p = cv2.resize(img, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (p[:, 1:] > p[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def main():
    itens = []   # (hash, classe, arquivo, lote)
    for rot in sorted((RAIZ / "rotulos").glob("*.csv")):
        lote = rot.stem
        with open(RAIZ / "pranchas" / f"{lote}.csv", encoding="utf-8") as f:
            arquivo = {int(x["numero"]): Path(x["arquivo"]) for x in csv.DictReader(f)}
        with open(rot, encoding="utf-8") as f:
            for x in csv.DictReader(f):
                p = arquivo[int(x["numero"])]
                h = dhash(p)
                if h is not None and x["classe"] in CLASSES:
                    itens.append((h, x["classe"], p, lote))

    # agrupa duplicatas (distância de Hamming pequena)
    grupos: list[list] = []
    for it in itens:
        for g in grupos:
            if bin(g[0][0] ^ it[0]).count("1") <= 6:
                g.append(it)
                break
        else:
            grupos.append([it])

    saida = {"dataset": RAIZ / "dataset", "teste_equipe": RAIZ / "teste_equipe"}
    for d in saida.values():
        shutil.rmtree(d, ignore_errors=True)
    contagem, conflitos, repetidas = defaultdict(Counter), 0, 0
    for g in grupos:
        classes = {c for _, c, _, _ in g}
        if len(classes) > 1:
            conflitos += 1
            continue
        repetidas += len(g) - 1
        classe = classes.pop()
        h, _, p, _ = next((x for x in g if x[3] in LOTES_TESTE), g[0])
        if any(x[3] in LOTES_TESTE for x in g):
            destino = saida["teste_equipe"] / classe
            split = "teste_equipe"
        else:
            # MD5 aqui só sorteia o split de forma estável (não protege nada); trocar mudaria o split já avaliado
            r = int(hashlib.md5(str(h).encode(), usedforsecurity=False).hexdigest(), 16) % 100  # nosemgrep: python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5
            split = "train" if r < 70 else "val" if r < 85 else "test"
            destino = saida["dataset"] / split / classe
        destino.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, destino / f"{h:016x}{p.suffix.lower()}")
        contagem[split][classe] += 1

    print(f"{len(itens)} rótulos -> {len(grupos)} imagens únicas ({repetidas} duplicatas juntadas, "
          f"{conflitos} descartadas por rótulos em conflito)")
    for split in ["train", "val", "test", "teste_equipe"]:
        print(f"  {split:13s}", dict(contagem[split]))


if __name__ == "__main__":
    main()
