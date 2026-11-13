"""Gera o QR Code do Vésper (web/qr.svg): aponte a câmera do celular e a câmera ao vivo do site abre.

    python scripts/gerar_qr.py                      # URL pública da Azure
    python scripts/gerar_qr.py --url https://...    # outra URL

Para cartazes em pontos da cidade, dá para fixar o local no QR:
    python scripts/gerar_qr.py --lat -23.5614 --lon -46.6559 --ref "Praça X" --saida cartaz.svg
O site abre já com o local marcado (o cidadão só filma e envia).
"""
import argparse
from pathlib import Path
from urllib.parse import urlencode

import segno

URL = "https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io/"

ap = argparse.ArgumentParser()
ap.add_argument("--url", default=URL)
ap.add_argument("--lat", type=float)
ap.add_argument("--lon", type=float)
ap.add_argument("--ref", help="nome do ponto (aparece como endereço)")
ap.add_argument("--saida", default=str(Path(__file__).resolve().parent.parent / "web" / "qr.svg"))
a = ap.parse_args()

q = {}
if a.lat is not None and a.lon is not None:
    q = {"lat": a.lat, "lon": a.lon, **({"ref": a.ref} if a.ref else {})}
destino = a.url + (f"?{urlencode(q)}" if q else "") + "#agora"
segno.make(destino, error="m").save(a.saida, scale=8, border=2, dark="#0a1e13", light="#e7f3ec")
print(destino, "->", a.saida)
