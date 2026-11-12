"""Métricas Prometheus da API (GET /metrics), lidas pelo Prometheus/Grafana do 06-devops-cloud.

As 4 métricas de ouro:
    tráfego    http_requisicoes_total{metodo, rota, status}
    erros      o mesmo contador, filtrado por status 4xx/5xx
    latência   http_duracao_segundos{rota}            (histograma: p50/p95/p99)
    saturação  http_requisicoes_em_andamento + CPU/memória do processo (coletor padrão)

E as do produto, que mostram o MVP funcionando:
    visao_analises_total{origem, foto_valida, abriu_chamado}
    visao_chamados_total{tipo, prioridade}         para qual setor da prefeitura e com que urgência
    visao_alertas_robo_total{status, acao}         alertas do robô do Maker Lab
    visao_modelo_carregado                          1/0 (alerta "ModeloNaoCarregado")

A rota vai como o MOLDE (/v1/analisar), nunca a URL crua: evita explosão de séries e não
registra nada do cidadão (LGPD). Nenhuma métrica tem localização, imagem ou identificador.
"""
from __future__ import annotations

import time
from typing import Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUISICOES = Counter("http_requisicoes_total", "Requisições HTTP atendidas", ["metodo", "rota", "status"])
DURACAO = Histogram("http_duracao_segundos", "Tempo de resposta por rota", ["rota"],
                    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 30, 60))
EM_ANDAMENTO = Gauge("http_requisicoes_em_andamento", "Requisições sendo processadas agora")

ANALISES = Counter("visao_analises_total", "Fotos analisadas", ["origem", "foto_valida", "abriu_chamado"])
CHAMADOS = Counter("visao_chamados_total", "Chamados abertos", ["tipo", "prioridade"])
ALERTAS_ROBO = Counter("visao_alertas_robo_total", "Alertas recebidos do robô", ["status", "acao"])
RELATOS = Counter("visao_relatos_total", "Relatos de cidadãos sem foto", ["status"])
MODELO_CARREGADO = Gauge("visao_modelo_carregado", "1 se o modelo YOLO está carregado")

ROTAS_IGNORADAS = {"/metrics"}   # o próprio Prometheus não entra na latência/tráfego do produto


def vigiar_modelo(esta_carregado: Callable[[], bool]) -> None:
    """O gauge é calculado na hora da leitura: sempre reflete o estado real da API."""
    MODELO_CARREGADO.set_function(lambda: 1.0 if esta_carregado() else 0.0)


async def middleware(request, call_next):
    inicio = time.perf_counter()
    EM_ANDAMENTO.inc()
    status = 500
    try:
        resposta = await call_next(request)
        status = resposta.status_code
        return resposta
    finally:
        EM_ANDAMENTO.dec()
        rota_obj = request.scope.get("route")
        rota = getattr(rota_obj, "path", None) or "nao_encontrada"
        if rota not in ROTAS_IGNORADAS:
            REQUISICOES.labels(request.method, rota, str(status)).inc()
            DURACAO.labels(rota).observe(time.perf_counter() - inicio)


def registrar_analise(analise) -> None:
    ANALISES.labels(analise.origem.value, str(analise.validacao.foto_valida).lower(),
                    str(analise.validacao.abrir_chamado).lower()).inc()
    if analise.validacao.abrir_chamado:
        for tipo in analise.fusao.tipos_chamado or ["indefinido"]:
            CHAMADOS.labels(getattr(tipo, "value", tipo), analise.prioridade.nivel.value).inc()


def registrar_alerta(resposta) -> None:
    ALERTAS_ROBO.labels(resposta.status, resposta.acao_robo.value).inc()


def registrar_relato(resposta) -> None:
    RELATOS.labels(resposta.status).inc()


def exportar() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
