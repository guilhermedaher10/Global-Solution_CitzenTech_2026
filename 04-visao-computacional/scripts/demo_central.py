"""Popula a central para a DEMONSTRAÇÃO (vídeo): vários moradores de um bairro relatam o escuro ao mesmo tempo.

    python scripts/demo_central.py                                   # API local (localhost:8000)
    python scripts/demo_central.py --url https://<sua-url>           # produção
    python scripts/demo_central.py --url https://<sua-url> --limpar  # zera antes (precisa CENTRAL_TOKEN no .env)

Envia as fotos de apagão do conjunto de teste (licença aberta) com coordenadas sorteadas a até ~200 m de um ponto
do Capão Redondo. Em segundos, a central mostra "Possível apagão em Capão Redondo", encaminhado à Enel.
Os chamados são de demonstração: use --limpar depois da gravação.
"""
import argparse
import os
import random
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--lat", type=float, default=-23.6655)
    ap.add_argument("--lon", type=float, default=-46.7790)
    ap.add_argument("--bairro", default="Capão Redondo")
    ap.add_argument("--limpar", action="store_true")
    a = ap.parse_args()
    url = a.url.rstrip("/")
    if a.limpar:
        from dotenv import dotenv_values   # python-dotenv (requirements-dados.txt)
        token = os.getenv("CENTRAL_TOKEN") or dotenv_values(RAIZ / ".env").get("CENTRAL_TOKEN")
        r = httpx.post(f"{url}/v1/central/limpar", headers={"Authorization": f"Bearer {token}"}, timeout=60)
        print("limpar:", r.status_code, r.text)
    random.seed(7)
    fotos = sorted((RAIZ / "data/cena/dataset/test/apagao").glob("*"))
    if not fotos:
        raise SystemExit("rode antes scripts/montar_dataset_cena.py (as fotos de teste ficam em data/cena/)")
    for i, f in enumerate(fotos, 1):
        lat, lon = a.lat + random.uniform(-0.0018, 0.0018), a.lon + random.uniform(-0.0018, 0.0018)
        with open(f, "rb") as fh:
            r = httpx.post(f"{url}/v1/analisar", timeout=120, files={"imagem": (f.name, fh, "image/jpeg")},
                           data={"latitude": lat, "longitude": lon, "endereco": f"Rua {i} · {a.bairro} · São Paulo"})
        r.raise_for_status()
        x = r.json()
        print(f"{i:2d} {x.get('protocolo') or '(sem chamado)':11s} cena={x['cena']['classe']:13s} "
              f"apagão={x['cena']['possivel_apagao']}")
    for reg in httpx.get(f"{url}/v1/regioes", timeout=60).json():
        print("REGIÃO:", reg["titulo"], f"({reg['relatos']} chamados, {reg['sinais_apagao']} sem nenhuma luz)")
