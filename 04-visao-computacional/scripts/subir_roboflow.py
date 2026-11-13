"""Sobe as imagens pré-anotadas (data/anotar_yolo/) para um projeto do Roboflow, para revisão.

    python scripts/subir_roboflow.py --projeto ruas-escuras-postes --criar
    python scripts/subir_roboflow.py --projeto ruas-escuras-postes          # continua um upload

As caixas sugeridas pelo modelo-base sobem junto: no Roboflow você só corrige (Annotate).
Imagens já enviadas são puladas (o Roboflow deduplica pelo conteúdo).
Depois da revisão: Generate → Export "YOLOv8" → descompacte em data/anotado/.
"""
from __future__ import annotations

import argparse
import os
import sys

from _comum import DATA, carregar_env, listar_imagens
from visao.config import classes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projeto", default="ruas-escuras-postes")
    ap.add_argument("--criar", action="store_true", help="cria o projeto se ainda não existir")
    ap.add_argument("--pasta", default=str(DATA / "anotar_yolo"))
    ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--lote", default="web-pre-anotado", help="nome do lote (batch) no Roboflow")
    ap.add_argument("--tag", default="web")
    args = ap.parse_args()

    carregar_env()
    chave = os.getenv("ROBOFLOW_API_KEY")
    if not chave:
        print("Defina ROBOFLOW_API_KEY no .env")
        return 1

    from roboflow import Roboflow

    ws = Roboflow(api_key=chave).workspace()
    existentes = {p.split("/")[-1] for p in ws.projects()}
    if args.projeto not in existentes:
        if not args.criar:
            print(f"Projeto '{args.projeto}' não existe. Use --criar.")
            return 1
        ws.create_project(project_name=args.projeto, project_type="object-detection",
                          project_license="CC BY 4.0", annotation="postes")
        print(f"Projeto criado: {args.projeto}")
    projeto = ws.project(args.projeto)

    pasta = __import__("pathlib").Path(args.pasta)
    mapa = dict(enumerate(classes()))
    imagens = listar_imagens(pasta / "images")[: args.max]
    ok = falhas = 0
    for i, img in enumerate(imagens, 1):
        label = pasta / "labels" / f"{img.stem}.txt"
        try:
            projeto.single_upload(image_path=str(img),
                                  annotation_path=str(label) if label.exists() and label.stat().st_size else None,
                                  annotation_labelmap=mapa, split="train", batch_name=args.lote,
                                  tag_names=[args.tag], num_retry_uploads=2,
                                  annotation_overwrite=True)
            ok += 1
        except Exception as e:
            falhas += 1
            print(f"  falhou {img.name}: {e}")
        if i % 25 == 0:
            print(f"{i}/{len(imagens)}", flush=True)

    print(f"\n{ok} enviadas, {falhas} falhas. Revise em https://app.roboflow.com/{ws.url}/{args.projeto}/annotate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
