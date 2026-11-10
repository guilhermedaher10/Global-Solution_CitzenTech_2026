"""Junta vários datasets YOLO (Roboflow + o que você anotou) num só, com as NOSSAS classes.

    python scripts/unificar_dataset.py --listar                 # vê os nomes de classe de cada fonte
    python scripts/unificar_dataset.py                          # gera data/final/
    python scripts/unificar_dataset.py --teste-fonte anotado    # uma fonte inteira só no teste

Regras:
- Nomes de classe traduzidos por configs/classes.yaml (aliases). Classe desconhecida = descartada.
- Imagem com alguma caixa descartada sai do dataset inteira: senão o modelo aprenderia que aquele
  poste "não é poste". Imagens originalmente sem caixa ficam (exemplos negativos).
- Polígonos (export de segmentação) viram caixas.
- Fonte sem valid/test é dividida 80/10/10 de forma determinística (hash do nome).
- --teste-fonte coloca uma fonte inteira no teste: mede se o modelo generaliza para imagens de
  outra origem (é o número honesto para o relatório).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from _comum import BRUTO, DATA, EXTENSOES_IMAGEM, RAIZ
from visao.config import classes, normalizar_classe

FINAL = DATA / "final"
SPLITS = ("train", "valid", "test")
ALIAS_SPLIT = {"train": "train", "valid": "valid", "val": "valid", "test": "test"}


def fontes_disponiveis() -> list[Path]:
    candidatas = sorted((BRUTO / "roboflow").glob("*")) + [DATA / "anotado"]
    return [p for p in candidatas if (p / "data.yaml").exists()]


def nomes_da_fonte(fonte: Path) -> list[str]:
    with open(fonte / "data.yaml", encoding="utf-8") as f:
        nomes = yaml.safe_load(f)["names"]
    if isinstance(nomes, dict):
        return [nomes[k] for k in sorted(nomes, key=int)]
    return list(nomes)


def pastas_split(fonte: Path) -> dict[str, Path]:
    achadas = {}
    for d in fonte.iterdir():
        if d.is_dir() and d.name in ALIAS_SPLIT and (d / "images").exists():
            achadas[ALIAS_SPLIT[d.name]] = d
    return achadas


def ler_label(caminho: Path) -> list[tuple[int, float, float, float, float]]:
    caixas = []
    if not caminho.exists():
        return caixas
    for linha in caminho.read_text().split("\n"):
        v = linha.split()
        if len(v) < 5:
            continue
        c, nums = int(float(v[0])), [float(x) for x in v[1:]]
        if len(nums) == 4:
            caixas.append((c, *nums))
        else:  # polígono x1 y1 x2 y2 ... -> caixa
            xs, ys = nums[0::2], nums[1::2]
            x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
            caixas.append((c, (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1))
    return caixas


def split_por_hash(nome: str) -> str:
    h = int(hashlib.md5(nome.encode()).hexdigest(), 16) % 100
    return "train" if h < 80 else ("valid" if h < 90 else "test")


def listar() -> None:
    for fonte in fontes_disponiveis():
        nomes = nomes_da_fonte(fonte)
        contagem = Counter()
        for d in pastas_split(fonte).values():
            for lbl in (d / "labels").glob("*.txt"):
                contagem.update(c for c, *_ in ler_label(lbl))
        print(f"\n{fonte.name}  (splits: {', '.join(pastas_split(fonte)) or 'nenhum'})")
        for i, nome in enumerate(nomes):
            destino = normalizar_classe(nome) or "DESCARTADA"
            print(f"  {nome!r:32} {contagem[i]:6d} caixas  ->  {destino}")
    print("\nClasse marcada DESCARTADA que deveria contar? Adicione o nome em configs/classes.yaml.")


def unificar(teste_fontes: set[str]) -> None:
    nossas = classes()
    if FINAL.exists():
        shutil.rmtree(FINAL)
    for s in SPLITS:
        (FINAL / s / "images").mkdir(parents=True)
        (FINAL / s / "labels").mkdir(parents=True)

    estat = defaultdict(lambda: defaultdict(Counter))  # split -> fonte -> classe
    descartadas = Counter()
    for fonte in fontes_disponiveis():
        nomes = nomes_da_fonte(fonte)
        mapa = {i: (nossas.index(c) if (c := normalizar_classe(n)) in nossas else None)
                for i, n in enumerate(nomes)}
        splits = pastas_split(fonte)
        redistribuir = not ("valid" in splits and "test" in splits)
        for split_orig, d in splits.items():
            for img in (d / "images").iterdir():
                if img.suffix.lower() not in EXTENSOES_IMAGEM:
                    continue
                caixas = ler_label(d / "labels" / f"{img.stem}.txt")
                if any(mapa.get(c) is None for c, *_ in caixas):
                    descartadas[fonte.name] += 1
                    continue
                if fonte.name in teste_fontes:
                    split = "test"
                elif redistribuir:
                    split = split_por_hash(img.name)
                else:
                    split = split_orig
                nome = f"{fonte.name}__{img.stem}"
                shutil.copy2(img, FINAL / split / "images" / f"{nome}{img.suffix.lower()}")
                linhas = [f"{mapa[c]} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for c, x, y, w, h in caixas]
                (FINAL / split / "labels" / f"{nome}.txt").write_text("\n".join(linhas))
                estat[split][fonte.name]["_imagens"] += 1
                for c, *_ in caixas:
                    estat[split][fonte.name][nossas[mapa[c]]] += 1

    yaml_final = {"path": str(FINAL.resolve()).replace("\\", "/"), "train": "train/images",
                  "val": "valid/images", "test": "test/images", "names": dict(enumerate(nossas))}
    with open(FINAL / "data.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(yaml_final, f, allow_unicode=True, sort_keys=False)

    # relatório versionável (sem imagens) para o README/relatório
    linhas = ["# Estatísticas do dataset unificado", "",
              "| Split | Fonte | Imagens | " + " | ".join(nossas) + " |",
              "|---|---|---|" + "---|" * len(nossas)]
    totais = defaultdict(Counter)
    for split in SPLITS:
        for fonte, cont in sorted(estat[split].items()):
            linhas.append(f"| {split} | {fonte} | {cont['_imagens']} | "
                          + " | ".join(str(cont[c]) for c in nossas) + " |")
            totais[split].update(cont)
    linhas += ["", "| Split | Imagens | " + " | ".join(nossas) + " |", "|---|---|" + "---|" * len(nossas)]
    for split in SPLITS:
        linhas.append(f"| **{split}** | {totais[split]['_imagens']} | "
                      + " | ".join(str(totais[split][c]) for c in nossas) + " |")
    if descartadas:
        linhas += ["", "Imagens descartadas por conter classe fora do escopo: "
                   + ", ".join(f"{k}: {v}" for k, v in descartadas.items())]
    (RAIZ / "results").mkdir(exist_ok=True)
    (RAIZ / "results" / "dataset.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    (FINAL / "estatisticas.json").write_text(json.dumps(estat, indent=2, default=dict))
    print("\n".join(linhas))
    print(f"\nDataset pronto em {FINAL}. Próximo passo: python scripts/treinar.py")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--teste-fonte", action="append", default=[],
                    help="nome da pasta da fonte que vai inteira para o teste")
    args = ap.parse_args()
    if not fontes_disponiveis():
        print("Nenhuma fonte encontrada. Rode scripts/baixar_roboflow.py ou exporte o anotado para data/anotado/")
        return 1
    listar() if args.listar else unificar(set(args.teste_fonte))
    return 0


if __name__ == "__main__":
    sys.exit(main())
