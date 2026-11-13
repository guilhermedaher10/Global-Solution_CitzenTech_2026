"""Integração com o GenAI (01-generative-ai): orientação oficial para o cidadão.

Quando a Visão confirma um chamado, pergunta ao assistente do GenAI (RAG local sobre fontes oficiais)
o prazo/canal daquele tipo de serviço e devolve a resposta COM o trecho citado. Se a base não cobre,
o GenAI responde "não consta" e nós repassamos isso, sem inventar.

É opcional e nunca derruba a análise:
- só roda se GENAI_URL estiver definida e o pedido tiver `incluir_orientacao=true`;
- falha/timeout vira `status: indisponivel` com o motivo;
- respostas iguais ficam em cache (o LLM roda com temperatura 0, então a resposta se repete).

Variáveis: GENAI_URL (ex.: http://localhost:8001), GENAI_TIMEOUT (s, padrão 120), GENAI_CIDADE
(padrão "São Paulo"). Perguntas por tipo de chamado em configs/regras.yaml (orientacao.perguntas).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request

from .config import regras
from .schemas import Orientacao, StatusOrientacao, TipoChamado

CACHE_SEGUNDOS = 3600
log = logging.getLogger("visao.orientacao")


class ClienteGenAI:
    def __init__(self, url: str | None = None, timeout: float | None = None, cidade: str | None = None):
        self.url = (url if url is not None else os.getenv("GENAI_URL", "")).rstrip("/") or None
        self.timeout = timeout if timeout is not None else float(os.getenv("GENAI_TIMEOUT", "120"))
        self.cidade = cidade or os.getenv("GENAI_CIDADE", "São Paulo")
        self._cache: dict[str, tuple[float, dict]] = {}

    @property
    def configurado(self) -> bool:
        return self.url is not None

    def _post(self, rota: str, corpo: dict, timeout: float | None = None) -> dict:
        req = urllib.request.Request(f"{self.url}{rota}", data=json.dumps(corpo).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            return json.loads(r.read())

    def saude(self) -> dict:
        """Para o /saude da Visão: o GenAI está no ar? (timeout curto, não trava o health check)"""
        if not self.configurado:
            return {"configurado": False}
        try:
            with urllib.request.urlopen(f"{self.url}/saude", timeout=2) as r:
                return {"configurado": True, "no_ar": r.status == 200, "url": self.url}
        except Exception as e:  # noqa: BLE001 - qualquer falha = fora do ar
            return {"configurado": True, "no_ar": False, "url": self.url, "erro": type(e).__name__}

    def perguntar(self, pergunta: str, timeout: float | None = None) -> dict:
        agora = time.monotonic()
        guardado = self._cache.get(pergunta)
        if guardado and agora - guardado[0] < CACHE_SEGUNDOS:
            return guardado[1]
        resposta = self._post("/consulta", {"pergunta": pergunta}, timeout)
        self._cache[pergunta] = (agora, resposta)
        return resposta

    def aquecer(self) -> threading.Thread | None:
        """Em segundo plano, faz uma vez cada pergunta configurada.

        Medido: a 1ª resposta do GenAI leva ~100 s (o Ollama carrega o modelo na GPU); depois, ~7 s.
        Aquecendo na subida da API, o modelo já está carregado e as respostas ficam no cache
        quando o primeiro cidadão chegar.
        """
        if not self.configurado:
            return None

        def _rodar():
            for modelo in regras().get("orientacao", {}).get("perguntas", {}).values():
                try:
                    self.perguntar(modelo.format(cidade=self.cidade), timeout=max(self.timeout, 300))
                except Exception as e:  # noqa: BLE001 - aquecimento é melhor esforço
                    log.warning("aquecimento do GenAI falhou: %s", e)
                    return

        t = threading.Thread(target=_rodar, name="aquecer-genai", daemon=True)
        t.start()
        return t

    def orientar(self, tipos: list[TipoChamado]) -> list[Orientacao]:
        modelos = regras().get("orientacao", {}).get("perguntas", {})
        saida = []
        for tipo in tipos:
            modelo = modelos.get(tipo.value)
            if not modelo:
                continue
            pergunta = modelo.format(cidade=self.cidade)
            if not self.configurado:
                saida.append(Orientacao(tipo_chamado=tipo, pergunta=pergunta, status=StatusOrientacao.indisponivel,
                                        motivo="GenAI não configurado (defina GENAI_URL)"))
                continue
            try:
                r = self.perguntar(pergunta)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                motivo = "tempo esgotado" if "timed out" in str(e) else f"GenAI fora do ar ({type(e).__name__})"
                saida.append(Orientacao(tipo_chamado=tipo, pergunta=pergunta,
                                        status=StatusOrientacao.indisponivel, motivo=motivo))
                continue
            ok = r.get("status") == "ok"
            saida.append(Orientacao(
                tipo_chamado=tipo, pergunta=pergunta,
                status=StatusOrientacao.ok if ok else StatusOrientacao.nao_consta,
                resposta=r.get("resposta") if ok else None,
                citacao=r.get("citacao") or None,
                trecho_citado=r.get("trecho_citado"),
                aviso=r.get("aviso"),
                motivo=None if ok else (r.get("motivo") or "a base oficial não cobre essa pergunta"),
            ))
        return saida
