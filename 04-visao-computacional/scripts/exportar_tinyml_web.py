"""Copia a IA do carrinho (Maker Lab, pasta 07) para a aba Robô do site.

Lê os pesos de 07-maker-lab/firmware/.../ModeloTreinado.h (o mesmo arquivo que vai para o ESP32)
e grava web/tinyml-carrinho.json, que a "Patrulha ao vivo" roda no navegador.
Rode de novo sempre que o Heitor treinar outro modelo:

    python scripts/exportar_tinyml_web.py

O teste tests/test_tinyml_web.py falha se o JSON ficar diferente do cabeçalho do firmware.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CABECALHO = (RAIZ.parent / "07-maker-lab" / "firmware" / "MakerLab_Controle_Independente_TinyML"
             / "ModeloTreinado.h")
SAIDA = RAIZ / "web" / "tinyml-carrinho.json"
CLASSES = ["claro_livre", "claro_obstaculo", "escuro_livre", "escuro_obstaculo"]
ATRIBUTOS = ["media_distancia", "min_distancia", "desvio_distancia", "fracao_escuro"]


def ler_cabecalho(caminho: Path = CABECALHO) -> dict:
    h = caminho.read_text(encoding="utf-8")

    def vetor(nome: str) -> list[float]:
        m = re.search(rf"\b{nome}(?:\[\d+\])+\s*=\s*\{{(.*?)\}};", h, re.S)
        if not m:
            raise ValueError(f"{caminho.name}: vetor '{nome}' não encontrado")
        return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?=f)", m.group(1))]

    w1, w2 = vetor("w1"), vetor("w2")
    if len(w1) != 48 or len(w2) != 48:
        raise ValueError("o modelo precisa ser 4 -> 12 -> 4")
    return {
        "origem": "07-maker-lab/firmware/MakerLab_Controle_Independente_TinyML/ModeloTreinado.h",
        "classes": CLASSES, "atributos": ATRIBUTOS,
        "media": vetor("media"), "escala": vetor("escala"),
        "w1": [w1[i * 12:(i + 1) * 12] for i in range(4)], "b1": vetor("b1"),
        "w2": [w2[j * 4:(j + 1) * 4] for j in range(12)], "b2": vetor("b2"),
        # mesmas regras do firmware (Config.h / inferir())
        "janela": 10, "passo": 2, "escore_min": 0.70, "repeticoes": 3, "periodo_ms": 100,
    }


if __name__ == "__main__":
    SAIDA.write_text(json.dumps(ler_cabecalho(), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"gravado {SAIDA.relative_to(RAIZ)}")
