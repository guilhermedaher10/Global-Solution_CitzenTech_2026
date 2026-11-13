"""Avalia um ou mais modelos no conjunto de TESTE e gera a tabela comparativa do relatório.

    python scripts/avaliar.py                                       # models/best.pt
    python scripts/avaliar.py --modelo runs/yolo26n/weights/best.pt --modelo runs/yolo26s/weights/best.pt

Saída: results/metricas.md e results/metricas.json (mAP50, mAP50-95, precisão, recall, por classe, FPS).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _comum import DATA, RAIZ


def avaliar(caminho: str, dados: str, device: str | None) -> dict:
    from ultralytics import YOLO

    model = YOLO(caminho)
    m = model.val(data=dados, split="test", device=device, plots=False, verbose=False)
    por_classe = {}
    for i, idx in enumerate(m.box.ap_class_index):
        nome = m.names[int(idx)]
        p, r, ap50, ap = m.box.class_result(i)
        por_classe[nome] = {"precisao": round(float(p), 3), "recall": round(float(r), 3),
                            "map50": round(float(ap50), 3), "map50_95": round(float(ap), 3)}
    ms = m.speed.get("inference", 0.0)
    return {
        "modelo": caminho,
        "map50": round(float(m.box.map50), 3),
        "map50_95": round(float(m.box.map), 3),
        "precisao": round(float(m.box.mp), 3),
        "recall": round(float(m.box.mr), 3),
        "ms_por_imagem": round(float(ms), 1),
        "fps_estimado": round(1000 / ms, 0) if ms else None,
        "por_classe": por_classe,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", action="append", help="pode repetir; padrão: models/best.pt")
    ap.add_argument("--dados", default=str(DATA / "final" / "data.yaml"))
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    modelos = args.modelo or [str(RAIZ / "models" / "best.pt")]
    resultados = [avaliar(m, args.dados, args.device) for m in modelos]

    linhas = ["# Métricas no conjunto de teste", "",
              "| Modelo | mAP50 | mAP50-95 | Precisão | Recall | ms/img | FPS |", "|---|---|---|---|---|---|---|"]
    for r in resultados:
        nome = Path(r["modelo"]).parent.parent.name if "runs" in r["modelo"] else Path(r["modelo"]).stem
        linhas.append(f"| {nome} | {r['map50']} | {r['map50_95']} | {r['precisao']} | {r['recall']} | "
                      f"{r['ms_por_imagem']} | {r['fps_estimado']} |")
    linhas += ["", "## Por classe", "", "| Modelo | Classe | Precisão | Recall | mAP50 | mAP50-95 |",
               "|---|---|---|---|---|---|"]
    for r in resultados:
        nome = Path(r["modelo"]).parent.parent.name if "runs" in r["modelo"] else Path(r["modelo"]).stem
        for c, v in r["por_classe"].items():
            linhas.append(f"| {nome} | {c} | {v['precisao']} | {v['recall']} | {v['map50']} | {v['map50_95']} |")

    (RAIZ / "results").mkdir(exist_ok=True)
    (RAIZ / "results" / "metricas.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    (RAIZ / "results" / "metricas.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False))
    print("\n".join(linhas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
