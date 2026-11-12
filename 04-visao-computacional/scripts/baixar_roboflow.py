"""Baixa os datasets do Roboflow Universe listados em configs/fontes.yaml (formato YOLO).

    python scripts/baixar_roboflow.py
    python scripts/baixar_roboflow.py --projeto street-light-off     # só um

Precisa de ROBOFLOW_API_KEY no .env (conta grátis em roboflow.com).

Usa a API REST do Roboflow e extrai o zip por conta própria, encurtando nomes de arquivo
enormes (alguns passam de 230 caracteres e estouram o limite de caminho do Windows).
Imagem e label recebem o mesmo nome curto, então o par continua casado.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import shutil
import sys
import time
import zipfile
from pathlib import PurePosixPath

import httpx

from _comum import BRUTO, carregar_env, fontes

API = "https://api.roboflow.com"
MAX_NOME = 60


def nome_curto(stem: str) -> str:
    if len(stem) <= MAX_NOME:
        return stem
    return f"{stem[:40]}_{hashlib.sha256(stem.encode()).hexdigest()[:10]}"


def link_export(cliente: httpx.Client, ws: str, proj: str, versao: int, chave: str) -> str:
    """Pede o export YOLO; se o Roboflow ainda estiver gerando, espera."""
    for _ in range(60):
        r = cliente.get(f"{API}/{ws}/{proj}/{versao}/yolov8", params={"api_key": chave})
        r.raise_for_status()
        j = r.json()
        link = (j.get("export") or {}).get("link")
        if link:
            return link
        time.sleep(5)
    raise TimeoutError("export não ficou pronto em 5 minutos")


def extrair(dados: bytes, destino) -> int:
    if destino.exists():
        shutil.rmtree(destino)
    n = 0
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            rel = PurePosixPath(info.filename)
            if ".." in rel.parts or rel.is_absolute():  # zip malicioso
                continue
            if rel.parent.name in ("images", "labels"):
                rel = rel.with_name(nome_curto(rel.stem) + rel.suffix)
                n += rel.parent.name == "images"
            alvo = destino.joinpath(*rel.parts)
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_bytes(z.read(info))
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projeto", action="append", help="baixa só este(s) projeto(s) de fontes.yaml")
    args = ap.parse_args()

    carregar_env()
    chave = os.getenv("ROBOFLOW_API_KEY")
    if not chave:
        print("Defina ROBOFLOW_API_KEY no arquivo .env (veja .env.example).")
        return 1

    ok, falhas = [], []
    with httpx.Client(timeout=120, follow_redirects=True) as cliente:
        for item in fontes().get("roboflow", []):
            ws, proj = item["workspace"], item["projeto"]
            if args.projeto and proj not in args.projeto:
                continue
            try:
                n = item.get("versao")
                if n is None:
                    r = cliente.get(f"{API}/{ws}/{proj}", params={"api_key": chave})
                    r.raise_for_status()
                    versoes = r.json().get("versions") or []
                    if not versoes:
                        raise RuntimeError("projeto sem versão publicada")
                    n = max(int(v["id"].split("/")[-1]) for v in versoes)
                print(f"-> {ws}/{proj} v{n}", flush=True)
                zipdata = cliente.get(link_export(cliente, ws, proj, int(n), chave)).content
                imgs = extrair(zipdata, BRUTO / "roboflow" / proj)
                ok.append(f"{ws}/{proj} v{n}: {imgs} imagens")
            except Exception as e:  # um dataset fora do ar não pode parar os outros
                falhas.append(f"{ws}/{proj}: {e}")

    print(f"\nBaixados ({len(ok)}):", *ok, sep="\n  ")
    if falhas:
        print(f"\nFalharam ({len(falhas)}):", *falhas, sep="\n  ")
    print("\nPróximo passo: python scripts/unificar_dataset.py --listar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
