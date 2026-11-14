"""Validacao dos dados do chamado. (Agrupamento de duplicados: agrupamento.py)

A prioridade NAO e calculada aqui: vem pronta da Visao (prioridade.nivel e pontuacao) e e
usada para ordenar a fila. A confirmacao (sensor + foto + atendente) tambem vem de fora.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .contrato import ID_VALIDO, NIVEIS

ENVIAR = "ENVIAR"
FALHA_DADOS = "FALHA_DADOS"


@dataclass(frozen=True)
class Decisao:
    acao: str
    motivo: str


def tipos(o: dict) -> set[str]:
    """Tipos do chamado (fusao.tipos_chamado). Sem tipo informado, vale 'geral'."""
    brutos = {t.strip() for t in (o.get("tipos_chamado") or "").split("|") if t.strip()}
    return brutos or {"geral"}


def pontuacao(o: dict) -> int:
    try:
        return int(float(o.get("prioridade_pontuacao") or 0))
    except ValueError:
        return 0


def validar_dados(o: dict, base_dir: Path) -> list[str]:
    """Devolve a lista de problemas encontrados (vazia = dados ok)."""
    erros: list[str] = []
    if not ID_VALIDO.match(o.get("id_captura") or ""):
        erros.append("id_captura invalido")

    for campo, limite in (("latitude", 90), ("longitude", 180)):
        bruto = (o.get(campo) or "").strip()
        if not bruto:
            erros.append(f"{campo} ausente")
            continue
        try:
            valor = float(bruto)
        except ValueError:
            erros.append(f"{campo} invalida: {bruto!r}")
            continue
        if abs(valor) > limite:
            erros.append(f"{campo} fora do intervalo")

    foto = (o.get("foto") or "").strip()
    if not foto:
        erros.append("foto ausente")
    else:
        caminho = (base_dir / foto).resolve()
        if not caminho.is_relative_to(base_dir.resolve()):
            erros.append("foto fora da pasta de dados")
        elif not caminho.is_file():
            erros.append(f"arquivo de foto nao encontrado: {foto}")

    if (o.get("prioridade_nivel") or "").strip() not in NIVEIS:
        erros.append(f"prioridade_nivel invalido: {o.get('prioridade_nivel')!r}")
    bruta = (o.get("prioridade_pontuacao") or "").strip()
    if bruta:
        try:
            float(bruta)
        except ValueError:
            erros.append("prioridade_pontuacao invalida")
    return erros


def avaliar(o: dict, cfg: Config) -> Decisao:
    erros = validar_dados(o, cfg.base_dir)
    if erros:
        return Decisao(FALHA_DADOS, "; ".join(erros))
    return Decisao(ENVIAR, "dados validos")
