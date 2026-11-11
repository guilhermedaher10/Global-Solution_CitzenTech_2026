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
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from visao.fusao import triar_alerta
from visao.pipeline import ImagemInvalida, analisar_bytes
from visao.privacidade import BorradorRostos
from visao.schemas import VERSAO_CONTRATO, AlertaRobo, Analise, Origem, RespostaAlerta, TipoAlerta

log = logging.getLogger("visao.api")
MAX_BYTES = int(float(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024)
TIPOS_ACEITOS = {"image/jpeg", "image/png", "image/webp"}

_estado: dict = {"detector": None, "erro": None, "borrador": None}


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


def obter_detector():
    if _estado["detector"] is None:
        raise HTTPException(503, f"modelo indisponível: {_estado['erro']}")
    return _estado["detector"]


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
    retornar_imagem: bool = Form(False, description="Devolver a imagem anonimizada em base64"),
    detector=Depends(obter_detector),
    borrador: BorradorRostos = Depends(obter_borrador),
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
        return analisar_bytes(dados, detector, origem=origem, latitude=latitude, longitude=longitude,
                              sensor_lux=sensor_lux, sensor_distancia_cm=sensor_distancia_cm,
                              alerta=alertas, borrador=borrador, retornar_imagem=retornar_imagem)
    except ImagemInvalida as e:
        raise HTTPException(422, str(e)) from e


@app.post("/v1/alerta-robo", response_model=RespostaAlerta, tags=["robo"],
          summary="Alerta do robô (só sensores, sem foto): registra a suspeita")
def alerta_robo(alerta: AlertaRobo):
    """Chamado pelo robô do Maker Lab quando o LDR ou o ultrassônico dispara.

    Não precisa do modelo carregado (funciona mesmo com a API degradada). A resposta é curta
    para a placa ler: `acao_robo` diz se acende LED vermelho (prioridade alta) ou amarelo.
    O ponto vira chamado quando uma foto do lugar for enviada a /v1/analisar com os mesmos sensores.
    """
    return triar_alerta(alerta)
