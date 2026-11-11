"""Regras de negocio do robo: validacao, duplicidade, revisao humana e prioridade."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import Config

STATUS_JA_ENVIADOS = {"ENVIADO", "FILA_PORTAL", "PROTOCOLADO"}

ENVIAR = "ENVIAR"
DESCARTAR_DUPLICADO = "DESCARTAR_DUPLICADO"
FALHA_DADOS = "FALHA_DADOS"
REVISAO_HUMANA = "REVISAO_HUMANA"


@dataclass(frozen=True)
class Decisao:
    acao: str
    motivo: str
    prioridade: str = ""  # URGENTE | NORMAL (so quando acao == ENVIAR)


def _sim(valor: str) -> bool:
    return str(valor).strip().lower() in {"1", "true", "sim", "s", "yes"}


def validar_dados(o: dict, base_dir: Path) -> list[str]:
    """Devolve a lista de problemas encontrados (vazia = dados ok)."""
    erros: list[str] = []
    if not (o.get("poste_id") or "").strip():
        erros.append("poste_id ausente")

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
    elif not (base_dir / foto).is_file():
        erros.append(f"arquivo de foto nao encontrado: {foto}")

    try:
        conf = float(o.get("confianca_ia") or "")
        if not 0 <= conf <= 1:
            erros.append("confianca_ia fora de 0..1")
    except ValueError:
        erros.append("confianca_ia invalida")
    return erros


def chamado_recente(o: dict, todas: list[dict], hoje: date, janela_dias: int) -> str | None:
    """ID de um chamado ja enviado para o mesmo poste dentro da janela, se existir."""
    for r in todas:
        if r.get("id") == o.get("id"):
            continue
        if r.get("poste_id") != o.get("poste_id"):
            continue
        if r.get("status") not in STATUS_JA_ENVIADOS:
            continue
        try:
            enviado_em = date.fromisoformat(r.get("data_envio", ""))
        except ValueError:
            continue
        if 0 <= (hoje - enviado_em).days <= janela_dias:
            return r.get("id")
    return None


def classificar_prioridade(o: dict) -> tuple[str, str]:
    """URGENTE se houver escola/ponto de onibus por perto ou escuridao severa."""
    if _sim(o.get("escola_proxima", "")):
        return "URGENTE", "escola proxima"
    if _sim(o.get("ponto_onibus_proximo", "")):
        return "URGENTE", "ponto de onibus proximo"
    if (o.get("severidade") or "").strip().lower() == "severa":
        return "URGENTE", "escuridao severa"
    return "NORMAL", "sem fatores de risco adicionais"


def avaliar(o: dict, todas: list[dict], hoje: date, cfg: Config) -> Decisao:
    """Ordem das decisoes: dados -> duplicidade -> confianca da IA -> prioridade."""
    erros = validar_dados(o, cfg.base_dir)
    if erros:
        return Decisao(FALHA_DADOS, "; ".join(erros))

    original = chamado_recente(o, todas, hoje, cfg.janela_duplicidade_dias)
    if original:
        return Decisao(DESCARTAR_DUPLICADO, f"ja existe chamado {original} para o poste {o['poste_id']}")

    aprovado = (o.get("status") or "").strip().upper() == "APROVADO"
    if not aprovado and float(o["confianca_ia"]) < cfg.limiar_confianca:
        return Decisao(
            REVISAO_HUMANA,
            f"confianca {float(o['confianca_ia']):.2f} abaixo do limiar {cfg.limiar_confianca:.2f}",
        )

    prioridade, motivo = classificar_prioridade(o)
    return Decisao(ENVIAR, motivo, prioridade)
