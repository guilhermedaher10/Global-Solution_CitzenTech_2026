"""Despachante de chamados de iluminacao.

Uso:
    python -m src.main                         # processa PENDENTE/APROVADO
    python -m src.main --dry-run               # so decide e loga, sem enviar nem alterar o CSV
    python -m src.main --hoje 2026-11-09       # fixa a data (testes/demo reproduzivel)
    python -m src.main --sincronizar-protocolos  # le outbox/protocolos_portal.csv (UiPath)
"""
from __future__ import annotations

import argparse
import csv
import traceback
import uuid
from dataclasses import replace
from datetime import date
from pathlib import Path

from . import regras, repositorio
from .anonimizacao import preparar_foto
from .chamado import gerar_pdf
from .config import Config
from .envio import enviar
from .logger import Auditoria, configurar_logging
from .notificacao import notificar_n8n

STATUS_PROCESSAVEIS = {"PENDENTE", "APROVADO"}


def run(cfg: Config, hoje: date, dry_run: bool = False) -> dict:
    execucao_id = uuid.uuid4().hex[:8]
    log = configurar_logging(cfg.logs_dir)
    audit = Auditoria(cfg.logs_dir, execucao_id)
    log.info("=== execucao %s | hoje=%s | modo=%s | dry_run=%s ===",
             execucao_id, hoje, cfg.envio_modo, dry_run)

    campos, linhas = repositorio.ler(cfg.csv_path)
    fila = [r for r in linhas if (r["status"] or "").strip().upper() in STATUS_PROCESSAVEIS]
    log.info("%d ocorrencia(s) para processar de %d no total", len(fila), len(linhas))

    resumo = {"processadas": 0, "enviadas": 0, "urgentes": 0, "normais": 0, "duplicadas": 0,
              "falhas_dados": 0, "revisao_humana": 0, "erros": 0}
    revisao_ids: list[str] = []
    falhas: list[dict] = []

    for o in fila:  # LOOP sobre a colecao de ocorrencias
        resumo["processadas"] += 1
        oid = o["id"]
        try:
            d = regras.avaliar(o, linhas, hoje, cfg)  # DECISOES (dados, duplicidade, IA, prioridade)

            if d.acao == regras.FALHA_DADOS:
                resumo["falhas_dados"] += 1
                falhas.append({"id": oid, "motivo": d.motivo})
                novo_status = "FALHA_DADOS"
            elif d.acao == regras.DESCARTAR_DUPLICADO:
                resumo["duplicadas"] += 1
                novo_status = "DESCARTADO_DUPLICADO"
            elif d.acao == regras.REVISAO_HUMANA:
                resumo["revisao_humana"] += 1
                revisao_ids.append(oid)
                novo_status = "REVISAO_HUMANA"
            else:
                novo_status = None  # definido apos o envio

            if d.acao == regras.ENVIAR:
                if dry_run:
                    log.info("[dry-run] %s seria enviada como %s (%s)", oid, d.prioridade, d.motivo)
                    audit.registrar(oid, "DECISAO", "DRY_RUN_ENVIAR", f"{d.prioridade}: {d.motivo}")
                    continue
                pasta_chamados = cfg.outbox_dir / "chamados"
                foto_limpa = pasta_chamados / f"foto_{oid}.jpg"
                regioes = preparar_foto(cfg.base_dir / o["foto"], foto_limpa)
                if regioes is None:
                    log.warning("%s: desfoque de rostos/placas indisponivel (opencv ou cascatas "
                                "ausentes); foto enviada apenas sem EXIF", oid)
                pdf = gerar_pdf(o, d, foto_limpa, pasta_chamados, cfg, hoje)
                res = enviar(o, d, pdf, cfg, hoje, log)
                o.update(status=res.status, prioridade=d.prioridade, protocolo=res.protocolo,
                         data_envio=hoje.isoformat(), chamado_pdf=str(pdf.name),
                         observacao=d.motivo)
                resumo["enviadas"] += 1
                resumo["urgentes" if d.prioridade == "URGENTE" else "normais"] += 1
                audit.registrar(oid, "ENVIO", res.status, f"{d.prioridade} via {res.canal}")
                log.info("%s -> %s (%s via %s)", oid, res.status, d.prioridade, res.canal)
            else:
                if dry_run:
                    log.info("[dry-run] %s -> %s (%s)", oid, novo_status, d.motivo)
                    audit.registrar(oid, "DECISAO", f"DRY_RUN_{novo_status}", d.motivo)
                    continue
                o.update(status=novo_status, observacao=d.motivo)
                audit.registrar(oid, "DECISAO", novo_status, d.motivo)
                log.info("%s -> %s (%s)", oid, novo_status, d.motivo)

        except Exception as e:  # noqa: BLE001  EXCECOES: um item ruim nao derruba o lote (inclui ErroEnvio)
            resumo["erros"] += 1
            log.error("%s: erro inesperado: %s\n%s", oid, e, traceback.format_exc())
            audit.registrar(oid, "ERRO", "ERRO", str(e))
            if not dry_run:
                o.update(status="ERRO", observacao=str(e)[:200])

        if not dry_run:
            repositorio.salvar(cfg.csv_path, campos, linhas)  # persiste item a item

    log.info("resumo: %s", resumo)
    notificar_n8n(
        {"execucao_id": execucao_id, "data": hoje.isoformat(), "resumo": resumo,
         "itens_revisao": revisao_ids, "falhas": falhas},
        cfg, log,
    )
    return resumo


def sincronizar_protocolos(cfg: Config, hoje: date) -> int:
    """Le outbox/protocolos_portal.csv (gerado pelo UiPath) e fecha o ciclo no CSV/dashboard."""
    log = configurar_logging(cfg.logs_dir)
    audit = Auditoria(cfg.logs_dir, uuid.uuid4().hex[:8])
    origem = cfg.outbox_dir / "protocolos_portal.csv"
    if not origem.exists():
        log.warning("sincronizacao: %s nao encontrado", origem)
        return 0
    with origem.open(newline="", encoding="utf-8") as f:
        protocolos = {r["id"]: r["protocolo"] for r in csv.DictReader(f)}
    campos, linhas = repositorio.ler(cfg.csv_path)
    n = 0
    for o in linhas:
        if o["status"] == "FILA_PORTAL" and o["id"] in protocolos:
            o.update(status="PROTOCOLADO", protocolo=protocolos[o["id"]])
            audit.registrar(o["id"], "SINCRONIZAR", "PROTOCOLADO", protocolos[o["id"]])
            n += 1
    repositorio.salvar(cfg.csv_path, campos, linhas)
    log.info("sincronizacao: %d ocorrencia(s) protocolada(s)", n)
    return n


def main() -> None:
    p = argparse.ArgumentParser(description="Despachante de chamados de iluminacao")
    p.add_argument("--csv", type=Path, help="caminho da tabela de ocorrencias")
    p.add_argument("--hoje", type=date.fromisoformat, default=date.today())
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--sincronizar-protocolos", action="store_true")
    a = p.parse_args()

    cfg = Config.from_env()
    if a.csv:
        cfg = replace(cfg, csv_path=a.csv)
    if a.sincronizar_protocolos:
        sincronizar_protocolos(cfg, a.hoje)
    else:
        run(cfg, a.hoje, a.dry_run)


if __name__ == "__main__":
    main()
