"""Despachante de chamados de iluminacao (componente 05 RPA).

Pega chamados `confirmado` (aprovados pelo atendente), agrupa duplicados por proximidade,
registra na prefeitura e passa o status para `encaminhado`.

Uso:
    python -m src.main                           # processa os chamados confirmados
    python -m src.main --dry-run                 # so decide e loga, sem enviar nem alterar a tabela
    python -m src.main --hoje 2026-11-09         # fixa a data (testes/demo reproduzivel)
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
from .agrupamento import Grupo, montar_plano
from .anonimizacao import preparar_foto
from .chamado import gerar_pdf
from .config import Config
from .contrato import CONFIRMADO, EM_REPARO, ENCAMINHADO, VALIDADO
from .envio import enviar
from .logger import Auditoria, configurar_logging
from .notificacao import notificar_n8n

# Etapas internas do RPA (coluna rpa_etapa) em que o chamado ainda pode ser processado.
# `erro` volta para a fila: falha de rede/e-mail costuma ser passageira.
ETAPAS_PROCESSAVEIS = {"", "erro"}


def _status(o: dict) -> str:
    return (o.get("status") or "").strip().lower()


def _anexar(o: dict, principal: dict, distancia: float, hoje: date) -> None:
    """Liga `o` ao chamado principal. Se o principal ja foi encaminhado, `o` o acompanha."""
    o.update(rpa_etapa="agrupado", chamado_principal=principal["id_captura"],
             motivo_rpa=f"mesmo trecho do chamado {principal['id_captura']} (a {distancia:.0f} m)")
    if _status(principal) in (ENCAMINHADO, EM_REPARO):
        o.update(status=_status(principal), protocolo=principal["protocolo"],
                 data_encaminhamento=hoje.isoformat())


def run(cfg: Config, hoje: date, dry_run: bool = False) -> dict:
    execucao_id = uuid.uuid4().hex[:8]
    log = configurar_logging(cfg.logs_dir)
    audit = Auditoria(cfg.logs_dir, execucao_id)
    log.info("=== execucao %s | hoje=%s | modo=%s | dry_run=%s ===",
             execucao_id, hoje, cfg.envio_modo, dry_run)

    campos, linhas = repositorio.ler(cfg.csv_path)

    def persistir() -> None:
        if not dry_run:
            repositorio.salvar(cfg.csv_path, campos, linhas)

    fila = [r for r in linhas if _status(r) == CONFIRMADO and r["rpa_etapa"] in ETAPAS_PROCESSAVEIS]
    aguardando = [r["id_captura"] for r in linhas if _status(r) == VALIDADO]
    log.info("%d chamado(s) confirmado(s) para processar; %d aguardando confirmacao do atendente",
             len(fila), len(aguardando))

    resumo = {"processadas": 0, "encaminhados": 0, "alta": 0, "media": 0, "baixa": 0,
              "agrupados": 0, "falhas_dados": 0, "erros": 0,
              "aguardando_confirmacao": len(aguardando)}
    falhas: list[dict] = []
    validos: list[dict] = []

    # LOOP 1: validacao dos dados de cada chamado
    for o in fila:
        resumo["processadas"] += 1
        cid = o["id_captura"]
        try:
            d = regras.avaliar(o, cfg)
            if d.acao == regras.FALHA_DADOS:
                resumo["falhas_dados"] += 1
                falhas.append({"id_captura": cid, "motivo": d.motivo})
                log.info("%s -> FALHA_DADOS (%s)", cid, d.motivo)
                audit.registrar(cid, "VALIDACAO", "DRY_RUN_FALHA_DADOS" if dry_run else "FALHA_DADOS",
                                d.motivo)
                if not dry_run:
                    o.update(rpa_etapa="falha_dados", motivo_rpa=d.motivo)
            else:
                validos.append(o)
        except Exception as e:  # noqa: BLE001  um item ruim nao derruba o lote
            resumo["erros"] += 1
            log.error("%s: erro inesperado na validacao: %s\n%s", cid, e, traceback.format_exc())
            audit.registrar(cid, "ERRO", "ERRO", str(e))
            if not dry_run:
                o.update(rpa_etapa="erro", motivo_rpa=str(e)[:200])
        persistir()

    # DECISAO: agrupamento por proximidade (os de maior prioridade viram principais)
    plano = montar_plano(validos, linhas, hoje, cfg)

    # Chamados que se juntam a um chamado que JA foi encaminhado: nao abrem chamado novo
    for o, existente, dist in plano.anexos:
        cid = o["id_captura"]
        msg = f"mesmo trecho do chamado {existente['id_captura']} (a {dist:.0f} m)"
        if dry_run:
            log.info("[dry-run] %s seria agrupado: %s", cid, msg)
            audit.registrar(cid, "AGRUPAR", "DRY_RUN_AGRUPADO", msg)
            continue
        _anexar(o, existente, dist, hoje)
        resumo["agrupados"] += 1
        audit.registrar(cid, "AGRUPAR", "AGRUPADO", msg)
        log.info("%s -> agrupado: %s", cid, msg)
        persistir()

    # LOOP 2: um chamado por grupo (o principal), com os membros anexados
    for g in plano.novos:
        _despachar(g, cfg, hoje, log, audit, resumo, dry_run)
        persistir()

    log.info("resumo: %s", resumo)
    if dry_run:
        log.info("dry-run: tabela intacta e n8n nao notificado")
    else:
        notificar_n8n(
            {"execucao_id": execucao_id, "data": hoje.isoformat(), "resumo": resumo,
             "itens_aguardando_confirmacao": aguardando, "falhas": falhas},
            cfg, log,
        )
    return resumo


def _despachar(g: Grupo, cfg: Config, hoje: date, log, audit: Auditoria, resumo: dict,
               dry_run: bool) -> None:
    o = g.principal
    cid = o["id_captura"]
    nivel = o["prioridade_nivel"]
    ids_membros = ", ".join(m["id_captura"] for m, _ in g.membros)
    if dry_run:
        log.info("[dry-run] %s seria encaminhado (%s, %s pts)%s", cid, nivel,
                 regras.pontuacao(o), f", consolidando {ids_membros}" if ids_membros else "")
        audit.registrar(cid, "DECISAO", "DRY_RUN_ENCAMINHAR", f"{nivel}: {len(g.membros)} agrupado(s)")
        for m, dist in g.membros:
            audit.registrar(m["id_captura"], "AGRUPAR", "DRY_RUN_AGRUPADO",
                            f"mesmo trecho de {cid} (a {dist:.0f} m)")
        return
    try:
        pasta = cfg.outbox_dir / "chamados"
        foto_limpa = pasta / f"foto_{cid}.jpg"
        regioes = preparar_foto(cfg.base_dir / o["foto"], foto_limpa)
        if regioes is None:
            log.warning("%s: desfoque de rostos/placas indisponivel (opencv ou cascatas ausentes); "
                        "foto enviada apenas sem EXIF", cid)
        pdf = gerar_pdf(o, g.membros, foto_limpa, pasta, cfg, hoje)
        res = enviar(o, len(g.membros), pdf, cfg, hoje, log)

        o.update(rpa_etapa=res.etapa, protocolo=res.protocolo, chamado_pdf=pdf.name,
                 data_encaminhamento=hoje.isoformat(), motivo_rpa="")
        if res.encaminhado:
            o["status"] = ENCAMINHADO
        for m, dist in g.membros:
            _anexar(m, o, dist, hoje)
            audit.registrar(m["id_captura"], "AGRUPAR", "AGRUPADO", f"mesmo trecho de {cid} (a {dist:.0f} m)")
        resumo["encaminhados"] += 1
        resumo[nivel] += 1
        resumo["agrupados"] += len(g.membros)
        audit.registrar(cid, "ENCAMINHAR", res.etapa.upper(), f"{nivel} via {res.canal}; "
                                                              f"{len(g.membros)} agrupado(s)")
        log.info("%s -> %s (%s via %s)%s", cid, res.etapa, nivel, res.canal,
                 f"; agrupou {ids_membros}" if ids_membros else "")
    except Exception as e:  # noqa: BLE001  inclui ErroEnvio; os membros ficam para a proxima execucao
        resumo["erros"] += 1
        log.error("%s: erro inesperado: %s\n%s", cid, e, traceback.format_exc())
        audit.registrar(cid, "ERRO", "ERRO", str(e))
        o.update(rpa_etapa="erro", motivo_rpa=str(e)[:200])


def sincronizar_protocolos(cfg: Config, hoje: date) -> int:
    """Le outbox/protocolos_portal.csv (gerado pelo UiPath) e fecha o ciclo: encaminhado + protocolo."""
    log = configurar_logging(cfg.logs_dir)
    audit = Auditoria(cfg.logs_dir, uuid.uuid4().hex[:8])
    origem = cfg.outbox_dir / "protocolos_portal.csv"
    if not origem.exists():
        log.warning("sincronizacao: %s nao encontrado", origem)
        return 0
    with origem.open(newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        if not {"id_captura", "protocolo"} <= set(leitor.fieldnames or []):
            log.error("sincronizacao: %s precisa das colunas id_captura e protocolo", origem)
            return 0
        protocolos = {r["id_captura"]: r["protocolo"] for r in leitor if r["protocolo"]}

    campos, linhas = repositorio.ler(cfg.csv_path)
    n = 0
    for o in linhas:
        cid = o["id_captura"]
        if o["rpa_etapa"] != "na_fila_portal" or cid not in protocolos:
            continue
        o.update(status=ENCAMINHADO, rpa_etapa="protocolado", protocolo=protocolos[cid])
        audit.registrar(cid, "SINCRONIZAR", "PROTOCOLADO", protocolos[cid])
        n += 1
        for m in linhas:  # os chamados agrupados acompanham o principal
            if m["chamado_principal"] == cid and m["rpa_etapa"] == "agrupado" and _status(m) == CONFIRMADO:
                m.update(status=ENCAMINHADO, protocolo=protocolos[cid],
                         data_encaminhamento=o["data_encaminhamento"])
                audit.registrar(m["id_captura"], "SINCRONIZAR", "ENCAMINHADO", protocolos[cid])
    repositorio.salvar(cfg.csv_path, campos, linhas)
    log.info("sincronizacao: %d chamado(s) principal(is) protocolado(s)", n)
    return n


def main() -> None:
    p = argparse.ArgumentParser(description="Despachante de chamados de iluminacao")
    p.add_argument("--csv", type=Path, help="caminho da tabela de chamados")
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
