"""Volta a tabela de exemplo ao estado inicial para repetir a demonstracao.

Todas as ocorrencias voltam para PENDENTE (a O-010 volta APROVADO, simulando a
aprovacao humana) e as saidas geradas em outbox/ sao apagadas.
"""
import csv
import shutil
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
p = raiz / "data" / "ocorrencias.csv"

with p.open(newline="", encoding="utf-8") as f:
    leitor = csv.DictReader(f)
    campos = leitor.fieldnames
    linhas = list(leitor)

for linha in linhas:
    if linha["id"] == "O-000":  # chamado antigo, usado no teste de duplicidade
        continue
    aprovada = linha["id"] == "O-010"
    linha["status"] = "APROVADO" if aprovada else "PENDENTE"
    for c in ("prioridade", "protocolo", "data_envio", "chamado_pdf"):
        linha[c] = ""
    linha["observacao"] = "aprovado manualmente apos revisao" if aprovada else ""

with p.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=campos)
    w.writeheader()
    w.writerows(linhas)

for pasta in ("emails", "chamados"):
    shutil.rmtree(raiz / "outbox" / pasta, ignore_errors=True)
(raiz / "outbox" / "fila_portal.csv").unlink(missing_ok=True)
(raiz / "outbox" / "protocolos_portal.csv").unlink(missing_ok=True)
print("demo resetada")
