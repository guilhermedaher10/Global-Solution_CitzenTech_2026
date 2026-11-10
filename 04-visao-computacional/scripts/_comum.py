"""Utilidades compartilhadas pelos scripts (caminhos e leitura de configs)."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
for _s in (sys.stdout, sys.stderr):  # acentos no terminal do Windows
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(RAIZ))  # permite `import visao` rodando `python scripts/x.py`

DATA = RAIZ / "data"
BRUTO = DATA / "bruto"
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def fontes() -> dict:
    with open(RAIZ / "configs" / "fontes.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def listar_imagens(pasta: Path) -> list[Path]:
    return sorted(p for p in Path(pasta).rglob("*") if p.suffix.lower() in EXTENSOES_IMAGEM)


def carregar_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(RAIZ / ".env")
    except ImportError:
        pass
