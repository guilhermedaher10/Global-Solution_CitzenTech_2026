"""Gera fotos SINTETICAS de exemplo (rua escura + poste) em data/fotos/<id_captura>.jpg.

Sao imagens desenhadas, sem pessoas nem placas. O chamado C-009 fica sem foto de proposito,
para exercitar o tratamento de "foto ausente".
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import contrato  # noqa: E402

DESTINO = RAIZ / "data" / "fotos"
EVENTOS = RAIZ / "data" / "visao_exemplos.jsonl"
SEM_FOTO = {"C-009"}


def desenhar(rotulo: str, destino: Path) -> None:
    w, h = 800, 600
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):  # ceu noturno em degrade
        c = int(10 + 30 * y / h)
        d.line([(0, y), (w, y)], fill=(c, c, c + 15))
    d.rectangle([0, 430, w, h], fill=(25, 25, 28))        # rua
    d.rectangle([0, 425, w, 435], fill=(45, 45, 50))      # calcada
    d.rectangle([395, 150, 405, 430], fill=(60, 60, 65))  # poste
    d.rectangle([395, 150, 470, 158], fill=(60, 60, 65))  # braco
    d.ellipse([455, 150, 485, 175], fill=(35, 35, 38))    # lampada apagada
    d.text((20, 20), f"EXEMPLO SINTETICO - {rotulo}", fill=(180, 180, 180))
    im.save(destino, "JPEG", quality=85)


if __name__ == "__main__":
    DESTINO.mkdir(parents=True, exist_ok=True)
    ids = [e["id_captura"] for e in contrato.ler_eventos(EVENTOS)]
    gerados = [i for i in ids if i not in SEM_FOTO]
    for i in gerados:
        desenhar(i, DESTINO / f"{i}.jpg")
    print(f"{len(gerados)} fotos geradas em {DESTINO}")
