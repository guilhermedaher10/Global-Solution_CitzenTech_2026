"""Reconstroi a tabela de exemplo (data/chamados.csv) a partir de data/visao_exemplos.jsonl.

Estado inicial da demonstracao:
  - C-000: ja encaminhado em 28/10 (serve para testar o agrupamento com chamado existente)
  - C-011: `validado`, ainda aguardando o atendente (o robo nao o processa e o n8n avisa)
  - os demais: `confirmado`, prontos para o robo
Tambem apaga as saidas geradas em outbox/ (e-mails, PDFs, fila do portal).
"""
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import contrato, repositorio  # noqa: E402

EVENTOS = RAIZ / "data" / "visao_exemplos.jsonl"
CSV = RAIZ / "data" / "chamados.csv"

ESTADO_INICIAL = {
    "C-000": {"status": "encaminhado", "rpa_etapa": "enviado", "protocolo": "CH-20261028-C-000",
              "data_encaminhamento": "2026-10-28", "chamado_pdf": "chamado_C-000.pdf"},
    "C-011": {"status": "validado"},
}


def main() -> None:
    linhas = []
    for ev in contrato.ler_eventos(EVENTOS):
        linha = contrato.de_visao_v11(ev)
        linha["foto"] = contrato.foto_do_evento(ev, CSV.parent)
        linha["status"] = contrato.CONFIRMADO
        linha.update(ESTADO_INICIAL.get(linha["id_captura"], {}))
        linhas.append(linha)
    repositorio.salvar(CSV, repositorio.CAMPOS_PADRAO, linhas)

    for pasta in ("emails", "chamados"):
        shutil.rmtree(RAIZ / "outbox" / pasta, ignore_errors=True)
    for nome in ("fila_portal.csv", "protocolos_portal.csv"):
        (RAIZ / "outbox" / nome).unlink(missing_ok=True)
    print(f"demo resetada: {len(linhas)} chamados em {CSV}")


if __name__ == "__main__":
    main()
