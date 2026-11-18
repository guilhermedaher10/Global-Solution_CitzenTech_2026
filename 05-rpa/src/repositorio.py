"""Leitura/escrita da tabela de chamados: CSV (padrão, offline) ou a API da central do Vésper.

O arquitetura.md do grupo prevê que o RPA leia/escreva "no banco ou na API do backend". As duas
fontes têm a mesma assinatura (ler/salvar), então o resto do robô não muda:

- RPA_FONTE=csv (padrão): data/chamados.csv faz o papel do banco (testes e demo offline).
- RPA_FONTE=api: lê os chamados da central da Visão (GET {VESPER_API_URL}/v1/chamados) e devolve
  o andamento pela mesma API (POST /v1/chamados/{protocolo}/status), que aparece na linha do
  tempo do site. O estado interno do RPA (etapa, PDF, protocolo da prefeitura) fica num CSV local
  ao lado (estado_rpa_api.csv), porque a central guarda só o ciclo de vida do chamado.
  A central NÃO guarda fotos (LGPD): nesse modo o chamado vai sem imagem (ver regras/chamado).
"""
from __future__ import annotations

import csv
import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger("rpa")

# Colunas vindas do contrato da Visao (ver contrato.de_visao_v11) + status do ciclo de vida
# + colunas escritas pelo RPA (rpa_etapa, chamado_principal, protocolo, ...).
CAMPOS_PADRAO = [
    "id_captura", "timestamp", "origem", "latitude", "longitude", "sensor_lux",
    "status_trecho", "postes_apagados", "tipos_chamado", "confirmacao",
    "prioridade_nivel", "prioridade_pontuacao", "fatores", "motivos", "modelo", "foto",
    "status",
    "rpa_etapa", "chamado_principal", "protocolo", "data_encaminhamento", "chamado_pdf",
    "motivo_rpa",
]
# Colunas que só o RPA escreve (no modo API ficam no CSV de estado local).
CAMPOS_RPA = ["rpa_etapa", "chamado_principal", "protocolo", "data_encaminhamento", "chamado_pdf",
              "motivo_rpa"]
API_PADRAO = "https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io"

# Status de cada chamado na central como o RPA leu/gravou por último (evita POST repetido).
_status_central: dict[str, str] = {}


def fonte() -> str:
    return os.getenv("RPA_FONTE", "csv").strip().lower()


def api_url() -> str:
    return os.getenv("VESPER_API_URL", API_PADRAO).rstrip("/")


def ler(csv_path: Path) -> tuple[list[str], list[dict]]:
    return _ler_api(csv_path) if fonte() == "api" else _ler_csv(csv_path)


def salvar(csv_path: Path, campos: list[str], linhas: list[dict]) -> None:
    if fonte() == "api":
        _salvar_api(csv_path, campos, linhas)
    else:
        _salvar_csv(csv_path, campos, linhas)


# ---------------------------------------------------------------- CSV
def _ler_csv(csv_path: Path) -> tuple[list[str], list[dict]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        campos = list(leitor.fieldnames or [])
        linhas = [dict(r) for r in leitor]
    for c in CAMPOS_PADRAO:
        if c not in campos:
            campos.append(c)
    for r in linhas:
        for c in campos:
            r.setdefault(c, "")
            if r[c] is None:
                r[c] = ""
    return campos, linhas


def _salvar_csv(csv_path: Path, campos: list[str], linhas: list[dict]) -> None:
    """Escrita atomica: grava num temporario e troca, para nao corromper o CSV se o robo cair."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = csv_path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)
    os.replace(tmp, csv_path)


# ---------------------------------------------------------------- API da central do Vésper
def _pedir(metodo: str, caminho: str, corpo: dict | None = None, timeout: float = 60) -> object:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(f"{api_url()}{caminho}", data=dados, method=metodo,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # 60 s: a API na Azure pode estar "acordando"
        return json.loads(r.read() or b"null")


def de_central(c: dict) -> dict:
    """Um chamado da central (GET /v1/chamados) vira uma linha do RPA. id_captura = protocolo VSP."""
    junta = lambda v, sep: sep.join(str(x) for x in (v or []))  # noqa: E731
    return {
        "id_captura": c.get("protocolo") or "",
        "timestamp": c.get("ts") or "",
        "origem": c.get("origem") or "",
        "latitude": "" if c.get("latitude") is None else str(c["latitude"]),
        "longitude": "" if c.get("longitude") is None else str(c["longitude"]),
        "sensor_lux": "",
        "status_trecho": c.get("trecho") or "",
        "postes_apagados": "",
        "tipos_chamado": junta(c.get("tipos"), "|"),
        "confirmacao": c.get("evidencia") or "",
        "prioridade_nivel": c.get("nivel") or "",
        "prioridade_pontuacao": "" if c.get("pontos") is None else str(c["pontos"]),
        "fatores": junta(c.get("fatores"), " | "),
        "motivos": junta(c.get("motivos"), " | "),
        "modelo": "Visão Computacional (Vésper)",
        "foto": "",
        "status": c.get("status") or "",
        "fonte": "api",
        "endereco": c.get("endereco") or "",
    }


def _arquivo_estado(csv_path: Path) -> Path:
    return csv_path.parent / "estado_rpa_api.csv"


def _ler_api(csv_path: Path) -> tuple[list[str], list[dict]]:
    chamados = _pedir("GET", "/v1/chamados?limite=300")
    estado: dict[str, dict] = {}
    arq = _arquivo_estado(csv_path)
    if arq.exists():
        with arq.open(newline="", encoding="utf-8") as f:
            estado = {r["id_captura"]: r for r in csv.DictReader(f)}
    linhas = []
    for c in chamados:
        r = de_central(c)
        if not r["id_captura"]:
            continue
        for k in CAMPOS_RPA:
            r[k] = (estado.get(r["id_captura"]) or {}).get(k, "") or ""
        _status_central[r["id_captura"]] = r["status"]
        # já enviado à prefeitura mas a central não recebeu o aviso (estava fora do ar): reenvia no salvar
        if r["status"] == "confirmado" and r["rpa_etapa"] in ("enviado", "protocolado"):
            r["status"] = "encaminhado"
        linhas.append(r)
    log.info("central do Vésper: %d chamado(s) lido(s) de %s", len(linhas), api_url())
    return CAMPOS_PADRAO + ["fonte", "endereco"], linhas


# Transições permitidas na central (visao/central.py): o RPA só avança o ciclo, sem pular etapa.
_CAMINHO = {"encaminhado": ["encaminhado"], "em_reparo": ["encaminhado", "em_reparo"]}


def _salvar_api(csv_path: Path, campos: list[str], linhas: list[dict]) -> None:
    for r in linhas:
        cid, novo = r["id_captura"], (r.get("status") or "").strip().lower()
        antes = _status_central.get(cid, "")
        if novo == antes or novo not in _CAMINHO:
            continue
        nota = (f"RPA encaminhou: protocolo {r.get('protocolo') or 'pendente'}"
                + (f" · {r['chamado_pdf']}" if r.get("chamado_pdf") else "")
                + (f" · agrupado com {r['chamado_principal']}" if r.get("chamado_principal") else ""))
        for passo in _CAMINHO[novo]:
            if passo == antes:
                continue
            try:
                _pedir("POST", f"/v1/chamados/{cid}/status", {"status": passo, "nota": nota[:200]})
                _status_central[cid] = antes = passo
                log.info("%s: status na central -> %s", cid, passo)
            except urllib.error.HTTPError as e:
                log.error("%s: a central recusou %s (%s)", cid, passo, e.code)
                break
            except (urllib.error.URLError, TimeoutError) as e:
                log.error("%s: central indisponível (%s); tenta de novo na próxima execução", cid, e)
                break
    # estado interno do RPA (não existe na central)
    arq = _arquivo_estado(csv_path)
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_captura"] + CAMPOS_RPA, extrasaction="ignore")
        w.writeheader()
        w.writerows(r for r in linhas if any(r.get(k) for k in CAMPOS_RPA))
    os.replace(tmp, arq)
