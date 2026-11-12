"""Leitura/escrita da tabela de ocorrencias.

Aqui o CSV simula a tabela Ouro do pipeline de dados. Para ligar no Databricks/SQL de verdade,
troque apenas estas duas funcoes (ler/salvar) mantendo a mesma assinatura.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

CAMPOS_PADRAO = [
    "id", "poste_id", "data_hora", "latitude", "longitude", "lux_medido", "foto",
    "descricao_ia", "confianca_ia", "severidade", "escola_proxima", "ponto_onibus_proximo",
    "status", "prioridade", "protocolo", "data_envio", "chamado_pdf", "observacao",
]


def ler(csv_path: Path) -> tuple[list[str], list[dict]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        campos = list(leitor.fieldnames or [])
        linhas = [dict(r) for r in leitor]
    for c in CAMPOS_PADRAO:
        if c not in campos:
            campos.append(c)
    for r in linhas:
        for c in campos:
            r.setdefault(c, "")
            if r[c] is None:
                r[c] = ""
    return campos, linhas


def salvar(csv_path: Path, campos: list[str], linhas: list[dict]) -> None:
    """Escrita atomica: grava num temporario e troca, para nao corromper o CSV se o robo cair."""
    tmp = csv_path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)
    os.replace(tmp, csv_path)
