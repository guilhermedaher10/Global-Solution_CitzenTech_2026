"""Roda o pipeline completo em uma pasta de fotos e salva imagem anotada + JSON de cada uma.

    python scripts/analisar_pasta.py --entrada data/final/test/images --max 30
    python scripts/analisar_pasta.py --entrada minhas_fotos --origem cidadao

Saída em results/exemplos/: <nome>.jpg (com caixas e painel, rostos borrados) e <nome>.json.
Ótimo para a seção "Exemplos de resultados" do relatório e para escolher casos para o vídeo.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

from _comum import RAIZ, listar_imagens
from visao.detector import YoloDetector
from visao.overlay import desenhar_deteccoes, desenhar_painel
from visao.pipeline import analisar_bytes
from visao.privacidade import BorradorRostos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrada", required=True)
    ap.add_argument("--saida", default=str(RAIZ / "results" / "exemplos"))
    ap.add_argument("--origem", default="cidadao", choices=["cidadao", "robo", "camera"])
    ap.add_argument("--modelo", default=None)
    ap.add_argument("--max", type=int, default=None)
    args = ap.parse_args()

    det = YoloDetector(args.modelo)
    borrador = BorradorRostos()
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)

    resumo = []
    for p in listar_imagens(Path(args.entrada))[: args.max]:
        analise = analisar_bytes(p.read_bytes(), det, origem=args.origem, borrador=borrador)
        img = cv2.imread(str(p))
        img, _ = borrador.borrar(img)
        desenhar_deteccoes(img, analise.deteccoes)
        r = analise.resumo
        desenhar_painel(img, r.status_trecho, r.postes_acesos, r.postes_apagados, r.luminosidade_media,
                        chamado=(f"Chamado: {analise.prioridade.nivel.value.upper()}"
                                 if analise.validacao.abrir_chamado else "Sem chamado"))
        cv2.imwrite(str(saida / f"{p.stem}.jpg"), img)
        (saida / f"{p.stem}.json").write_text(analise.model_dump_json(indent=2), encoding="utf-8")
        resumo.append((p.name, r.status_trecho.value, analise.validacao.abrir_chamado, analise.prioridade.nivel.value))

    for nome, status, chamado, nivel in resumo:
        print(f"{nome:40} {status:20} chamado={'sim' if chamado else 'não':3} prioridade={nivel}")
    print(f"\n{len(resumo)} imagens em {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
