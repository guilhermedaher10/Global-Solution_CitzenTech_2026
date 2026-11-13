"""Avalia a leitura de CENA por cenário: regras (cena.py) x classificador (YOLO26-cls) x fusão.

    python scripts/avaliar_cena.py --modelo runs/cena/cls_n/weights/best.pt

Conjuntos (nunca vistos no treino):
  test          imagens com licença aberta, separadas pelo hash antes do treino
  teste_equipe  fotos noturnas da equipe (São Paulo e arredores): o "mundo real"

Para cada abordagem: acurácia, precisão/recall por classe e matriz de confusão (linhas = verdade).
Saída: results/cena/avaliacao.json + matrizes em PNG. As regras são mapeadas assim:
  possivel_apagao -> apagao · muito_escura/breu -> trecho_escuro · iluminada/pouca_iluminacao -> iluminada
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from visao.cena import analisar_cena  # noqa: E402
from visao.classificador_cena import fundir_cena  # noqa: E402

CLASSES = ["iluminada", "trecho_escuro", "apagao"]


def regra(c) -> str:
    if c.possivel_apagao:
        return "apagao"
    return "trecho_escuro" if c.nivel.value in ("muito_escura", "breu") else "iluminada"


def metricas(verdade, pred):
    m = np.zeros((3, 3), int)
    for v, p in zip(verdade, pred):
        m[CLASSES.index(v), CLASSES.index(p)] += 1
    por = {}
    for i, c in enumerate(CLASSES):
        tp, fp, fn = m[i, i], m[:, i].sum() - m[i, i], m[i, :].sum() - m[i, i]
        por[c] = {"precisao": round(tp / (tp + fp), 3) if tp + fp else None,
                  "recall": round(tp / (tp + fn), 3) if tp + fn else None, "n": int(m[i].sum())}
    return {"acuracia": round(np.trace(m) / m.sum(), 3), "por_classe": por, "matriz": m.tolist()}


def desenhar(m, titulo, caminho):
    m = np.array(m)
    cel, mx, my = 110, 170, 70
    img = np.full((my + cel * 3 + 60, mx + cel * 3 + 20, 3), 255, np.uint8)
    cv2.putText(img, titulo, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 40, 25), 2)
    for i in range(3):
        cv2.putText(img, CLASSES[i], (10, my + i * cel + cel // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 40, 25), 1)
        cv2.putText(img, CLASSES[i][:9], (mx + i * cel + 8, my + cel * 3 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 40, 25), 1)
        tot = max(1, m[i].sum())
        for j in range(3):
            f = m[i, j] / tot
            cor = (int(255 - 150 * f), int(255 - 60 * f), int(255 - 150 * f))
            x, y = mx + j * cel, my + i * cel
            cv2.rectangle(img, (x, y), (x + cel - 4, y + cel - 4), cor, -1)
            cv2.putText(img, str(m[i, j]), (x + 40, y + 62), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (10, 30, 15), 2)
    cv2.putText(img, "linhas = verdade, colunas = previsto", (10, img.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (90, 90, 90), 1)
    cv2.imwrite(str(caminho), img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="models/cena.pt")
    ap.add_argument("--saida", default="results/cena")
    a = ap.parse_args()
    from ultralytics import YOLO
    clf = YOLO(a.modelo)
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    resultado, erros = {}, []
    for nome, pasta in [("test", Path("data/cena/dataset/test")), ("teste_equipe", Path("data/cena/teste_equipe"))]:
        verdade, pr, pc, pf = [], [], [], []
        for classe in CLASSES:
            for p in sorted((pasta / classe).glob("*")):
                img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
                cena = analisar_cena(img)
                r = clf.predict(img, verbose=False, imgsz=320)[0]
                probs = {clf.names[i]: float(v) for i, v in enumerate(r.probs.data.tolist())}
                verdade.append(classe)
                pr.append(regra(cena))
                pc.append(max(probs, key=probs.get))
                pf.append(fundir_cena(cena, probs).classe)
                if pf[-1] != classe:
                    erros.append({"conjunto": nome, "arquivo": p.name, "verdade": classe, "fusao": pf[-1],
                                  "regra": pr[-1], "classificador": pc[-1]})
        resultado[nome] = {k: metricas(verdade, v) for k, v in
                           [("regras", pr), ("classificador", pc), ("fusao", pf)]}
        for k in ("regras", "classificador", "fusao"):
            desenhar(resultado[nome][k]["matriz"], f"{nome} - {k} (acuracia {resultado[nome][k]['acuracia']:.0%})",
                     saida / f"matriz_{nome}_{k}.png")
    (saida / "avaliacao.json").write_text(json.dumps({"resultado": resultado, "erros_fusao": erros},
                                                     ensure_ascii=False, indent=2), encoding="utf-8")
    for nome, r in resultado.items():
        print(f"\n== {nome}")
        for k, v in r.items():
            pc = " · ".join(f"{c}: P {x['precisao']} R {x['recall']} (n={x['n']})" for c, x in v["por_classe"].items())
            print(f"  {k:14s} acurácia {v['acuracia']:.0%}   {pc}")


if __name__ == "__main__":
    main()
