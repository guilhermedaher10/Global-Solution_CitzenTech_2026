"""Agrupamento de relatos: muitos pedidos no mesmo lugar e na mesma hora viram UM alerta de região.

Um poste apagado é um chamado. Dez pessoas da mesma vizinhança dizendo "está tudo escuro" na mesma noite,
com fotos sem nenhuma luz (nem janelas), é outra coisa: provável APAGÃO, e quem resolve é a distribuidora.

Regra (explicável, limiares em configs/regras.yaml, seção regioes):
  1. entram os chamados de luz ainda abertos, das últimas `janela_horas`, com localização;
  2. dois chamados a até `raio_m` um do outro ficam no mesmo grupo (encadeado, como o DBSCAN);
  3. grupo com >= `min_relatos` chamados vira alerta:
       - `apagao_regiao` se >= `min_sinais_apagao` deles têm sinal de falta de energia
         (foto/vídeo sem NENHUMA fonte de luz, ou tipo falta_de_energia). Breu com postes acesos ao
         fundo NÃO conta: se há luz na rede, não é falta de energia;
       - senão, `trecho_escuro_recorrente` (vários relatos de escuro no mesmo lugar).
"""
from __future__ import annotations

import hashlib
import math
from collections import Counter
from datetime import datetime, timedelta

from .central import agora, encaminhar
from .config import regras
from .schemas import Chamado, Regiao, StatusChamado, TipoRegiao

TIPOS_LUZ = {"conserto_poste", "trecho_sem_luz", "instalacao_iluminacao", "falta_de_energia", "suspeita_escuro",
             "poda_ou_obstrucao"}
FECHADOS = {StatusChamado.resolvido, StatusChamado.recusado}


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine: distância em metros entre dois pontos GPS."""
    r = 6_371_000
    f1, f2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(f1) * math.cos(f2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def sinal_apagao(c: Chamado) -> bool:
    return c.possivel_apagao or "falta_de_energia" in c.tipos


def bairro_de(endereco: str | None) -> str | None:
    """O front monta 'rua, nº · bairro · cidade'; o bairro é o do meio."""
    if not endereco:
        return None
    partes = [p.strip() for p in endereco.split("·") if p.strip()]
    if len(partes) >= 3:
        return partes[1]
    if len(partes) == 2:
        return partes[0] if any(ch.isdigit() for ch in partes[1]) else partes[1]
    return None


def agrupar(chamados: list[Chamado], referencia: str | None = None) -> list[Regiao]:
    cfg = regras()["regioes"]
    ref = datetime.fromisoformat(referencia or agora())
    inicio = ref - timedelta(hours=cfg["janela_horas"])
    pontos = [c for c in chamados
              if c.status not in FECHADOS and c.latitude is not None and c.longitude is not None
              and TIPOS_LUZ & set(c.tipos) and datetime.fromisoformat(c.ts) >= inicio]

    # componentes conexos: vizinhos a até raio_m (n pequeno: O(n²) basta)
    grupo = list(range(len(pontos)))

    def raiz(i: int) -> int:
        while grupo[i] != i:
            grupo[i] = grupo[grupo[i]]
            i = grupo[i]
        return i

    for i in range(len(pontos)):
        for j in range(i + 1, len(pontos)):
            if distancia_m(pontos[i].latitude, pontos[i].longitude,
                           pontos[j].latitude, pontos[j].longitude) <= cfg["raio_m"]:
                grupo[raiz(i)] = raiz(j)
    membros: dict[int, list[Chamado]] = {}
    for i, c in enumerate(pontos):
        membros.setdefault(raiz(i), []).append(c)

    regioes = []
    for g in membros.values():
        if len(g) < cfg["min_relatos"]:
            continue
        lat = sum(c.latitude for c in g) / len(g)
        lon = sum(c.longitude for c in g) / len(g)
        raio = max(100, int(max(distancia_m(lat, lon, c.latitude, c.longitude) for c in g)) + 50)
        sinais = sum(sinal_apagao(c) for c in g)
        bairros = Counter(b for b in (bairro_de(c.endereco) for c in g) if b)
        bairro = bairros.most_common(1)[0][0] if bairros else None
        onde = f"em {bairro}" if bairro else f"perto de {lat:.4f}, {lon:.4f}"
        apagao = sinais >= cfg["min_sinais_apagao"]
        tipo = TipoRegiao.apagao_regiao if apagao else TipoRegiao.trecho_escuro_recorrente
        titulo = f"Possível apagão {onde}" if apagao else f"Trecho escuro recorrente {onde}"
        motivos = [f"{len(g)} chamados a até {cfg['raio_m']} m uns dos outros nas últimas {cfg['janela_horas']} h",
                   f"{sinais} com sinal de falta de energia (cena sem nenhuma fonte de luz, nem janelas)"]
        motivos.append("mínimo de sinais atingido: tratar como falta de energia na região" if apagao
                       else f"menos de {cfg['min_sinais_apagao']} sinais de apagão: tratar como falha de iluminação")
        protocolos = sorted(c.protocolo for c in g)
        regioes.append(Regiao(
            id="REG-" + hashlib.sha256(",".join(protocolos).encode()).hexdigest()[:6].upper(),
            tipo=tipo, titulo=titulo, bairro=bairro, latitude=round(lat, 6), longitude=round(lon, 6),
            raio_m=raio, relatos=len(g), sinais_apagao=sinais, protocolos=protocolos,
            primeiro=min(c.ts for c in g), ultimo=max(c.ts for c in g),
            encaminhar_para=encaminhar(["falta_de_energia"] if apagao else ["trecho_sem_luz"]),
            motivos=motivos,
        ))
    return sorted(regioes, key=lambda r: (r.tipo != TipoRegiao.apagao_regiao, -r.relatos))
