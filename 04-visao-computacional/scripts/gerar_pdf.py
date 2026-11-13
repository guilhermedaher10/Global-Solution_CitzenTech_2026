"""Gera um PDF A4 a partir de um relatório HTML (Chrome headless via Playwright).

    python scripts/gerar_pdf.py docs/relatorio/relatorio-visao.html docs/Relatorio-Visao-Computacional.pdf

Imprime também os contadores de palavras do resumo e do objetivo (limites da FIAP: 250 e 50).
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

if __name__ == "__main__":
    origem, destino = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    with sync_playwright() as pw:
        kw = {"executable_path": CHROME} if Path(CHROME).exists() else {}
        nav = pw.chromium.launch(**kw)
        pg = nav.new_page()
        pg.goto(origem.as_uri(), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        for c in pg.locator(".contador").all():
            print(c.text_content())
        pg.pdf(path=str(destino), format="A4", print_background=True, prefer_css_page_size=True,
               display_header_footer=True, header_template="<span></span>",
               footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#6b7b71">'
                               'Vésper · FIAP GS 2026.2 · <span class="pageNumber"></span>/<span class="totalPages"></span></div>')
        nav.close()
    print("PDF:", destino)
