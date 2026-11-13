"""Coleta imagens da internet com LICENÇA ABERTA e registra autor e licença de cada uma.

    python scripts/coletar_web.py                       # termos de configs/fontes.yaml
    python scripts/coletar_web.py --termo "broken street light" --max 100
    python scripts/coletar_web.py --incluir-nd          # aceita também licenças "sem derivação"

Fontes (APIs oficiais, sem chave):
- Openverse (api.openverse.org): agrega Flickr, Wikimedia e outros acervos Creative Commons.
- Wikimedia Commons (commons.wikimedia.org): acervo livre da Wikipédia.

Por que não raspar o Google/Bing: viola os termos de uso, traz muito lixo (apostila, desenho,
Pinterest) e as imagens não têm licença conhecida. Aqui toda imagem tem autor e licença no
manifesto, o que permite citar no relatório e, no futuro, usar o modelo em produção.

Imagens que você salvar à mão (ex.: foto de matéria de jornal) vão em data/bruto/web/manual/
com a fonte anotada em data/bruto/web/manual/fontes.csv. Elas não vão para o Git.

Saída: data/bruto/web/<fonte>/ + data/bruto/web/manifesto.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import time
from pathlib import Path

import httpx

from _comum import BRUTO, fontes

PASTA_WEB = BRUTO / "web"
MANIFESTO = PASTA_WEB / "manifesto.csv"
CABECALHO = ["arquivo", "fonte", "termo", "titulo", "autor", "licenca", "url_licenca", "pagina", "url_imagem"]
# Wikimedia exige User-Agent identificável com um link de contato (política de robôs)
HEADERS = {"User-Agent": "GS-CitizenTech-RuasEscuras/1.0 "
                         "(https://github.com/guilhermedaher10/Global-Solution_CitzenTech_2026) httpx"}
LADO_MINIMO = 320


def _sem_derivacao(licenca: str) -> bool:
    import re
    return re.search(r"(^|[-\s])nd($|[-\s])", licenca.lower()) is not None


def buscar_openverse(cliente: httpx.Client, termo: str, maximo: int):
    pagina = 1
    entregues = 0
    while entregues < maximo:
        r = cliente.get("https://api.openverse.org/v1/images/",
                        params={"q": termo, "page_size": 20, "page": pagina, "mature": "false"})
        if r.status_code != 200:
            break
        dados = r.json()
        for x in dados.get("results", []):
            if (x.get("width") or 0) < LADO_MINIMO or (x.get("height") or 0) < LADO_MINIMO:
                continue
            lic = f"cc-{x['license']}" + (f" {x['license_version']}" if x.get("license_version") else "")
            yield {"fonte": f"openverse-{x.get('source', '')}", "titulo": x.get("title") or "",
                   "autor": x.get("creator") or "", "licenca": lic, "url_licenca": x.get("license_url") or "",
                   "pagina": x.get("foreign_landing_url") or "", "url_imagem": x["url"]}
            entregues += 1
            if entregues >= maximo:
                return
        if pagina >= (dados.get("page_count") or 0):
            break
        pagina += 1
        time.sleep(1)  # API anônima tem limite de requisições


def buscar_wikimedia(cliente: httpx.Client, termo: str, maximo: int):
    continuar: dict = {}
    entregues = 0
    while entregues < maximo:
        params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": termo,
                  "gsrnamespace": 6, "gsrlimit": 50, "prop": "imageinfo",
                  "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1280, **continuar}
        r = cliente.get("https://commons.wikimedia.org/w/api.php", params=params)
        if r.status_code != 200:
            break
        dados = r.json()
        for pg in (dados.get("query", {}).get("pages") or {}).values():
            ii = (pg.get("imageinfo") or [{}])[0]
            if ii.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
                continue
            if min(ii.get("width", 0), ii.get("height", 0)) < LADO_MINIMO:
                continue
            meta = ii.get("extmetadata", {})
            val = lambda k: (meta.get(k) or {}).get("value", "")  # noqa: E731
            yield {"fonte": "wikimedia", "titulo": pg.get("title", ""),
                   "autor": _texto_puro(val("Artist")), "licenca": val("LicenseShortName"),
                   "url_licenca": val("LicenseUrl"), "pagina": ii.get("descriptionurl", ""),
                   "url_imagem": ii.get("thumburl") or ii.get("url")}
            entregues += 1
            if entregues >= maximo:
                return
        if "continue" not in dados:
            break
        continuar = dados["continue"]


def _texto_puro(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", html or "").strip()[:200]


def ja_baixadas() -> set[str]:
    if not MANIFESTO.exists():
        return set()
    with open(MANIFESTO, encoding="utf-8") as f:
        return {linha["url_imagem"] for linha in csv.DictReader(f)}


def baixar(cliente: httpx.Client, item: dict, termo: str) -> dict | None:
    try:
        r = cliente.get(item["url_imagem"], follow_redirects=True)
        tipo = r.headers.get("content-type", "")
        if r.status_code != 200 or not tipo.startswith("image/") or len(r.content) < 10_000:
            return None
    except httpx.HTTPError:
        return None
    ext = {"image/png": ".png", "image/webp": ".webp"}.get(tipo.split(";")[0], ".jpg")
    nome = hashlib.sha256(item["url_imagem"].encode()).hexdigest()[:16] + ext
    pasta = PASTA_WEB / item["fonte"].split("-")[0]
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_bytes(r.content)
    return {"arquivo": f"{pasta.name}/{nome}", "termo": termo, **item}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--termo", action="append", help="termo de busca (pode repetir); padrão: fontes.yaml")
    ap.add_argument("--max", type=int, default=120, help="máximo de imagens por termo e por fonte")
    ap.add_argument("--fonte", choices=["openverse", "wikimedia", "todas"], default="todas")
    ap.add_argument("--incluir-nd", action="store_true", help="aceitar licenças sem derivação (ND)")
    args = ap.parse_args()

    termos = args.termo or fontes().get("busca_web", [])
    buscadores = {"openverse": buscar_openverse, "wikimedia": buscar_wikimedia}
    if args.fonte != "todas":
        buscadores = {args.fonte: buscadores[args.fonte]}

    PASTA_WEB.mkdir(parents=True, exist_ok=True)
    vistas = ja_baixadas()
    novo = not MANIFESTO.exists()
    total = 0
    with httpx.Client(headers=HEADERS, timeout=30) as cliente, \
            open(MANIFESTO, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CABECALHO)
        if novo:
            w.writeheader()
        for termo in termos:
            for nome_fonte, buscar in buscadores.items():
                n = 0
                try:
                    for item in buscar(cliente, termo, args.max):
                        if item["url_imagem"] in vistas:
                            continue
                        if not args.incluir_nd and _sem_derivacao(item["licenca"]):
                            continue
                        vistas.add(item["url_imagem"])
                        linha = baixar(cliente, item, termo)
                        if linha:
                            w.writerow(linha)
                            n += 1
                except httpx.HTTPError as e:
                    print(f"  [{nome_fonte}] erro de rede: {e}")
                f.flush()
                total += n
                print(f"{n:4d}  {nome_fonte:10} {termo}")
    print(f"\n{total} imagens novas em {PASTA_WEB} (autor e licença em manifesto.csv)."
          "\nPróximo passo: python scripts/deduplicar.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
