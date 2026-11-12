"""Carrega as configurações em configs/*.yaml (classes, aliases e regras de negócio)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parent.parent
PASTA_CONFIGS = Path(os.getenv("VISAO_CONFIGS", RAIZ / "configs"))

CLASSE_ACESO = "poste_aceso"
CLASSE_APAGADO = "poste_apagado"
CLASSE_BURACO = "buraco"      # entra no modelo quando o dataset de buraco for treinado


def _ler_yaml(nome: str) -> dict[str, Any]:
    with open(PASTA_CONFIGS / nome, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def regras() -> dict[str, Any]:
    return _ler_yaml("regras.yaml")


@lru_cache
def classes() -> list[str]:
    return list(_ler_yaml("classes.yaml")["classes"])


@lru_cache
def tabela_aliases() -> dict[str, str]:
    """Nome usado por qualquer dataset (minúsculo) -> nossa classe."""
    dados = _ler_yaml("classes.yaml")
    tabela: dict[str, str] = {}
    for classe, nomes in dados.get("aliases", {}).items():
        for nome in nomes:
            tabela[str(nome).strip().lower()] = classe
    return tabela


def normalizar_classe(nome: str) -> str | None:
    """Traduz o nome de classe de um dataset/modelo para a nossa. None = descartar."""
    return tabela_aliases().get(str(nome).strip().lower())
