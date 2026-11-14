"""Teste ponta a ponta: sucesso, decisao e falha, com logs de evidencia."""
import csv
import logging
from dataclasses import replace
from datetime import date

import pytest

from src import main as robo
from src import repositorio
from src.envio import ErroEnvio, com_retry
from src.main import run, sincronizar_protocolos

HOJE = date(2026, 11, 9)


def tabela(cfg) -> dict:
    _, linhas = repositorio.ler(cfg.csv_path)
    return {r["id_captura"]: r for r in linhas}


def ordem_de_encaminhamento(cfg) -> list[str]:
    with (cfg.logs_dir / "auditoria.csv").open(encoding="utf-8") as f:
        return [r["id_captura"] for r in csv.DictReader(f) if r["acao"] == "ENCAMINHAR"]


def test_fluxo_completo(cfg):
    resumo = run(cfg, HOJE)

    assert resumo == {"processadas": 10, "encaminhados": 5, "alta": 2, "media": 2, "baixa": 1,
                      "agrupados": 3, "falhas_dados": 2, "erros": 0, "aguardando_confirmacao": 1}

    t = tabela(cfg)
    for cid in ("C-001", "C-003", "C-004", "C-005", "C-007"):   # principais
        assert (t[cid]["status"], t[cid]["rpa_etapa"]) == ("encaminhado", "enviado"), cid
        assert t[cid]["protocolo"] == f"CH-20261109-{cid}"
        assert t[cid]["data_encaminhamento"] == "2026-11-09"

    # agrupados no mesmo trecho: acompanham o principal e usam o mesmo protocolo
    for membro, principal in (("C-002", "C-001"), ("C-006", "C-005")):
        assert (t[membro]["status"], t[membro]["rpa_etapa"]) == ("encaminhado", "agrupado")
        assert t[membro]["chamado_principal"] == principal
        assert t[membro]["protocolo"] == t[principal]["protocolo"]

    # C-010 juntou-se a C-000, que ja tinha sido encaminhado em 28/10: nao abre chamado novo
    assert t["C-010"]["chamado_principal"] == "C-000"
    assert t["C-010"]["protocolo"] == "CH-20261028-C-000"

    # falhas de dados: continuam `confirmado` e ficam marcadas, com o motivo
    assert (t["C-008"]["rpa_etapa"], "latitude ausente" in t["C-008"]["motivo_rpa"]) == ("falha_dados", True)
    assert (t["C-009"]["rpa_etapa"], t["C-009"]["motivo_rpa"]) == ("falha_dados", "foto ausente")
    assert t["C-008"]["status"] == t["C-009"]["status"] == "confirmado"

    # ainda nao confirmado pelo atendente: o robo nao toca
    assert (t["C-011"]["status"], t["C-011"]["rpa_etapa"]) == ("validado", "")

    assert len(list((cfg.outbox_dir / "emails").glob("*.eml"))) == 5
    assert len(list((cfg.outbox_dir / "chamados").glob("chamado_*.pdf"))) == 5
    assert (cfg.logs_dir / "auditoria.csv").exists()


def test_fila_e_ordenada_pela_prioridade_da_visao(cfg):
    run(cfg, HOJE)
    # pontuacoes: C-005=100, C-001=90, C-003=50, C-007=35, C-004=15
    assert ordem_de_encaminhamento(cfg) == ["C-005", "C-001", "C-003", "C-007", "C-004"]


def test_reexecucao_nao_reenvia_nada(cfg):
    run(cfg, HOJE)
    segunda = run(cfg, HOJE)
    assert segunda["processadas"] == 0 and segunda["encaminhados"] == 0
    assert segunda["aguardando_confirmacao"] == 1


def test_dry_run_nao_altera_nada(cfg):
    antes = cfg.csv_path.read_text(encoding="utf-8")
    resumo = run(cfg, HOJE, dry_run=True)
    assert cfg.csv_path.read_text(encoding="utf-8") == antes
    assert not (cfg.outbox_dir / "emails").exists()
    assert resumo["encaminhados"] == 0 and resumo["falhas_dados"] == 2


def test_chamado_corrigido_volta_para_a_fila(cfg):
    run(cfg, HOJE)
    campos, linhas = repositorio.ler(cfg.csv_path)
    for r in linhas:
        if r["id_captura"] == "C-008":   # alguem completou a coordenada que faltava
            r.update(latitude="-23.5700", longitude="-46.6500", rpa_etapa="", motivo_rpa="")
    repositorio.salvar(cfg.csv_path, campos, linhas)

    resumo = run(cfg, HOJE)
    assert resumo["processadas"] == 1 and resumo["encaminhados"] == 1
    assert tabela(cfg)["C-008"]["status"] == "encaminhado"


def test_atendente_confirma_e_o_robo_pega_na_proxima_execucao(cfg):
    run(cfg, HOJE)
    campos, linhas = repositorio.ler(cfg.csv_path)
    for r in linhas:
        if r["id_captura"] == "C-011":
            r["status"] = "confirmado"
    repositorio.salvar(cfg.csv_path, campos, linhas)

    resumo = run(cfg, HOJE)
    assert resumo["encaminhados"] == 1 and resumo["aguardando_confirmacao"] == 0
    assert tabela(cfg)["C-011"]["status"] == "encaminhado"


def test_n8n_recebe_resumo_e_lista_de_chamados_aguardando_o_atendente(cfg, monkeypatch):
    recebido = {}
    monkeypatch.setattr(robo, "notificar_n8n", lambda payload, c, log: recebido.update(payload))
    run(cfg, HOJE)
    assert recebido["itens_aguardando_confirmacao"] == ["C-011"]
    assert recebido["resumo"]["aguardando_confirmacao"] == 1
    assert {f["id_captura"] for f in recebido["falhas"]} == {"C-008", "C-009"}


def test_modo_portal_e_sincronizacao(cfg):
    cfg = replace(cfg, envio_modo="portal")
    run(cfg, HOJE)
    t = tabela(cfg)

    # principais ficam na fila do portal; o status so muda quando o portal devolve o protocolo
    assert (t["C-001"]["status"], t["C-001"]["rpa_etapa"], t["C-001"]["protocolo"]) == \
        ("confirmado", "na_fila_portal", "")
    assert (t["C-002"]["status"], t["C-002"]["rpa_etapa"]) == ("confirmado", "agrupado")
    # o que se juntou a um chamado ja protocolado acompanha na hora
    assert (t["C-010"]["status"], t["C-010"]["protocolo"]) == ("encaminhado", "CH-20261028-C-000")

    with (cfg.outbox_dir / "fila_portal.csv").open(encoding="utf-8") as f:
        fila = list(csv.DictReader(f))
    assert {r["id_captura"] for r in fila} == {"C-001", "C-003", "C-004", "C-005", "C-007"}
    c001 = next(r for r in fila if r["id_captura"] == "C-001")
    assert (c001["prioridade"], c001["agrupados"], c001["tipos_chamado"]) == ("alta", "1", "conserto_poste")

    with (cfg.outbox_dir / "protocolos_portal.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id_captura", "protocolo"])
        w.writerow(["C-001", "PM-2026-0001"])
    assert sincronizar_protocolos(cfg, HOJE) == 1

    t = tabela(cfg)
    assert (t["C-001"]["status"], t["C-001"]["rpa_etapa"], t["C-001"]["protocolo"]) == \
        ("encaminhado", "protocolado", "PM-2026-0001")
    assert (t["C-002"]["status"], t["C-002"]["protocolo"]) == ("encaminhado", "PM-2026-0001")
    assert t["C-005"]["status"] == "confirmado"  # o portal ainda nao devolveu o dele


def test_sincronizacao_com_arquivo_sem_as_colunas_esperadas(cfg):
    cfg = replace(cfg, envio_modo="portal")
    run(cfg, HOJE)
    cfg.outbox_dir.joinpath("protocolos_portal.csv").write_text("id,numero\nC-001,1\n", encoding="utf-8")
    assert sincronizar_protocolos(cfg, HOJE) == 0
    assert tabela(cfg)["C-001"]["rpa_etapa"] == "na_fila_portal"


def test_falha_de_smtp_nao_derruba_o_lote_e_o_reenvio_recupera(cfg, monkeypatch):
    import smtplib

    def sempre_falha(*a, **k):
        raise ConnectionRefusedError("smtp fora do ar")

    monkeypatch.setattr(smtplib, "SMTP", sempre_falha)
    com_falha = replace(cfg, envio_modo="smtp", smtp_host="localhost", max_tentativas=2)
    resumo = run(com_falha, HOJE)

    # os 5 envios falharam, mas todos foram tentados e o lote seguiu
    assert resumo["erros"] == 5 and resumo["encaminhados"] == 0
    assert resumo["falhas_dados"] == 2
    assert resumo["agrupados"] == 1   # so C-010, que nao depende de envio (ja existia C-000)
    t = tabela(cfg)
    assert t["C-001"]["rpa_etapa"] == "erro" and "falhou apos 2 tentativas" in t["C-001"]["motivo_rpa"]
    # os membros de um grupo cujo principal falhou nao ficam orfaos: voltam para a fila
    assert (t["C-002"]["rpa_etapa"], t["C-002"]["chamado_principal"]) == ("", "")

    # smtp voltou (aqui: modo mock). Os chamados com erro sao reprocessados, sem duplicar nada
    segunda = run(cfg, HOJE)
    assert segunda["encaminhados"] == 5 and segunda["agrupados"] == 2 and segunda["erros"] == 0
    t = tabela(cfg)
    assert t["C-001"]["status"] == "encaminhado" and t["C-002"]["chamado_principal"] == "C-001"


def test_retry_recupera_apos_falha_transitoria():
    chamadas = {"n": 0}

    def instavel():
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise TimeoutError("lento")
        return "ok"

    assert com_retry(instavel, 3, 0.0, logging.getLogger("t"), "teste") == "ok"
    assert chamadas["n"] == 3


def test_retry_esgotado_levanta_erro():
    def falha():
        raise TimeoutError("lento")

    with pytest.raises(ErroEnvio):
        com_retry(falha, 2, 0.0, logging.getLogger("t"), "teste")
