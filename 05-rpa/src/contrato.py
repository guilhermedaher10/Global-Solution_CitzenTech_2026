"""Contrato com os outros componentes do grupo (docs/arquitetura.md na raiz do repositorio).

Entrada: o JSON da Visao, versao 1.1 (04-visao-computacional/docs/integracao.md), achatado em
uma linha de chamado. Ciclo de vida do chamado, compartilhado com o backend e o app:

    recebido -> validado (Visao) -> confirmado (atendente) -> encaminhado (RPA)
             -> em_reparo -> resolvido        (ou recusado, com motivo)

O RPA so pega chamados `confirmado` e os leva a `encaminhado`.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from pathlib import Path

VERSAO_CONTRATO = "1.1"

RECEBIDO = "recebido"
VALIDADO = "validado"
CONFIRMADO = "confirmado"
ENCAMINHADO = "encaminhado"
EM_REPARO = "em_reparo"
RESOLVIDO = "resolvido"
RECUSADO = "recusado"

NIVEIS = ("alta", "media", "baixa")

# id_captura vira nome de arquivo (PDF, foto, e-mail): so caracteres seguros.
ID_VALIDO = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _txt(valor: object) -> str:
    return "" if valor is None else str(valor)


def _juntar(itens: object, sep: str) -> str:
    return sep.join(str(i) for i in (itens or []))


def abrir_chamado(d: dict) -> bool:
    """validacao.abrir_chamado: a Visao considerou a foto evidencia valida?"""
    return bool((d.get("validacao") or {}).get("abrir_chamado"))


def de_visao_v11(d: dict) -> dict:
    """Achata o JSON da Visao v1.1 numa linha de chamado (sem foto nem status)."""
    id_ = d.get("id_captura")
    if not isinstance(id_, str) or not ID_VALIDO.match(id_):
        raise ValueError(f"id_captura invalido: {id_!r}")
    loc = d.get("localizacao") or {}
    res = d.get("resumo") or {}
    val = d.get("validacao") or {}
    pri = d.get("prioridade") or {}
    fus = d.get("fusao") or {}
    mod = d.get("modelo") or {}
    return {
        "id_captura": id_,
        "timestamp": _txt(d.get("timestamp")),
        "origem": _txt(d.get("origem")),
        "latitude": _txt(loc.get("latitude")),
        "longitude": _txt(loc.get("longitude")),
        "sensor_lux": _txt(d.get("sensor_lux")),
        "status_trecho": _txt(res.get("status_trecho")),
        "postes_apagados": _txt(res.get("postes_apagados")),
        "tipos_chamado": _juntar(fus.get("tipos_chamado"), "|"),
        "confirmacao": _txt(fus.get("confirmacao")),
        "prioridade_nivel": _txt(pri.get("nivel")),
        "prioridade_pontuacao": _txt(pri.get("pontuacao")),
        "fatores": _juntar(pri.get("fatores"), " | "),
        "motivos": _juntar(val.get("motivos"), " | "),
        "modelo": f"{_txt(mod.get('nome'))} {_txt(mod.get('versao'))}".strip(),
    }


def foto_do_evento(d: dict, base_dir: Path, pasta: str = "fotos") -> str:
    """Caminho (relativo a base_dir) da foto do chamado, ou '' se nao ha foto.

    A Visao nao guarda imagem (privacidade.imagem_armazenada=false); ela so devolve a foto
    anonimizada em `imagem_anonimizada_base64` quando pedido. Se vier, gravamos em fotos/<id>.jpg.
    """
    rel = f"{pasta}/{d['id_captura']}.jpg"
    destino = base_dir / rel
    b64 = d.get("imagem_anonimizada_base64")
    if b64:
        try:
            dados = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            return ""
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)
        return rel
    return rel if destino.is_file() else ""


def ler_eventos(caminho: Path) -> list[dict]:
    """Le um .json (objeto ou lista), um .jsonl (um evento por linha) ou uma pasta deles."""
    if caminho.is_dir():
        eventos: list[dict] = []
        for p in sorted(caminho.iterdir()):
            if p.suffix.lower() in (".json", ".jsonl"):
                eventos += ler_eventos(p)
        return eventos
    texto = caminho.read_text(encoding="utf-8")
    if caminho.suffix.lower() == ".jsonl":
        return [json.loads(linha) for linha in texto.splitlines() if linha.strip()]
    dado = json.loads(texto)
    return dado if isinstance(dado, list) else [dado]


def importar_eventos(eventos: list[dict], ids_existentes: set[str], base_dir: Path,
                     confirmar: bool = False) -> tuple[list[dict], list[str]]:
    """Converte eventos da Visao em linhas de chamado. Devolve (linhas, avisos).

    Status inicial: `validado` se a Visao mandou abrir chamado (ou `confirmado` com
    confirmar=True, que simula o atendente na demo), senao `recusado`.
    Eventos repetidos (mesmo id_captura) sao ignorados: importar duas vezes nao duplica.
    """
    linhas: list[dict] = []
    avisos: list[str] = []
    vistos = set(ids_existentes)
    for ev in eventos:
        try:
            linha = de_visao_v11(ev)
        except ValueError as e:
            avisos.append(str(e))
            continue
        cid = linha["id_captura"]
        if cid in vistos:
            avisos.append(f"{cid}: ja existe, ignorado")
            continue
        vistos.add(cid)
        linha["foto"] = foto_do_evento(ev, base_dir)
        if abrir_chamado(ev):
            linha["status"] = CONFIRMADO if confirmar else VALIDADO
        else:
            linha["status"] = RECUSADO
        linhas.append(linha)
    return linhas, avisos
