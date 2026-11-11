"""Teste ponta a ponta: sucesso, decisao e falha, com logs de evidencia."""
import csv
from dataclasses import replace
from datetime import date

import pytest

from src import repositorio
from src.envio import ErroEnvio, com_retry
from src.main import run, sincronizar_protocolos

HOJE = date(2026, 11, 9)


def status_por_id(cfg) -> dict:
    _, linhas = repositorio.ler(cfg.csv_path)
    return {r["id"]: r["status"] for r in linhas}


def test_fluxo_completo(cfg):
    resumo = run(cfg, HOJE)

    assert resumo == {"processadas": 10, "enviadas": 5, "urgentes": 3, "normais": 2,
                      "duplicadas": 2, "falhas_dados": 2, "revisao_humana": 1, "erros": 0}

    s = status_por_id(cfg)
    assert s["O-001"] == "ENVIADO"                 # sucesso normal
    assert s["O-002"] == "ENVIADO"                 # urgente (escola)
    assert s["O-003"] == "ENVIADO"                 # urgente (escuridao severa)
    assert s["O-004"] == "DESCARTADO_DUPLICADO"    # duplicado de chamado antigo
    assert s["O-005"] == "FALHA_DADOS"             # sem coordenada
    assert s["O-006"] == "REVISAO_HUMANA"          # confianca baixa
    assert s["O-007"] == "FALHA_DADOS"             # foto inexistente
    assert s["O-008"] == "DESCARTADO_DUPLICADO"    # duplicado dentro do proprio lote
    assert s["O-009"] == "ENVIADO"                 # urgente (ponto de onibus)
    assert s["O-010"] == "ENVIADO"                 # aprovado por humano

    emails = list((cfg.outbox_dir / "emails").glob("*.eml"))
    pdfs = list((cfg.outbox_dir / "chamados").glob("chamado_*.pdf"))
    assert len(emails) == 5 and len(pdfs) == 5
    assert (cfg.logs_dir / "auditoria.csv").exists()


def test_reexecucao_e_idempotente(cfg):
    run(cfg, HOJE)
    segunda = run(cfg, HOJE)
    # so sobra o item em REVISAO_HUMANA, que nao e reprocessado sem aprovacao
    assert segunda["processadas"] == 0 and segunda["enviadas"] == 0


def test_dry_run_nao_altera_nada(cfg):
    antes = cfg.csv_path.read_text(encoding="utf-8")
    run(cfg, HOJE, dry_run=True)
    assert cfg.csv_path.read_text(encoding="utf-8") == antes
    assert not (cfg.outbox_dir / "emails").exists()


def test_modo_portal_e_sincronizacao(cfg):
    cfg = replace(cfg, envio_modo="portal")
    run(cfg, HOJE)
    assert status_por_id(cfg)["O-002"] == "FILA_PORTAL"

    with (cfg.outbox_dir / "fila_portal.csv").open(encoding="utf-8") as f:
        fila = list(csv.DictReader(f))
    assert len(fila) == 5

    with (cfg.outbox_dir / "protocolos_portal.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "protocolo"])
        w.writerow(["O-002", "PM-2026-0001"])
    assert sincronizar_protocolos(cfg, HOJE) == 1
    assert status_por_id(cfg)["O-002"] == "PROTOCOLADO"


def test_falha_de_smtp_nao_derruba_o_lote(cfg, monkeypatch):
    import smtplib

    def sempre_falha(*a, **k):
        raise ConnectionRefusedError("smtp fora do ar")

    monkeypatch.setattr(smtplib, "SMTP", sempre_falha)
    cfg = replace(cfg, envio_modo="smtp", smtp_host="localhost", max_tentativas=2)
    resumo = run(cfg, HOJE)

    # Os envios falharam, mas todos foram tentados e o lote seguiu. Como O-001 nao chegou a ser
    # enviado, O-008 (mesmo poste) deixa de ser duplicado e tambem tenta enviar: 6 erros.
    assert resumo["erros"] == 6
    assert resumo["duplicadas"] == 1       # so O-004 (chamado antigo ja enviado)
    assert resumo["falhas_dados"] == 2     # o resto do lote seguiu normalmente
    assert status_por_id(cfg)["O-001"] == "ERRO"


def test_retry_recupera_apos_falha_transitoria():
    chamadas = {"n": 0}

    def instavel():
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise TimeoutError("lento")
        return "ok"

    import logging
    assert com_retry(instavel, 3, 0.0, logging.getLogger("t"), "teste") == "ok"
    assert chamadas["n"] == 3


def test_retry_esgotado_levanta_erro():
    import logging

    def falha():
        raise TimeoutError("lento")

    with pytest.raises(ErroEnvio):
        com_retry(falha, 2, 0.0, logging.getLogger("t"), "teste")
