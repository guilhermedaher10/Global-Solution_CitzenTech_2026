"""Gera exemplos SINTÉTICOS de poste apagado a partir de fotos noturnas com poste aceso.

    python scripts/apagar_lampadas.py --max 300          # gera data/sintetico/
    python scripts/apagar_lampadas.py --amostra 12        # só um mosaico antes/depois para conferir

Por quê: "poste apagado à noite" é a classe difícil (poucas fotos reais existem), e é justamente a
que importa. Nas fotos noturnas com poste ACESO a posição da luminária já está anotada; aqui o brilho
dela é removido e a imagem vira um exemplo de APAGADO com a caixa no lugar certo.

Como (por luminária):
  1. máscara do brilho (lâmpada + halo) num círculo em volta da caixa
  2. inpainting (cv2.inpaint, Telea): a região é reconstruída a partir do entorno
  3. o halo que sobra é escurecido com um gradiente radial
  4. desenha a luminária apagada (elipse cinza-escura) no centro da caixa

Rigor (vai para o relatório):
  - só usa originais que caem no TREINO pela mesma regra de divisão do unificar_dataset.py:
    um sintético nunca deriva de uma foto que está na validação ou no teste (sem vazamento)
  - o unificar_dataset.py manda a fonte "sintetico" inteira para o treino; as métricas (mAP) são
    medidas só em fotos reais
"""
from __future__ import annotations

import argparse
import random
import shutil
import sys

import cv2
import numpy as np
import yaml

from _comum import DATA
from unificar_dataset import fontes_disponiveis, ler_label, nomes_da_fonte, pastas_split, split_por_hash, traduzir
from visao.config import CLASSE_ACESO, CLASSE_APAGADO, classes

# só cenas de rua com luminárias distantes; streetlight-night (closes com reflexo de lente) gerava
# "fantasmas" que ensinariam um atalho falso ao modelo (conferido no mosaico antes/depois)
FONTES = {"nighttime-streetlight-detection", "led-only"}
MAX_LARGURA_CAIXA = 0.08   # luminária ocupando mais que isso da largura = close, descartado
MAX_SATURADO = 0.015       # mais que 1,5% de pixels estourados = muito reflexo, descartado
CENA_NOITE = 110          # brilho médio (V, 0-255) abaixo do qual a cena é noturna
DESTINO = DATA / "sintetico"


def candidatas() -> list[tuple[str, object, list]]:
    """(fonte, caminho da imagem, caixas YOLO) só com postes acesos e só do split de treino."""
    saida = []
    for fonte in fontes_disponiveis():
        if fonte.name not in FONTES:
            continue
        nomes = nomes_da_fonte(fonte)
        splits = pastas_split(fonte)
        redistribuir = not ("valid" in splits and "test" in splits)
        for split_orig, d in splits.items():
            for img in (d / "images").iterdir():
                caixas = ler_label(d / "labels" / f"{img.stem}.txt")
                if not caixas or any(traduzir(fonte, nomes[c]) != CLASSE_ACESO for c, *_ in caixas):
                    continue
                split = split_por_hash(img.name) if redistribuir else split_orig
                if split == "train":  # anti-vazamento: nada que esteja na validação/teste
                    saida.append((fonte.name, img, caixas))
    return saida


def apagar(img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> None:
    """Remove o brilho de UMA luminária (in-place)."""
    H, W = img.shape[:2]
    w, h = x2 - x1, y2 - y1
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    R = int(max(w, h) * 2.2) + 8
    a, b, c, d = max(0, cx - R), max(0, cy - R), min(W, cx + R), min(H, cy + R)
    roi = img[b:d, a:c]
    if roi.size == 0:
        return
    v = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[..., 2].astype(np.float32)
    yy, xx = np.mgrid[b:d, a:c]
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / R            # 0 no centro, 1 na borda do círculo
    dentro = r <= 1

    # 1-2. brilho forte dentro do círculo -> inpainting
    limiar = max(120.0, float(np.median(v[dentro])) + 45)
    mascara = ((v > limiar) & dentro).astype(np.uint8) * 255
    mascara = cv2.dilate(mascara, np.ones((5, 5), np.uint8), iterations=2)
    if mascara.any():
        roi[:] = cv2.inpaint(roi, mascara, 7, cv2.INPAINT_TELEA)

    # 3. halo residual: escurece mais perto do centro
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV).astype(np.float32)
    # nunca abaixo do entorno: em céu com névoa, escurecer demais deixava uma "mancha" escura
    anel = hsv[..., 2][(r > 0.9) & (r <= 1)]
    piso = float(np.median(anel)) if anel.size else 0.0
    fator = np.where(dentro, 0.7 + 0.3 * np.clip(r, 0, 1) ** 1.5, 1.0)
    hsv[..., 2] = np.where(dentro, np.maximum(hsv[..., 2] * fator, np.minimum(hsv[..., 2], piso)), hsv[..., 2])
    roi[:] = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)

    # 4. luminária apagada: elipse cinza-escura (carcaça sem luz), suavizada para não ficar "colada"
    base = np.median(roi[dentro], axis=0)
    cor = tuple(int(min(255, 0.55 * base[i] + 38)) for i in range(3))
    camada = roi.copy()
    cv2.ellipse(camada, (cx - a, cy - b), (max(2, int(w * 0.42)), max(2, int(h * 0.30))), 0, 0, 360, cor, -1, cv2.LINE_AA)
    mistura = cv2.GaussianBlur(camada, (3, 3), 0)
    roi[:] = cv2.addWeighted(mistura, 0.55, roi, 0.45, 0)


def gerar(item) -> tuple[np.ndarray, list] | None:
    _, caminho, caixas = item
    img = cv2.imread(str(caminho))
    if img is None:
        return None
    v = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 2]
    if float(v.mean()) >= CENA_NOITE or float((v > 245).mean()) > MAX_SATURADO:
        return None
    if any(w > MAX_LARGURA_CAIXA for _, _, _, w, _ in caixas):
        return None
    H, W = img.shape[:2]
    usadas = []
    for _, x, y, w, h in caixas:
        x1, y1, x2, y2 = int((x - w / 2) * W), int((y - h / 2) * H), int((x + w / 2) * W), int((y + h / 2) * H)
        if x2 - x1 < 10 or y2 - y1 < 10:
            continue
        apagar(img, x1, y1, x2, y2)
        usadas.append((x, y, w, h))
    return (img, usadas) if usadas else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", type=int, default=300)
    ap.add_argument("--semente", type=int, default=7)
    ap.add_argument("--amostra", type=int, default=0, help="só gera um mosaico antes/depois com N imagens")
    ap.add_argument("--mosaico", default=str(DATA / "sintetico_amostra.jpg"))
    args = ap.parse_args()

    itens = candidatas()
    random.Random(args.semente).shuffle(itens)
    print(f"{len(itens)} fotos noturnas com poste aceso no TREINO disponíveis")

    if args.amostra:
        pares = []
        for it in itens:
            r = gerar(it)
            if r:
                orig = cv2.imread(str(it[1]))
                lado = lambda im: cv2.resize(im, (360, int(360 * im.shape[0] / im.shape[1])))  # noqa: E731
                o, s = lado(orig), lado(r[0])
                pares.append(np.hstack([o, np.full((o.shape[0], 6, 3), 255, np.uint8), s]))
            if len(pares) == args.amostra:
                break
        alt = max(p.shape[0] for p in pares)
        linhas = [cv2.copyMakeBorder(p, 0, alt - p.shape[0] + 6, 0, 0, cv2.BORDER_CONSTANT) for p in pares]
        cols = 2
        while len(linhas) % cols:
            linhas.append(np.zeros_like(linhas[0]))
        cv2.imwrite(args.mosaico, np.vstack([np.hstack(linhas[i:i + cols]) for i in range(0, len(linhas), cols)]))
        print(f"mosaico antes | depois: {args.mosaico}")
        return 0

    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    (DESTINO / "train" / "images").mkdir(parents=True)
    (DESTINO / "train" / "labels").mkdir(parents=True)
    id_apagado = classes().index(CLASSE_APAGADO)
    feitas = caixas = 0
    for it in itens:
        if feitas >= args.max:
            break
        r = gerar(it)
        if not r:
            continue
        img, usadas = r
        nome = f"{it[0]}__{it[1].stem}__apagada"
        cv2.imwrite(str(DESTINO / "train" / "images" / f"{nome}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        (DESTINO / "train" / "labels" / f"{nome}.txt").write_text(
            "\n".join(f"{id_apagado} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for x, y, w, h in usadas))
        feitas += 1
        caixas += len(usadas)
    with open(DESTINO / "data.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump({"names": classes(), "nc": len(classes())}, f, allow_unicode=True)
    print(f"{feitas} imagens sintéticas, {caixas} caixas de '{CLASSE_APAGADO}' em {DESTINO} (só treino)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
