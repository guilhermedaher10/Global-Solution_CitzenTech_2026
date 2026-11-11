"""Log tecnico (logs/robo.log) e trilha de auditoria (logs/auditoria.csv)."""
from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

CAMPOS_AUDITORIA = ["timestamp", "execucao_id", "ocorrencia_id", "acao", "resultado", "detalhe"]


def configurar_logging(logs_dir: Path) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("despachante")
    log.setLevel(logging.INFO)
    for h in list(log.handlers):  # evita handlers duplicados (testes, reexecucao)
        log.removeHandler(h)
        h.close()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    arquivo = logging.FileHandler(logs_dir / "robo.log", encoding="utf-8")
    arquivo.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    log.addHandler(arquivo)
    log.addHandler(console)
    log.propagate = False
    return log


class Auditoria:
    """Uma linha por decisao/acao. Nao grava dados pessoais: so IDs, acao e resultado."""

    def __init__(self, logs_dir: Path, execucao_id: str):
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.path = logs_dir / "auditoria.csv"
        self.execucao_id = execucao_id
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(CAMPOS_AUDITORIA)

    def registrar(self, ocorrencia_id: str, acao: str, resultado: str, detalhe: str = "") -> None:
        with self.path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [datetime.now().isoformat(timespec="seconds"), self.execucao_id,
                 ocorrencia_id, acao, resultado, detalhe]
            )
