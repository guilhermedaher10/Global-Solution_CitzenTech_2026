"""Agrupa chamados duplicados por proximidade.

Dois chamados sao do mesmo trecho quando:
  1. estao a no maximo `raio_agrupamento_m` metros um do outro; e
  2. tem ao menos um tipo em comum (poste e buraco na mesma rua vao para setores diferentes).

Ordem: o chamado de maior pontuacao vira o principal; os demais sao anexados a ele (so o
principal e encaminhado). Um chamado tambem e anexado a outro JA encaminhado (ou na fila do
portal) nos ultimos `janela_agrupamento_dias`, em vez de abrir um novo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import asin, cos, radians, sin, sqrt

from . import regras
from .config import Config
from .contrato import ENCAMINHADO, EM_REPARO

RAIO_TERRA_M = 6_371_000


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia em metros entre dois pontos (haversine)."""
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * RAIO_TERRA_M * asin(sqrt(a))


@dataclass
class Grupo:
    principal: dict
    membros: list[tuple[dict, float]] = field(default_factory=list)  # (chamado, distancia em m)


@dataclass
class Plano:
    novos: list[Grupo] = field(default_factory=list)
    anexos: list[tuple[dict, dict, float]] = field(default_factory=list)  # (chamado, existente, m)


def _distancia_se_mesmo_trecho(a: dict, b: dict, raio_m: float) -> float | None:
    try:
        d = distancia_m(float(a["latitude"]), float(a["longitude"]),
                        float(b["latitude"]), float(b["longitude"]))
    except (ValueError, KeyError):
        return None
    if d <= raio_m and regras.tipos(a) & regras.tipos(b):
        return d
    return None


def _mais_proximo(o: dict, candidatos: list[dict], raio_m: float) -> tuple[dict, float] | None:
    melhor: tuple[dict, float] | None = None
    for c in candidatos:
        d = _distancia_se_mesmo_trecho(o, c, raio_m)
        if d is not None and (melhor is None or d < melhor[1]):
            melhor = (c, d)
    return melhor


def _ja_encaminhado_recente(r: dict, hoje: date, janela_dias: int) -> bool:
    if r.get("chamado_principal"):  # so anexa a chamados principais
        return False
    ativo = r.get("status") in (ENCAMINHADO, EM_REPARO) or r.get("rpa_etapa") == "na_fila_portal"
    if not ativo:
        return False
    try:
        enviado_em = date.fromisoformat(r.get("data_encaminhamento", ""))
    except ValueError:
        return False
    return 0 <= (hoje - enviado_em).days <= janela_dias


def montar_plano(validos: list[dict], todas: list[dict], hoje: date, cfg: Config) -> Plano:
    ids_lote = {o["id_captura"] for o in validos}
    existentes = [r for r in todas
                  if r["id_captura"] not in ids_lote
                  and _ja_encaminhado_recente(r, hoje, cfg.janela_agrupamento_dias)]

    plano = Plano()
    ordenados = sorted(validos, key=lambda o: (-regras.pontuacao(o), o.get("timestamp", ""),
                                               o["id_captura"]))
    for o in ordenados:
        existente = _mais_proximo(o, existentes, cfg.raio_agrupamento_m)
        if existente:
            plano.anexos.append((o, existente[0], existente[1]))
            continue
        principais = [g.principal for g in plano.novos]
        proximo = _mais_proximo(o, principais, cfg.raio_agrupamento_m)
        if proximo:
            grupo = next(g for g in plano.novos if g.principal is proximo[0])
            grupo.membros.append((o, proximo[1]))
        else:
            plano.novos.append(Grupo(principal=o))
    return plano
