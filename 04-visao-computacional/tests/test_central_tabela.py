"""Cliente da Azure Table (RepositorioTabela) contra um servidor HTTP falso que imita a Azure:
token da identidade gerenciada, PUT/GET por chave, consulta paginada e DELETE."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from visao.central import Central, RepositorioTabela
from visao.schemas import Chamado, EventoChamado, Evidencia


class AzureFalsa(BaseHTTPRequestHandler):
    linhas: dict = {}
    pedidos: list = []

    def log_message(self, *a):
        pass

    def _resp(self, codigo, corpo=None, cab=None):
        self.send_response(codigo)
        for k, v in (cab or {}).items():
            self.send_header(k, v)
        dados = json.dumps(corpo).encode() if corpo is not None else b""
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _chave(self):
        caminho = unquote(urlsplit(self.path).path)
        return caminho.split("RowKey='")[1].rstrip("')") if "RowKey='" in caminho else None

    def do_GET(self):
        u = urlsplit(self.path)
        if u.path == "/token":
            assert self.headers["X-IDENTITY-HEADER"] == "segredo"
            assert parse_qs(u.query)["client_id"] == ["id-cliente"]
            return self._resp(200, {"access_token": "tok", "expires_on": "9999999999"})
        AzureFalsa.pedidos.append(("GET", self.headers["Authorization"], self.headers["x-ms-version"]))
        chave = self._chave()
        if chave:
            return self._resp(200, AzureFalsa.linhas[chave]) if chave in AzureFalsa.linhas else self._resp(404)
        q = parse_qs(u.query)
        todas = sorted(AzureFalsa.linhas.values(), key=lambda x: x["RowKey"])
        inicio = int(q.get("NextRowKey", ["0"])[0])
        pagina = todas[inicio:inicio + 2]   # páginas de 2 para exercitar a continuação
        cab = {"x-ms-continuation-NextPartitionKey": "vesper", "x-ms-continuation-NextRowKey": str(inicio + 2)} \
            if inicio + 2 < len(todas) else {}
        return self._resp(200, {"value": [{"dados": x["dados"]} for x in pagina]}, cab)

    def do_PUT(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert corpo["PartitionKey"] == "vesper" and corpo["RowKey"] == self._chave()
        AzureFalsa.linhas[self._chave()] = corpo
        self._resp(204)

    def do_DELETE(self):
        assert self.headers["If-Match"] == "*"
        AzureFalsa.linhas.pop(self._chave(), None)
        self._resp(204)


@pytest.fixture
def azure(monkeypatch):
    AzureFalsa.linhas, AzureFalsa.pedidos = {}, []
    srv = HTTPServer(("127.0.0.1", 0), AzureFalsa)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    monkeypatch.setenv("IDENTITY_ENDPOINT", f"{base}/token")
    monkeypatch.setenv("IDENTITY_HEADER", "segredo")
    yield base
    srv.shutdown()


def chamado(n):
    ts = f"2026-11-13T2{n}:00:00-03:00"
    return Chamado(protocolo=f"VSP-00000{n}", id=str(n), ts=ts, origem="cidadao", evidencia=Evidencia.foto,
                   nivel="alta", pontos=80, tipos=["conserto_poste"], trecho="escura", status="recebido",
                   historico=[EventoChamado(status="recebido", ts=ts)])


def test_repositorio_tabela_fala_o_protocolo_da_azure(azure):
    repo = RepositorioTabela(f"{azure}/chamados", client_id="id-cliente")
    for n in range(5):
        repo.salvar(chamado(n))
    assert repo.obter("VSP-000003").id == "3"
    assert repo.obter("VSP-NAOEXISTE") is None
    assert [c.id for c in repo.listar()] == ["4", "3", "2", "1", "0"]   # juntou 3 páginas, mais novo primeiro
    assert all(p[1] == "Bearer tok" and p[2] == "2020-12-06" for p in AzureFalsa.pedidos)
    central = Central(repo)
    assert central.mudar_status("VSP-000001", "confirmado").status == "confirmado"
    assert repo.obter("VSP-000001").historico[-1].status == "confirmado"
    assert repo.limpar() == 5 and repo.listar() == []
