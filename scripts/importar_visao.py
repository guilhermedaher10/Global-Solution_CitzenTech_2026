"""Importa respostas da Visao (JSON v1.1) para a tabela de chamados.

Exemplos:
    python scripts/importar_visao.py data/visao_exemplos.jsonl
    python scripts/importar_visao.py eventos.jsonl --confirmar   # simula o atendente (demo)
    python scripts/importar_visao.py pasta_com_jsons/ --csv data/chamados.csv

A entrada pode ser um .json (objeto ou lista), um .jsonl (um evento por linha, como o
`tempo_real.py --eventos` da Visao gera) ou uma pasta com esses arquivos.

Status inicial: `validado` (aguarda o atendente) ou `recusado` (a Visao disse para nao abrir).
Com --confirmar, os validos entram como `confirmado`, o estado em que o RPA os pega.
Importar duas vezes o mesmo evento nao duplica.
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import contrato, repositorio  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("entrada", type=Path)
    p.add_argument("--csv", type=Path, default=RAIZ / "data" / "chamados.csv")
    p.add_argument("--confirmar", action="store_true")
    a = p.parse_args()

    if a.csv.exists():
        campos, linhas = repositorio.ler(a.csv)
    else:
        campos, linhas = list(repositorio.CAMPOS_PADRAO), []

    novas, avisos = contrato.importar_eventos(
        contrato.ler_eventos(a.entrada), {r["id_captura"] for r in linhas},
        a.csv.parent, a.confirmar)
    repositorio.salvar(a.csv, campos, linhas + novas)

    for aviso in avisos:
        print("aviso:", aviso)
    print(f"{len(novas)} chamado(s) importado(s) para {a.csv}")


if __name__ == "__main__":
    main()
