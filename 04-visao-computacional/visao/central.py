"""Central de chamados: onde o relato do cidadão (foto, vídeo, endereço) e o alerta do robô CHEGAM.

Guarda só os dados do chamado (tipo, prioridade, local, status e histórico), nunca a foto nem o vídeo.
Dois "armazéns", escolhidos por variável de ambiente:

    CENTRAL_TABELA_URL   https://<conta>.table.core.windows.net/<tabela>  -> Azure Table Storage, com a
                         identidade gerenciada do Container App (sem chave). É o da nuvem: os chamados
                         sobrevivem quando o container dorme (escala a zero) e valem para todos os aparelhos.
    CENTRAL_DB           caminho de um arquivo SQLite (padrão: pasta temporária). Para rodar no PC e nos testes.

Também decide PARA QUEM vai cada chamado (configs/regras.yaml, seção encaminhamento) e quais mudanças de
status são permitidas (a central não pula etapas).
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Protocol

from .config import regras
from .schemas import (
    Analise, Chamado, Encaminhamento, EventoChamado, Evidencia, RespostaAlerta, StatusChamado,
)

log = logging.getLogger("visao.central")
FUSO_SP = timezone(timedelta(hours=-3))

# status atual -> próximos permitidos (a mesma regra que o front mostra como botões)
TRANSICOES: dict[StatusChamado, set[StatusChamado]] = {
    StatusChamado.suspeita: {StatusChamado.confirmado, StatusChamado.recusado},
    StatusChamado.recebido: {StatusChamado.confirmado, StatusChamado.recusado},
    StatusChamado.confirmado: {StatusChamado.encaminhado, StatusChamado.recusado},
    StatusChamado.encaminhado: {StatusChamado.em_reparo},
    StatusChamado.em_reparo: {StatusChamado.resolvido},
    StatusChamado.resolvido: set(),
    StatusChamado.recusado: set(),
}


class TransicaoInvalida(ValueError):
    pass


def agora() -> str:
    return datetime.now(FUSO_SP).isoformat(timespec="seconds")


def protocolo_de(ident: str) -> str:
    return "VSP-" + ident.replace("-", "")[:6].upper()


def encaminhar(tipos: list[str]) -> list[Encaminhamento]:
    """Tipos de chamado -> órgãos responsáveis, sem repetir órgão."""
    por_tipo = regras().get("encaminhamento", {}).get("por_tipo", {})
    saida: list[Encaminhamento] = []
    for t in tipos:
        for e in por_tipo.get(t, []):
            if all(x.orgao != e["orgao"] for x in saida):
                saida.append(Encaminhamento(orgao=e["orgao"], canal=e["canal"], motivo=e["motivo"]))
    return saida


# ------------------------------------------------------------------------------------------ armazéns
class Repositorio(Protocol):
    def salvar(self, c: Chamado) -> None: ...
    def obter(self, protocolo: str) -> Chamado | None: ...
    def listar(self, limite: int = 500) -> list[Chamado]: ...
    def limpar(self) -> int: ...


class RepositorioSQLite:
    def __init__(self, caminho: str):
        self.caminho = caminho
        self._trava = threading.Lock()
        with self._con() as con:
            con.execute("CREATE TABLE IF NOT EXISTS chamados (protocolo TEXT PRIMARY KEY, ts TEXT, dados TEXT)")

    def _con(self):
        return sqlite3.connect(self.caminho, timeout=10)

    def salvar(self, c: Chamado) -> None:
        with self._trava, self._con() as con:
            con.execute("INSERT OR REPLACE INTO chamados VALUES (?, ?, ?)", (c.protocolo, c.ts, c.model_dump_json()))

    def obter(self, protocolo: str) -> Chamado | None:
        with self._con() as con:
            linha = con.execute("SELECT dados FROM chamados WHERE protocolo = ?", (protocolo,)).fetchone()
        return Chamado.model_validate_json(linha[0]) if linha else None

    def listar(self, limite: int = 500) -> list[Chamado]:
        with self._con() as con:
            linhas = con.execute("SELECT dados FROM chamados ORDER BY ts DESC LIMIT ?", (limite,)).fetchall()
        return [Chamado.model_validate_json(x[0]) for x in linhas]

    def limpar(self) -> int:
        with self._trava, self._con() as con:
            return con.execute("DELETE FROM chamados").rowcount


class RepositorioTabela:
    """Azure Table Storage via REST, autenticado pela identidade gerenciada (sem chave, sem SDK extra)."""

    PARTICAO = "vesper"
    VERSAO_API = "2020-12-06"

    def __init__(self, url_tabela: str, client_id: str | None = None):
        partes = urllib.parse.urlsplit(url_tabela.rstrip("/"))
        self.conta = f"{partes.scheme}://{partes.netloc}"
        self.tabela = partes.path.strip("/")
        self.client_id = client_id
        self._token: tuple[str, float] | None = None
        self._trava = threading.Lock()

    def _bearer(self) -> str:
        with self._trava:
            if self._token and self._token[1] - time.time() > 300:
                return self._token[0]
            endpoint, segredo = os.environ["IDENTITY_ENDPOINT"], os.environ["IDENTITY_HEADER"]
            q = {"resource": "https://storage.azure.com/", "api-version": "2019-08-01"}
            if self.client_id:
                q["client_id"] = self.client_id
            req = urllib.request.Request(f"{endpoint}?{urllib.parse.urlencode(q)}",
                                         headers={"X-IDENTITY-HEADER": segredo})
            with urllib.request.urlopen(req, timeout=10) as r:
                corpo = json.load(r)
            self._token = (corpo["access_token"], float(corpo.get("expires_on", time.time() + 3000)))
            return self._token[0]

    def _pedir(self, metodo: str, caminho: str, corpo: dict | None = None, extra: dict | None = None):
        cab = {"Authorization": f"Bearer {self._bearer()}", "x-ms-version": self.VERSAO_API,
               "x-ms-date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
               "Accept": "application/json;odata=nometadata", **(extra or {})}
        dados = None
        if corpo is not None:
            dados = json.dumps(corpo).encode()
            cab["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.conta}/{caminho}", data=dados, method=metodo, headers=cab)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                texto = r.read()
                return (json.loads(texto) if texto else None), r.headers   # get() sem diferenciar maiúsculas
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, {}
            raise

    def _chave(self, protocolo: str) -> str:
        return f"{self.tabela}(PartitionKey='{self.PARTICAO}',RowKey='{urllib.parse.quote(protocolo)}')"

    def salvar(self, c: Chamado) -> None:   # PUT sem If-Match = insere ou substitui
        self._pedir("PUT", self._chave(c.protocolo),
                    {"PartitionKey": self.PARTICAO, "RowKey": c.protocolo, "ts": c.ts, "dados": c.model_dump_json()})

    def obter(self, protocolo: str) -> Chamado | None:
        corpo, _ = self._pedir("GET", self._chave(protocolo))
        return Chamado.model_validate_json(corpo["dados"]) if corpo else None

    def listar(self, limite: int = 500) -> list[Chamado]:
        itens, cont = [], {}
        while True:
            q = {"$filter": f"PartitionKey eq '{self.PARTICAO}'", "$select": "dados", **cont}
            corpo, cab = self._pedir("GET", f"{self.tabela}()?{urllib.parse.urlencode(q)}")
            itens += [Chamado.model_validate_json(x["dados"]) for x in (corpo or {}).get("value", [])]
            prox_p, prox_r = cab.get("x-ms-continuation-NextPartitionKey"), cab.get("x-ms-continuation-NextRowKey")
            if not prox_p or len(itens) >= 5000:
                break
            cont = {"NextPartitionKey": prox_p, "NextRowKey": prox_r or ""}
        return sorted(itens, key=lambda c: c.ts, reverse=True)[:limite]

    def limpar(self) -> int:
        todos = self.listar(5000)
        for c in todos:
            self._pedir("DELETE", self._chave(c.protocolo), extra={"If-Match": "*"})
        return len(todos)


def criar_repositorio() -> Repositorio:
    url = os.getenv("CENTRAL_TABELA_URL")
    if url:
        log.info("central: Azure Table Storage (%s)", url)
        return RepositorioTabela(url, client_id=os.getenv("AZURE_CLIENT_ID"))
    caminho = os.getenv("CENTRAL_DB") or os.path.join(tempfile.gettempdir(), "vesper-central.db")
    log.info("central: SQLite em %s", caminho)
    return RepositorioSQLite(caminho)


# ------------------------------------------------------------------------------------------ operações
class Central:
    def __init__(self, repo: Repositorio | None = None):
        self.repo = repo or criar_repositorio()

    def registrar_analise(self, a: Analise, evidencia: Evidencia = Evidencia.foto) -> Chamado:
        tipos = [t.value for t in a.fusao.tipos_chamado] or ["trecho_sem_luz"]
        loc = a.localizacao
        nota = "IA validou o vídeo gravado ao vivo" if evidencia == Evidencia.video else "IA validou a foto"
        c = Chamado(
            protocolo=protocolo_de(a.id_captura), id=a.id_captura, ts=a.timestamp,
            origem="robo+foto" if a.origem.value == "robo" else "cidadao", evidencia=evidencia,
            latitude=loc.latitude if loc else None, longitude=loc.longitude if loc else None,
            endereco=loc.endereco if loc else None,
            nivel=a.prioridade.nivel, pontos=a.prioridade.pontuacao, tipos=tipos,
            trecho=a.resumo.status_trecho.value,
            cena_nivel=a.cena.nivel if a.cena else None,
            possivel_apagao=bool(a.cena and a.cena.possivel_apagao),
            fatores=a.prioridade.fatores[:8], motivos=(a.validacao.motivos + a.fusao.motivos)[:8],
            encaminhar_para=encaminhar(tipos), status=StatusChamado.recebido,
            historico=[EventoChamado(status=StatusChamado.recebido, ts=a.timestamp, nota=nota)],
        )
        self.repo.salvar(c)
        return c

    def registrar_suspeita(self, r: RespostaAlerta, *, origem: str, nota: str) -> Chamado:
        tipos = [f"suspeita_{x.value}" for x in r.alertas]
        c = Chamado(
            protocolo=protocolo_de(r.id_alerta), id=r.id_alerta, ts=r.timestamp, origem=origem,
            evidencia=Evidencia.relato if origem == "relato" else Evidencia.sensores,
            latitude=r.localizacao.latitude, longitude=r.localizacao.longitude, endereco=r.localizacao.endereco,
            nivel=r.prioridade_previa.nivel, pontos=r.prioridade_previa.pontuacao, tipos=tipos, trecho="suspeita",
            fatores=r.prioridade_previa.fatores[:8], encaminhar_para=encaminhar(tipos),
            status=StatusChamado.suspeita,
            historico=[EventoChamado(status=StatusChamado.suspeita, ts=r.timestamp, nota=nota)],
        )
        self.repo.salvar(c)
        return c

    def mudar_status(self, protocolo: str, novo: StatusChamado, nota: str | None = None) -> Chamado | None:
        c = self.repo.obter(protocolo)
        if c is None:
            return None
        if novo not in TRANSICOES[c.status]:
            permitidos = ", ".join(sorted(s.value for s in TRANSICOES[c.status])) or "nenhum (chamado encerrado)"
            raise TransicaoInvalida(f"de '{c.status.value}' não dá para ir para '{novo.value}'; permitidos: {permitidos}")
        c.status = novo
        c.historico.append(EventoChamado(status=novo, ts=agora(), nota=nota))
        self.repo.salvar(c)
        return c

    def obter(self, protocolo: str) -> Chamado | None:
        return self.repo.obter(protocolo.strip().upper())

    def listar(self, limite: int = 500) -> list[Chamado]:
        return self.repo.listar(limite)

    def limpar(self) -> int:
        return self.repo.limpar()
