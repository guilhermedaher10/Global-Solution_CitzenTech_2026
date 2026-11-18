"""RPA_FONTE=api: o robô lê a central do Vésper e devolve o andamento pela API (sem CSV de chamados)."""
import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src import repositorio
from src.main import run

HOJE = date(2026, 11, 18)

CENTRAL = [
    {"protocolo": "VSP-AAA111", "ts": "2026-11-17T20:00:00-03:00", "origem": "cidadao", "evidencia": "foto",
     "latitude": -23.5600, "longitude": -46.6500, "nivel": "alta", "pontos": 80, "tipos": ["conserto_poste"],
     "trecho": "escura", "fatores": ["+40: poste apagado"], "motivos": ["foto válida"], "status": "confirmado"},
    {"protocolo": "VSP-BBB222", "ts": "2026-11-17T21:00:00-03:00", "origem": "robo", "evidencia": "sensores",
     "latitude": -23.5700, "longitude": -46.6400, "nivel": "media", "pontos": 30, "tipos": ["suspeita_escuro"],
     "trecho": "suspeita", "fatores": ["TinyML do carrinho: escuro_livre (100%)"], "motivos": [],
     "status": "confirmado"},
    {"protocolo": "VSP-CCC333", "ts": "2026-11-17T22:00:00-03:00", "origem": "robo", "evidencia": "sensores",
     "latitude": -23.5800, "longitude": -46.6300, "nivel": "alta", "pontos": 60, "tipos": ["suspeita_escuro"],
     "trecho": "suspeita", "fatores": [], "motivos": [], "status": "suspeita"},   # ainda não confirmado: fica
]


@pytest.fixture
def central(monkeypatch):
    estado = {"chamados": json.loads(json.dumps(CENTRAL)), "posts": []}

    class Central(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, corpo, codigo=200):
            dados = json.dumps(corpo).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def do_GET(self):
            self._json(estado["chamados"] if self.path.startswith("/v1/chamados") else {"detail": "?"},
                       200 if self.path.startswith("/v1/chamados") else 404)

        def do_POST(self):
            protocolo = self.path.split("/")[3]
            corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            estado["posts"].append((protocolo, corpo))
            c = next(c for c in estado["chamados"] if c["protocolo"] == protocolo)
            c["status"] = corpo["status"]
            self._json(c)

    srv = HTTPServer(("127.0.0.1", 0), Central)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("RPA_FONTE", "api")
    monkeypatch.setenv("VESPER_API_URL", f"http://127.0.0.1:{srv.server_port}")
    yield estado
    srv.shutdown()


def test_le_a_central_e_devolve_o_encaminhamento(cfg, central):
    csv_antes = cfg.csv_path.read_bytes()
    resumo = run(cfg, HOJE)

    assert resumo["encaminhados"] == 2 and resumo["falhas_dados"] == 0 and resumo["erros"] == 0
    # a central recebeu "encaminhado" dos dois confirmados, com o protocolo da prefeitura na nota
    enviados = {p: c for p, c in central["posts"]}
    assert set(enviados) == {"VSP-AAA111", "VSP-BBB222"}
    assert all(c["status"] == "encaminhado" and "protocolo CH-" in c["nota"] for c in enviados.values())
    # a suspeita não confirmada não foi tocada
    assert next(c for c in central["chamados"] if c["protocolo"] == "VSP-CCC333")["status"] == "suspeita"
    # PDF gerado sem foto (a central não guarda imagens) e estado interno salvo à parte
    assert (cfg.outbox_dir / "chamados" / "chamado_VSP-AAA111.pdf").exists()
    estado = (cfg.csv_path.parent / "estado_rpa_api.csv").read_text(encoding="utf-8")
    assert "VSP-AAA111" in estado and "VSP-BBB222" in estado
    # o CSV de exemplo (modo offline) continua intacto
    assert cfg.csv_path.read_bytes() == csv_antes

    # segunda execução: nada novo para encaminhar, nenhum POST repetido
    n_posts = len(central["posts"])
    assert run(cfg, HOJE)["encaminhados"] == 0
    assert len(central["posts"]) == n_posts


def test_mapeia_o_chamado_da_central():
    r = repositorio.de_central(CENTRAL[1])
    assert r["id_captura"] == "VSP-BBB222" and r["tipos_chamado"] == "suspeita_escuro"
    assert r["prioridade_nivel"] == "media" and r["prioridade_pontuacao"] == "30"
    assert r["fonte"] == "api" and r["foto"] == ""
