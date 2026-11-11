"""Integração com o GenAI (01). Um servidor HTTP falso imita a API do colega (POST /consulta, GET /saude)
no mesmo formato de resposta, então o teste exercita a rede de verdade sem precisar de Ollama/LLM."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from conftest import DetectorFalso, cena, jpeg, poste
from visao.orientacao import ClienteGenAI
from visao.schemas import StatusOrientacao, TipoChamado

PERGUNTAS_RECEBIDAS: list[str] = []


class GenAIFalso(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencia o log do servidor
        pass

    def _json(self, codigo, corpo):
        dados = json.dumps(corpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        self._json(200, {"ok": True, "trechos": 31})

    def do_POST(self):
        pergunta = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["pergunta"]
        PERGUNTAS_RECEBIDAS.append(pergunta)
        aviso = "Pré-orientação automática. Confirme com o canal oficial da prefeitura (humano no circuito)."
        if "iluminação" in pergunta and "prazo" in pergunta:
            self._json(200, {"status": "ok", "resposta": "Normalmente em até 24 horas.", "citacao": "SP-prazo",
                             "trecho_citado": "São Paulo (capital): normalmente a manutenção da iluminação "
                                              "pública é concluída em até 24 horas.", "aviso": aviso})
        else:
            self._json(200, {"status": "nao_consta", "resposta": "Não consta na base.", "citacao": "",
                             "trecho_citado": None, "motivo": "abaixo do limiar", "aviso": aviso})


@pytest.fixture(scope="module")
def genai_url():
    srv = HTTPServer(("127.0.0.1", 0), GenAIFalso)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_resposta_com_fonte_e_nao_consta_sem_inventar(genai_url):
    o = ClienteGenAI(genai_url).orientar([TipoChamado.conserto_poste, TipoChamado.buraco])
    assert o[0].status == StatusOrientacao.ok
    assert o[0].citacao == "SP-prazo" and "24 horas" in o[0].trecho_citado
    assert o[0].aviso and "humano" in o[0].aviso
    assert o[1].status == StatusOrientacao.nao_consta and o[1].resposta is None   # não repassa "não consta" como resposta


def test_cache_nao_repete_a_pergunta(genai_url):
    cli = ClienteGenAI(genai_url, cidade="Cidade Teste")
    antes = len(PERGUNTAS_RECEBIDAS)
    cli.orientar([TipoChamado.conserto_poste])
    cli.orientar([TipoChamado.conserto_poste])
    assert len(PERGUNTAS_RECEBIDAS) - antes == 1
    assert "Cidade Teste" in PERGUNTAS_RECEBIDAS[-1]


def test_genai_fora_do_ar_ou_desligado_nao_derruba():
    fora = ClienteGenAI("http://127.0.0.1:9", timeout=2).orientar([TipoChamado.conserto_poste])
    assert fora[0].status == StatusOrientacao.indisponivel
    assert "fora do ar" in fora[0].motivo or "tempo esgotado" in fora[0].motivo   # Windows: porta fechada = timeout
    sem = ClienteGenAI("").orientar([TipoChamado.conserto_poste])
    assert sem[0].status == StatusOrientacao.indisponivel and "GENAI_URL" in sem[0].motivo
    assert ClienteGenAI("").saude() == {"configurado": False}


def _cliente_api(genai):
    from api import main
    from test_pipeline_api import _sem_lifespan

    main._estado.update(detector=DetectorFalso([poste("poste_apagado")]), erro=None, genai=genai)
    main.app.router.lifespan_context = _sem_lifespan
    return TestClient(main.app)


def test_api_inclui_orientacao_so_quando_pedido(genai_url):
    arq = {"imagem": ("rua.jpg", jpeg(cena(30)), "image/jpeg")}
    with _cliente_api(ClienteGenAI(genai_url)) as c:
        sem = c.post("/v1/analisar", files=arq).json()
        assert sem["orientacao"] is None
        com = c.post("/v1/analisar", files=arq, data={"incluir_orientacao": "true"}).json()
        assert com["orientacao"][0]["tipo_chamado"] == "conserto_poste"
        assert com["orientacao"][0]["status"] == "ok"
        saude = c.get("/saude").json()
        assert saude["genai"]["no_ar"] is True and saude["status"] == "ok"


def test_api_continua_ok_com_genai_fora_do_ar():
    arq = {"imagem": ("rua.jpg", jpeg(cena(30)), "image/jpeg")}
    with _cliente_api(ClienteGenAI("http://127.0.0.1:9", timeout=2)) as c:
        r = c.post("/v1/analisar", files=arq, data={"incluir_orientacao": "true"})
        assert r.status_code == 200
        assert r.json()["orientacao"][0]["status"] == "indisponivel"
        saude = c.get("/saude").json()
        assert saude["status"] == "ok" and saude["genai"]["no_ar"] is False
