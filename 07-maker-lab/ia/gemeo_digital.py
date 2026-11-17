"""Gêmeo digital do carrinho: roda a MESMA IA do ESP32 com leituras REAIS e avisa o Vésper.

Sem o carrinho montado, este script faz o papel dele, passo a passo igual ao firmware:
  1. lê os pesos de ModeloTreinado.h (o mesmo arquivo que vai para o ESP32);
  2. "dirige" por uma rua reproduzindo os CSVs gravados pelo carrinho real (dados/teste e dados/treino),
     10 leituras por segundo;
  3. a cada 2 leituras, calcula os 4 atributos da janela de 10 e roda a MLP (ReLU + softmax);
  4. confirma a classe depois de 3 inferências seguidas com confiança >= 0,70 (como no .ino);
  5. quando confirma escuro_livre ou escuro_obstaculo, manda POST /v1/alerta-robo para a API do Vésper
     (no máximo 1 a cada 30 s) e mostra o protocolo e o LED devolvidos.

O alerta aparece no site do Vésper (central de chamados, origem "Robô"), no mapa e no Grafana.

Uso (só Python, sem bibliotecas extras):
    py ia/gemeo_digital.py                         # patrulha mandando para a API na Azure
    py ia/gemeo_digital.py --api http://localhost:8000
    py ia/gemeo_digital.py --sem-api               # só mostra o que seria enviado
    py ia/gemeo_digital.py --velocidade 1          # tempo real (padrão: 4x mais rápido)
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
MODELO_H = RAIZ.parent / "firmware" / "MakerLab_Controle_Independente_TinyML" / "ModeloTreinado.h"
DADOS = RAIZ / "dados"
API_PADRAO = "https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io"

# Mesmas constantes do Config.h / Vesper.h
CLASSES = ("claro_livre", "claro_obstaculo", "escuro_livre", "escuro_obstaculo")
PERIODO_S = 0.1          # PERIODO_MS = 100
JANELA = 10              # LEITURAS_JANELA
PASSO = 2                # PASSO_INFERENCIA
ESCORE_MIN = 0.70        # ESCORE_MIN
REPETICOES = 3           # confirmação no inferir()
INTERVALO_MIN_S = 30     # vesper::INTERVALO_MIN_MS

# Rua da demonstração (perto da FIAP Paulista); cada leitura anda ~2 m
LAT0, LON0, PASSO_GRAUS = -23.5641, -46.6525, 0.00002

# Percurso: trechos gravados pelo carrinho real, na ordem em que ele "passa" por eles.
# Dois trechos escuros separados por mais de 30 s de rua iluminada.
PERCURSO = (
    "teste/claro_livre.teste_01", "teste/claro_obstaculo.teste_01",
    "teste/escuro_livre.teste_01", "teste/escuro_obstaculo.teste_01",
    "treino/claro_livre.treino_01", "treino/claro_livre.treino_02", "treino/claro_obstaculo.treino_01",
    "treino/claro_livre.treino_03", "treino/claro_obstaculo.treino_02", "treino/claro_livre.treino_04",
    "teste/claro_livre.teste_02",
    "teste/escuro_obstaculo.teste_02", "teste/escuro_livre.teste_02",
    "teste/claro_obstaculo.teste_02",
)


# ---------------------------------------------------------------- modelo (ModeloTreinado.h)
@dataclass
class Modelo:
    media: list[float]
    escala: list[float]
    w1: list[list[float]]   # [4][12]
    b1: list[float]
    w2: list[list[float]]   # [12][4]
    b2: list[float]


def _numeros(texto: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?=f)", texto)]


def carregar_modelo(caminho: Path = MODELO_H) -> Modelo:
    """Lê os pesos direto do cabeçalho C++ que vai para o ESP32 (uma fonte só)."""
    h = caminho.read_text(encoding="utf-8")

    def bloco(nome: str) -> list[float]:
        m = re.search(rf"\b{nome}(?:\[\d+\])+\s*=\s*\{{(.*?)\}};", h, re.S)
        if not m:
            raise ValueError(f"{caminho.name}: não achei o vetor '{nome}'")
        return _numeros(m.group(1))

    w1, w2 = bloco("w1"), bloco("w2")
    if len(w1) != 48 or len(w2) != 48:
        raise ValueError("modelo fora do formato 4 -> 12 -> 4")
    return Modelo(media=bloco("media"), escala=bloco("escala"),
                  w1=[w1[i * 12:(i + 1) * 12] for i in range(4)], b1=bloco("b1"),
                  w2=[w2[j * 4:(j + 1) * 4] for j in range(12)], b2=bloco("b2"))


def prever(m: Modelo, x: list[float]) -> list[float]:
    """Igual a preverRede() do .ino: normaliza, ReLU com 12 neurônios, softmax com 4 saídas."""
    z = [(x[i] - m.media[i]) / m.escala[i] for i in range(4)]
    h = [max(0.0, m.b1[j] + sum(z[i] * m.w1[i][j] for i in range(4))) for j in range(12)]
    logits = [m.b2[k] + sum(h[j] * m.w2[j][k] for j in range(12)) for k in range(4)]
    topo = max(logits)
    e = [math.exp(v - topo) for v in logits]
    total = sum(e)
    return [v / total for v in e]


def atributos(janela: list[tuple[float, int]]) -> list[float]:
    """Igual a extrairAtributos(): média, mínimo, desvio-padrão da distância e fração escura."""
    d = [l[0] for l in janela]
    media = sum(d) / len(d)
    variancia = sum(v * v for v in d) / len(d) - media * media
    return [media, min(d), math.sqrt(max(0.0, variancia)), sum(l[1] for l in janela) / len(janela)]


# ---------------------------------------------------------------- leituras reais do carrinho
def ler_csv(caminho: Path) -> list[tuple[float, int]]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return [(float(r["distancia_cm"]), int(r["escuro"])) for r in csv.DictReader(f)]


def leituras_do_percurso(percurso=PERCURSO) -> list[tuple[float, int, str]]:
    saida = []
    for trecho in percurso:
        rotulo = Path(trecho).name.split(".")[0]
        saida += [(d, e, rotulo) for d, e in ler_csv(DADOS / f"{trecho}.csv")]
    return saida


# ---------------------------------------------------------------- o "firmware" em Python
@dataclass
class Evento:
    indice: int            # número da leitura (tempo = indice * 0,1 s)
    classe: str
    confianca: float
    latitude: float
    longitude: float


class Carrinho:
    """Mesma lógica de amostrar() + inferir() + registrarEvento() do firmware."""

    def __init__(self, modelo: Modelo):
        self.modelo = modelo
        self.janela: list[tuple[float, int]] = []
        self.novas = 0
        self.pendente, self.repeticoes, self.confirmado = -1, 0, -1

    def ler(self, indice: int, distancia: float, escuro: int) -> Evento | None:
        self.janela = (self.janela + [(distancia, escuro)])[-JANELA:]
        self.novas += 1
        if len(self.janela) < JANELA or self.novas < PASSO:
            return None
        self.novas = 0
        probs = prever(self.modelo, atributos(self.janela))
        melhor = max(range(4), key=probs.__getitem__)
        if probs[melhor] < ESCORE_MIN:
            self.pendente, self.repeticoes = -1, 0
            return None
        if self.pendente == melhor:
            self.repeticoes += 1
        else:
            self.pendente, self.repeticoes = melhor, 1
        if self.repeticoes >= REPETICOES and self.confirmado != melhor:
            self.confirmado = melhor
            return Evento(indice, CLASSES[melhor], probs[melhor],
                          round(LAT0, 6), round(LON0 + indice * PASSO_GRAUS, 6))
        return None


def corpo_alerta(ev: Evento) -> dict:
    """O mesmo JSON que o Vesper.h manda (contrato de POST /v1/alerta-robo)."""
    return {"origem": "robo", "latitude": ev.latitude, "longitude": ev.longitude, "alerta": ["escuro"],
            "classe_ia": ev.classe, "confianca_ia": round(ev.confianca, 3)}


def enviar(api: str, corpo: dict) -> dict:
    req = urllib.request.Request(f"{api.rstrip('/')}/v1/alerta-robo", data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:   # 60 s: a API na Azure pode estar "acordando"
        return json.loads(r.read())


def avaliar(modelo: Modelo) -> tuple[int, int]:
    """Confere a IA nos CSVs de teste com janelas fixas de 10 (como no treino): (acertos, total)."""
    acertos = total = 0
    for f in sorted((DADOS / "teste").glob("*.csv")):
        rotulo = f.name.split(".")[0]
        leituras = ler_csv(f)
        for i in range(0, len(leituras), JANELA):
            probs = prever(modelo, atributos(leituras[i:i + JANELA]))
            acertos += CLASSES[max(range(4), key=probs.__getitem__)] == rotulo
            total += 1
    return acertos, total


# ---------------------------------------------------------------- execução
LED = {"led_vermelho": "🔴 LED vermelho", "led_amarelo": "🟡 LED amarelo", "nenhuma": "⚪ sem LED"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default=API_PADRAO, help="URL da API do Vésper (padrão: Azure)")
    ap.add_argument("--sem-api", action="store_true", help="não envia; só mostra o JSON")
    ap.add_argument("--velocidade", type=float, default=4.0, help="1 = tempo real; 0 = sem pausa")
    args = ap.parse_args()

    modelo = carregar_modelo()
    acertos, total = avaliar(modelo)
    print(f"IA do carrinho carregada de {MODELO_H.name}: 4 -> 12 -> 4, "
          f"{acertos}/{total} janelas de teste corretas\n")
    print(f"Patrulha com leituras reais gravadas pelo carrinho -> {'(sem envio)' if args.sem_api else args.api}\n")

    carrinho = Carrinho(modelo)
    ultimo_envio_s: float | None = None
    enviados = 0
    trecho_atual = None
    for i, (dist, escuro, rotulo) in enumerate(leituras_do_percurso()):
        if args.velocidade > 0:
            time.sleep(PERIODO_S / args.velocidade)
        if rotulo != trecho_atual:
            trecho_atual = rotulo
            print(f"  [{i * PERIODO_S:5.1f}s] trecho gravado: {rotulo}")
        ev = carrinho.ler(i, dist, escuro)
        if ev is None:
            continue
        t = ev.indice * PERIODO_S
        print(f"  [{t:5.1f}s] IA confirmou {ev.classe} ({ev.confianca:.0%})")
        if not ev.classe.startswith("escuro_"):
            continue
        if ultimo_envio_s is not None and t - ultimo_envio_s < INTERVALO_MIN_S:
            print(f"           trecho escuro já avisado há {t - ultimo_envio_s:.0f}s (intervalo de {INTERVALO_MIN_S}s)")
            continue
        corpo = corpo_alerta(ev)
        ultimo_envio_s = t
        if args.sem_api:
            print(f"           POST /v1/alerta-robo {json.dumps(corpo)}")
            continue
        try:
            r = enviar(args.api, corpo)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"           ✗ não consegui falar com a API ({getattr(e, 'reason', e)}); o carrinho segue sozinho")
            continue
        enviados += 1
        print(f"           → Vésper: {r['status']}, protocolo {r.get('protocolo') or '--'}, "
              f"prioridade {r['prioridade_previa']['nivel']}, {LED.get(r['acao_robo'], r['acao_robo'])}")
        for o in r.get("encaminhar_para", [])[:1]:
            print(f"             encaminhar para: {o.get('orgao')}")

    if not args.sem_api:
        print(f"\n{enviados} alerta(s) enviados. Veja na central do site (origem \"Robô\"): {args.api}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
