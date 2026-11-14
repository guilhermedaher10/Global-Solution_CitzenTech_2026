"""Leitura/escrita da tabela de chamados.

O arquitetura.md do grupo preve que o RPA leia/escreva "no banco ou na API do backend", mas o
backend ainda nao foi definido. Por isso o CSV faz o papel do banco de chamados.
Para ligar no backend real, troque so estas duas funcoes (ler/salvar), mantendo a assinatura.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

# Colunas vindas do contrato da Visao (ver contrato.de_visao_v11) + status do ciclo de vida
# + colunas escritas pelo RPA (rpa_etapa, chamado_principal, protocolo, ...).
CAMPOS_PADRAO = [
    "id_captura", "timestamp", "origem", "latitude", "longitude", "sensor_lux",
    "status_trecho", "postes_apagados", "tipos_chamado", "confirmacao",
    "prioridade_nivel", "prioridade_pontuacao", "fatores", "motivos", "modelo", "foto",
    "status",
    "rpa_etapa", "chamado_principal", "protocolo", "data_encaminhamento", "chamado_pdf",
    "motivo_rpa",
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
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = csv_path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)
    os.replace(tmp, csv_path)
