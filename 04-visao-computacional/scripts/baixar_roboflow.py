"""Baixa os datasets do Roboflow Universe listados em configs/fontes.yaml (formato YOLO).

    python scripts/baixar_roboflow.py

Precisa de ROBOFLOW_API_KEY no .env (conta grátis em roboflow.com).
"""
from __future__ import annotations

import os
import sys

from _comum import BRUTO, carregar_env, fontes


def main() -> int:
    carregar_env()
    chave = os.getenv("ROBOFLOW_API_KEY")
    if not chave:
        print("Defina ROBOFLOW_API_KEY no arquivo .env (veja .env.example).")
        return 1

    from roboflow import Roboflow

    rf = Roboflow(api_key=chave)
    ok, falhas = [], []
    for item in fontes().get("roboflow", []):
        ws, proj = item["workspace"], item["projeto"]
        destino = BRUTO / "roboflow" / proj
        try:
            projeto = rf.workspace(ws).project(proj)
            n = item.get("versao")
            if n is None:
                versoes = projeto.versions()
                if not versoes:
                    raise RuntimeError("projeto sem versão publicada")
                n = max(int(str(v.version).split("/")[-1]) for v in versoes)
            print(f"-> {ws}/{proj} v{n}")
            projeto.version(int(n)).download("yolov8", location=str(destino), overwrite=True)
            ok.append(f"{ws}/{proj} v{n}")
        except Exception as e:  # um dataset fora do ar não pode parar os outros
            falhas.append(f"{ws}/{proj}: {e}")

    print(f"\nBaixados ({len(ok)}):", *ok, sep="\n  ")
    if falhas:
        print(f"\nFalharam ({len(falhas)}):", *falhas, sep="\n  ")
    print("\nPróximo passo: python scripts/unificar_dataset.py --listar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
