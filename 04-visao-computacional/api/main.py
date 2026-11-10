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

from visao.pipeline import ImagemInvalida, analisar_bytes
from visao.privacidade import BorradorRostos
from visao.schemas import VERSAO_CONTRATO, Analise, Origem

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
        return analisar_bytes(dados, detector, origem=origem, latitude=latitude, longitude=longitude,
                              sensor_lux=sensor_lux, borrador=borrador, retornar_imagem=retornar_imagem)
    except ImagemInvalida as e:
        raise HTTPException(422, str(e)) from e
