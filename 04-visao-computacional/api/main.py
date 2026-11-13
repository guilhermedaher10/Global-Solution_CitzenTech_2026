"""API da Visão Computacional. É por aqui que o app do cidadão, o robô e o RPA usam o modelo.

Rodar (a partir de 04-visao-computacional/):
    uvicorn api.main:app --port 8000
Documentação interativa: http://localhost:8000/docs

Variáveis de ambiente (todas opcionais):
    MODELO_PATH      caminho do .pt/.onnx (padrão: models/best.pt)
    MODELO_NOME      nome exibido no JSON (padrão: nome do arquivo)
    MODELO_VERSAO    versão exibida no JSON (padrão: dev)
    CORS_ORIGENS     origens liberadas, separadas por vírgula (padrão: *)
    MAX_UPLOAD_MB    tamanho máximo da foto (padrão: 10)
    GENAI_URL        API do GenAI (01-generative-ai), ex.: http://localhost:8001 (sem ela, sem orientação)
    GENAI_TIMEOUT    segundos de espera pelo GenAI (padrão: 120)
    GENAI_CIDADE     cidade usada nas perguntas ao GenAI (padrão: São Paulo)
    METRICS_TOKEN    se definido, GET /metrics exige 'Authorization: Bearer <token>' (use na nuvem)
    CENTRAL_TABELA_URL  Azure Table da central de chamados (na nuvem, com identidade gerenciada)
    CENTRAL_DB       arquivo SQLite da central (padrão: pasta temporária), quando não há tabela
    CENTRAL_TOKEN    se definido, libera POST /v1/central/limpar com 'Authorization: Bearer <token>'
"""
from __future__ import annotations

import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from visao import metricas
from visao.central import Central, TransicaoInvalida
from visao.fusao import triar_alerta
from visao.orientacao import ClienteGenAI
from visao.pipeline import ImagemInvalida, analisar_bytes
from visao.privacidade import BorradorRostos
from visao.regioes import agrupar
from visao.schemas import (
    VERSAO_CONTRATO, AlertaRobo, Analise, Chamado, Evidencia, MudancaStatus, Origem, Regiao, RelatoCidadao,
    RespostaAlerta, TipoAlerta,
)
from visao.video import SUFIXOS, analisar_video_bytes
from visao.config import regras

log = logging.getLogger("visao.api")
MAX_BYTES = int(float(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024)
TIPOS_ACEITOS = {"image/jpeg", "image/png", "image/webp"}

_estado: dict = {"detector": None, "erro": None, "borrador": None, "genai": None, "central": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    from visao.detector import YoloDetector

    try:
        _estado["detector"] = YoloDetector()
        log.info("modelo carregado: %s", _estado["detector"].caminho)
    except Exception as e:  # a API sobe mesmo sem modelo, para o /saude dizer o que falta
        _estado["erro"] = str(e)
        log.error("modelo não carregado: %s", e)
    _estado["borrador"] = BorradorRostos()
    _estado["genai"] = ClienteGenAI()
    _estado["genai"].aquecer()   # carrega o LLM do GenAI e enche o cache em segundo plano
    yield


app = FastAPI(
    title="Ruas Escuras · Visão Computacional",
    description="Detecta postes acesos e apagados, classifica o trecho, valida a foto do cidadão "
                "e devolve o chamado com prioridade explicável. Não armazena imagens.",
    version=VERSAO_CONTRATO,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGENS", "*").split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _openapi_formulario_simples() -> dict:
    """Na página /docs, o Swagger preenche sozinho os campos opcionais do formulário ("string", 0 ou o
    mínimo permitido) e manda junto. Aqui, só nos esquemas de ENTRADA de formulário (Body_*), o
    "número OU nulo" vira "número" com exemplo vazio; o contrato de resposta continua dizendo "pode ser nulo".
    """
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(title=app.title, version=app.version, description=app.description,
                         routes=app.routes)
    for nome, corpo in schema.get("components", {}).get("schemas", {}).items():
        if not nome.startswith("Body_"):
            continue
        for campo in corpo.get("properties", {}).values():
            opcoes = campo.get("anyOf")
            if isinstance(opcoes, list) and {"type": "null"} in opcoes:
                tipos = [o for o in opcoes if o != {"type": "null"}]
                if len(tipos) == 1:
                    del campo["anyOf"]
                    campo.update(tipos[0])
                    # sem exemplo, o Swagger inventa um (0 = mínimo, "string"); vazio = não envia
                    campo["example"] = ""
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_formulario_simples
app.middleware("http")(metricas.middleware)

# ---------------------------------------------------------------- front do cidadão (web/)
WEB = Path(__file__).resolve().parent.parent / "web"
# CSP só na página e nos estáticos (o /docs usa o CDN do Swagger e ficaria quebrado).
# Script e fontes só da própria origem; imagens também do mapa e busca de endereço do OpenStreetMap
# (Nominatim); nada de iframe de terceiros.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: blob: https://tile.openstreetmap.org; font-src 'self'; "
       "connect-src 'self' https://nominatim.openstreetmap.org; media-src 'self' blob:; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


@app.middleware("http")
async def cabecalhos_de_seguranca(request, call_next):
    resposta = await call_next(request)
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        resposta.headers["Content-Security-Policy"] = CSP
        resposta.headers["Permissions-Policy"] = "geolocation=(self), camera=(self), microphone=()"
    return resposta


if WEB.is_dir():
    app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/", include_in_schema=False)
def pagina_inicial():
    """Front do MVP: cidadão (foto), robô (sensores) e prefeitura (mapa e fila)."""
    if not (WEB / "index.html").exists():
        raise HTTPException(404, "front não incluído nesta imagem")
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})

metricas.vigiar_modelo(lambda: _estado["detector"] is not None)


def obter_detector():
    if _estado["detector"] is None:
        raise HTTPException(503, f"modelo indisponível: {_estado['erro']}")
    return _estado["detector"]


def obter_genai() -> ClienteGenAI:
    if _estado["genai"] is None:
        _estado["genai"] = ClienteGenAI()
    return _estado["genai"]


def obter_central() -> Central:
    if _estado["central"] is None:
        _estado["central"] = Central()
    return _estado["central"]


def _registrar_analise(central: Central, analise: Analise, evidencia: Evidencia) -> None:
    """Chamado aberto -> grava na central e devolve o protocolo. Se a central falhar, a análise segue."""
    from visao.central import encaminhar

    if not analise.validacao.abrir_chamado:
        return
    analise.encaminhar_para = encaminhar([t.value for t in analise.fusao.tipos_chamado])
    try:
        analise.protocolo = central.registrar_analise(analise, evidencia).protocolo
    except Exception:
        log.exception("central indisponível: chamado %s não registrado", analise.id_captura)
        metricas.registrar_falha_central()


def _registrar_suspeita(central: Central, resposta: RespostaAlerta, origem: str, nota: str) -> None:
    from visao.central import encaminhar

    if resposta.status != "suspeita":
        return
    resposta.encaminhar_para = encaminhar([f"suspeita_{a.value}" for a in resposta.alertas])
    try:
        resposta.protocolo = central.registrar_suspeita(resposta, origem=origem, nota=nota).protocolo
    except Exception:
        log.exception("central indisponível: suspeita %s não registrada", resposta.id_alerta)
        metricas.registrar_falha_central()


def obter_borrador() -> BorradorRostos:
    if _estado["borrador"] is None:
        _estado["borrador"] = BorradorRostos()
    return _estado["borrador"]


@app.get("/saude", tags=["infra"])
def saude():
    det = _estado["detector"]
    return {
        "status": "ok" if det else "degradado",
        "modelo_carregado": det is not None,
        "modelo": {"nome": det.nome, "versao": det.versao} if det else None,
        "erro": _estado["erro"],
        "genai": obter_genai().saude(),       # dependência opcional: não deixa a Visão "degradada"
        "versao_contrato": VERSAO_CONTRATO,
    }


@app.post("/v1/analisar", response_model=Analise, tags=["analise"],
          summary="Analisa uma foto de rua e diz se deve abrir chamado")
async def analisar(
    imagem: UploadFile = File(..., description="Foto JPEG, PNG ou WebP"),
    origem: Origem = Form(Origem.cidadao),
    latitude: float | None = Form(None, ge=-90, le=90),
    longitude: float | None = Form(None, ge=-180, le=180),
    sensor_lux: float | None = Form(None, ge=0, description="Leitura do sensor de luz do robô"),
    sensor_distancia_cm: float | None = Form(None, ge=0, description="Leitura do ultrassônico do robô"),
    alerta: str | None = Form(None, description="O que disparou no robô, separado por vírgula: escuro,buraco"),
    endereco: str | None = Form(None, max_length=200, description="Endereço legível do local (opcional)"),
    retornar_imagem: bool = Form(False, description="Devolver a imagem anonimizada em base64"),
    incluir_orientacao: bool = Form(False, description="Perguntar ao GenAI o prazo/canal oficial "
                                    "(só se abrir chamado; pode levar alguns segundos)"),
    registrar: bool = Form(True, description="Abrir o chamado na central quando a foto confirmar a falha"),
    detector=Depends(obter_detector),
    borrador: BorradorRostos = Depends(obter_borrador),
    genai: ClienteGenAI = Depends(obter_genai),
    central: Central = Depends(obter_central),
):
    if imagem.content_type not in TIPOS_ACEITOS:
        raise HTTPException(415, f"tipo {imagem.content_type} não aceito; use JPEG, PNG ou WebP")
    dados = await imagem.read(MAX_BYTES + 1)
    if len(dados) > MAX_BYTES:
        raise HTTPException(413, f"imagem maior que {MAX_BYTES // (1024 * 1024)} MB")
    try:
        alertas = [TipoAlerta(a.strip()) for a in (alerta or "").split(",") if a.strip()]
    except ValueError as e:
        raise HTTPException(422, f"alerta inválido: {alerta!r}; use escuro e/ou buraco") from e
    try:
        analise = analisar_bytes(dados, detector, origem=origem, latitude=latitude, longitude=longitude,
                                 sensor_lux=sensor_lux, sensor_distancia_cm=sensor_distancia_cm,
                                 alerta=alertas, borrador=borrador, retornar_imagem=retornar_imagem,
                                 endereco=endereco)
    except ImagemInvalida as e:
        raise HTTPException(422, str(e)) from e
    if incluir_orientacao and analise.validacao.abrir_chamado:
        # o LLM do GenAI roda em CPU e pode demorar: fora do loop de eventos
        analise.orientacao = await run_in_threadpool(genai.orientar, analise.fusao.tipos_chamado)
    if registrar:
        await run_in_threadpool(_registrar_analise, central, analise, Evidencia.foto)
    metricas.registrar_analise(analise)
    return analise


@app.post("/v1/analisar-video", response_model=Analise, tags=["analise"],
          summary="Analisa um vídeo curto gravado ao vivo e abre o chamado")
async def analisar_video(
    video: UploadFile = File(..., description="Vídeo WebM ou MP4 (até ~20 s); só os primeiros segundos contam"),
    latitude: float | None = Form(None, ge=-90, le=90),
    longitude: float | None = Form(None, ge=-180, le=180),
    endereco: str | None = Form(None, max_length=200, description="Endereço legível do local (opcional)"),
    retornar_imagem: bool = Form(False, description="Devolver o quadro escolhido, anonimizado, em base64"),
    incluir_orientacao: bool = Form(False, description="Perguntar ao GenAI o prazo/canal oficial"),
    registrar: bool = Form(True, description="Abrir o chamado na central quando o vídeo confirmar a falha"),
    detector=Depends(obter_detector),
    borrador: BorradorRostos = Depends(obter_borrador),
    genai: ClienteGenAI = Depends(obter_genai),
    central: Central = Depends(obter_central),
):
    """Para o cidadão que está no escuro AGORA: grava alguns segundos pela câmera do navegador e envia.

    Um quadro a cada meio segundo passa pelo detector; o mais evidente (mais postes apagados, sinal de
    apagão, mais nítido) vira a prova e segue o mesmo fluxo da foto. O vídeo é apagado logo após a análise.
    """
    tipo = (video.content_type or "").split(";")[0].strip()
    if tipo not in SUFIXOS:
        raise HTTPException(415, f"tipo {video.content_type} não aceito; use WebM ou MP4")
    limite = int(regras()["video"]["max_mb"] * 1024 * 1024)
    dados = await video.read(limite + 1)
    if len(dados) > limite:
        raise HTTPException(413, f"vídeo maior que {limite // (1024 * 1024)} MB; grave menos segundos")
    try:
        analise = await run_in_threadpool(
            analisar_video_bytes, dados, tipo, detector, origem=Origem.cidadao, latitude=latitude,
            longitude=longitude, endereco=endereco, borrador=borrador, retornar_imagem=retornar_imagem)
    except ImagemInvalida as e:
        raise HTTPException(422, str(e)) from e
    if incluir_orientacao and analise.validacao.abrir_chamado:
        analise.orientacao = await run_in_threadpool(genai.orientar, analise.fusao.tipos_chamado)
    if registrar:
        await run_in_threadpool(_registrar_analise, central, analise, Evidencia.video)
    metricas.registrar_analise(analise)
    metricas.registrar_video(analise)
    return analise


@app.post("/v1/alerta-robo", response_model=RespostaAlerta, tags=["robo"],
          summary="Alerta do robô (só sensores, sem foto): registra a suspeita")
def alerta_robo(alerta: AlertaRobo, central: Central = Depends(obter_central)):
    """Chamado pelo robô do Maker Lab quando o LDR ou o ultrassônico dispara.

    Não precisa do modelo carregado (funciona mesmo com a API degradada). A resposta é curta
    para a placa ler: `acao_robo` diz se acende LED vermelho (prioridade alta) ou amarelo.
    O ponto vira chamado quando uma foto do lugar for enviada a /v1/analisar com os mesmos sensores.
    """
    resposta = triar_alerta(alerta)
    _registrar_suspeita(central, resposta, "robo",
                        f"robô: {alerta.sensor_lux} lux, {alerta.sensor_distancia_cm} cm")
    metricas.registrar_alerta(resposta)
    return resposta


@app.post("/v1/relatos", response_model=RespostaAlerta, tags=["cidadao"],
          summary="Relato do cidadão SEM foto (só o local): registra a suspeita")
def relato_cidadao(relato: RelatoCidadao, central: Central = Depends(obter_central)):
    """Para quem não consegue fotografar (breu total, celular sem câmera, acessibilidade).

    Vira uma suspeita com prioridade prévia, como o alerta do robô; uma foto do mesmo local enviada a
    /v1/analisar confirma. Funciona mesmo sem o modelo carregado.
    """
    resposta = triar_alerta(AlertaRobo(origem=Origem.cidadao, latitude=relato.latitude, longitude=relato.longitude,
                                       endereco=relato.endereco, alerta=relato.problema))
    _registrar_suspeita(central, resposta, "relato", "relato do cidadão, aguardando foto")
    metricas.registrar_relato(resposta)
    return resposta


# ---------------------------------------------------------------- central de chamados
@app.get("/v1/chamados", response_model=list[Chamado], tags=["central"],
         summary="Fila da central: chamados mais recentes primeiro")
def listar_chamados(limite: int = 300, central: Central = Depends(obter_central)):
    """O que a prefeitura e a distribuidora veem. Só dados do chamado: nunca foto, vídeo ou dado pessoal."""
    return central.listar(max(1, min(limite, 1000)))


@app.get("/v1/chamados/{protocolo}", response_model=Chamado, tags=["central"],
         summary="Acompanhar um chamado pelo protocolo")
def obter_chamado(protocolo: str, central: Central = Depends(obter_central)):
    c = central.obter(protocolo[:20])
    if c is None:
        raise HTTPException(404, "protocolo não encontrado")
    return c


@app.post("/v1/chamados/{protocolo}/status", response_model=Chamado, tags=["central"],
          summary="Atendente muda o status (confirmar, encaminhar, em reparo, resolvido, recusar)")
def mudar_status(protocolo: str, mudanca: MudancaStatus, central: Central = Depends(obter_central)):
    """Só transições válidas (não dá para pular de 'recebido' para 'resolvido'). Na demonstração, sem login."""
    try:
        c = central.mudar_status(protocolo[:20].strip().upper(), mudanca.status, mudanca.nota)
    except TransicaoInvalida as e:
        raise HTTPException(409, str(e)) from e
    if c is None:
        raise HTTPException(404, "protocolo não encontrado")
    metricas.registrar_status(mudanca.status.value)
    return c


@app.get("/v1/regioes", response_model=list[Regiao], tags=["central"],
         summary="Relatos agrupados: 'possível apagão na região X'")
def regioes(central: Central = Depends(obter_central)):
    """Muitos chamados próximos e recentes viram um alerta de região (regra em configs/regras.yaml)."""
    return agrupar(central.listar(1000))


@app.post("/v1/central/limpar", tags=["central"], include_in_schema=False)
def limpar_central(authorization: str | None = Header(None), central: Central = Depends(obter_central)):
    """Zera a demonstração. Só com CENTRAL_TOKEN definido e enviado."""
    token = os.getenv("CENTRAL_TOKEN")
    if not token or not hmac.compare_digest(authorization or "", f"Bearer {token}"):
        raise HTTPException(403, "limpeza desativada ou token inválido")
    return {"removidos": central.limpar()}


@app.get("/metrics", include_in_schema=False)
def metrics(authorization: str | None = Header(None)):
    """Métricas para o Prometheus. Na nuvem, protegido por token (METRICS_TOKEN)."""
    token = os.getenv("METRICS_TOKEN")
    if token and not hmac.compare_digest(authorization or "", f"Bearer {token}"):
        raise HTTPException(401, "token do /metrics ausente ou inválido")
    corpo, tipo = metricas.exportar()
    return Response(corpo, media_type=tipo)
