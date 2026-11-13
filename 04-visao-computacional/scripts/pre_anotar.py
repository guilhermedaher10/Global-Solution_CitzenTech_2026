"""Sugere caixas nas imagens de data/anotar/ (pré-anotação) e descarta as que não têm poste.

    python scripts/pre_anotar.py                              # YOLO-World (padrão)
    python scripts/pre_anotar.py --metodo modelo --modelo runs/base/weights/best.pt

Métodos:
- yolo-world (padrão): detector de vocabulário aberto da Ultralytics, que acha "street light"
  sem treino. Imagens sem nenhum poste são descartadas (a busca na web traz muito lixo).
  Aceso ou apagado é decidido pelo brilho dentro da caixa:
    cena escura + luminária com pixels quase saturados = aceso; senão = apagado.
- modelo: usa um modelo nosso já treinado (útil a partir da 2ª rodada).

Gera data/anotar_yolo/ (images/ + labels/ + data.yaml). Suba com scripts/subir_roboflow.py
e REVISE todas as caixas: são só sugestões.
"""
from __future__ import annotations

import argparse
import shutil
import sys

import cv2
import numpy as np
import yaml

from _comum import DATA, listar_imagens
from visao.config import CLASSE_ACESO, CLASSE_APAGADO, classes

PROMPTS = ["street light", "street lamp"]
CENA_ESCURA = 110      # brilho médio (0-255) abaixo do qual consideramos noite/entardecer
LUZ_SATURADA = 235     # percentil 99 do brilho dentro da caixa acima disso = lâmpada emitindo luz


def classificar_por_brilho(img: np.ndarray, bbox) -> str:
    x1, y1, x2, y2 = bbox
    v = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 2]
    recorte = v[max(0, y1):y2, max(0, x1):x2]
    if recorte.size == 0:
        return CLASSE_APAGADO
    cena_escura = float(v.mean()) < CENA_ESCURA
    acesa = float(np.percentile(recorte, 99)) > LUZ_SATURADA
    return CLASSE_ACESO if (cena_escura and acesa) else CLASSE_APAGADO


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metodo", choices=["yolo-world", "modelo"], default="yolo-world")
    ap.add_argument("--modelo", default=None, help="para --metodo modelo (padrão: models/best.pt)")
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--manter-sem-poste", action="store_true", help="não descartar imagens sem detecção")
    ap.add_argument("--origem", default=str(DATA / "anotar"), help="pasta com as imagens (busca recursiva)")
    ap.add_argument("--destino", default=str(DATA / "anotar_yolo"))
    ap.add_argument("--so-noite", action="store_true",
                    help=f"descarta cenas claras (brilho médio >= {CENA_ESCURA}): o foco é a rua à noite")
    args = ap.parse_args()

    from pathlib import Path
    origem, destino = Path(args.origem), Path(args.destino)
    if destino.exists():
        shutil.rmtree(destino)
    (destino / "images").mkdir(parents=True)
    (destino / "labels").mkdir(parents=True)
    nossas = classes()

    if args.metodo == "yolo-world":
        from ultralytics import YOLOWorld
        mundo = YOLOWorld("yolov8s-worldv2.pt")
        mundo.set_classes(PROMPTS)

        def detectar(img):
            # agnostic_nms: "street light" e "street lamp" no mesmo poste viram uma caixa só
            r = mundo.predict(img, conf=args.conf, agnostic_nms=True, verbose=False)[0]
            caixas = [tuple(int(round(v)) for v in b.xyxy[0].tolist()) for b in r.boxes]
            h, w = img.shape[:2]
            # caixa cobrindo quase a imagem toda não é luminária: descarta
            caixas = [c for c in caixas if (c[2] - c[0]) * (c[3] - c[1]) < 0.6 * w * h]
            return [(classificar_por_brilho(img, c), c) for c in caixas]
    else:
        from visao.detector import YoloDetector
        det = YoloDetector(args.modelo, conf=args.conf)

        def detectar(img):
            return [(d.classe, tuple(d.bbox)) for d in det.detectar(img)]

    total = mantidas = claras = 0
    contagem = {c: 0 for c in nossas}
    for p in listar_imagens(origem):
        img = cv2.imread(str(p))
        if img is None:
            continue
        total += 1
        if args.so_noite and float(cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 2].mean()) >= CENA_ESCURA:
            claras += 1
            continue
        achados = detectar(img)
        if not achados and not args.manter_sem_poste:
            continue
        h, w = img.shape[:2]
        linhas = []
        for classe, (x1, y1, x2, y2) in achados:
            contagem[classe] += 1
            linhas.append(f"{nossas.index(classe)} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} "
                          f"{(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
        nome = f"{p.parent.name}__{p.stem}"  # pastas diferentes podem repetir nomes ("images (1).jpg")
        nome = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in nome)
        shutil.copy2(p, destino / "images" / f"{nome}{p.suffix.lower()}")
        (destino / "labels" / f"{nome}.txt").write_text("\n".join(linhas))
        mantidas += 1

    with open(destino / "data.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump({"names": nossas, "nc": len(nossas)}, f, allow_unicode=True)
    print(f"{total} imagens analisadas -> {mantidas} mantidas em {destino}"
          + (f" ({claras} descartadas por serem claras)" if args.so_noite else ""))
    print("caixas sugeridas:", ", ".join(f"{k}={v}" for k, v in contagem.items()))
    print("Próximo passo: python scripts/subir_roboflow.py --criar  (e revise TODAS as caixas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
