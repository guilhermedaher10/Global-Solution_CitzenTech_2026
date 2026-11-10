"""Contrato de saída da Visão Computacional.

É o formato que RPA, Big Data, GenAI, Maker Lab e o app consomem. Mudou aqui, avise o grupo
e atualize docs/integracao.md. A versão do contrato vai em `versao_contrato`.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

VERSAO_CONTRATO = "1.0"


class Origem(str, Enum):
    cidadao = "cidadao"
    robo = "robo"
    camera = "camera"


class StatusTrecho(str, Enum):
    iluminada = "iluminada"
    parcial = "parcial"
    escura = "escura"
    sem_postes_visiveis = "sem_postes_visiveis"


class NivelPrioridade(str, Enum):
    alta = "alta"
    media = "media"
    baixa = "baixa"
    nenhuma = "nenhuma"


class Localizacao(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    fonte: str = Field(description="'informada' (app/robô) ou 'exif' (GPS da foto)")


class Deteccao(BaseModel):
    classe: str
    confianca: float = Field(ge=0, le=1)
    bbox: list[int] = Field(description="[x1, y1, x2, y2] em pixels da imagem original")
    id_rastreio: int | None = Field(default=None, description="Só no vídeo: mesmo poste entre frames")


class Resumo(BaseModel):
    postes_acesos: int
    postes_apagados: int
    luminosidade_media: float = Field(description="Brilho médio da cena, 0 a 255")
    status_trecho: StatusTrecho


class Validacao(BaseModel):
    foto_valida: bool = Field(description="A imagem serve de evidência?")
    falha_detectada: bool = Field(description="Há sinal de falha na iluminação?")
    abrir_chamado: bool = Field(description="foto_valida E falha_detectada")
    motivos: list[str] = Field(description="Explicação legível de cada decisão")


class Prioridade(BaseModel):
    nivel: NivelPrioridade
    pontuacao: int = Field(ge=0, le=100)
    fatores: list[str] = Field(description="O que somou pontos: decisão explicável e auditável")


class Privacidade(BaseModel):
    rostos_borrados: int
    exif_removido: bool
    imagem_armazenada: bool = Field(default=False, description="A API nunca guarda a imagem")


class ModeloInfo(BaseModel):
    nome: str
    versao: str


class Analise(BaseModel):
    versao_contrato: str = VERSAO_CONTRATO
    id_captura: str
    timestamp: str = Field(description="ISO 8601 com fuso de São Paulo")
    hora_captura: str | None = Field(default=None, description="Data/hora da foto (EXIF), se houver")
    origem: Origem
    localizacao: Localizacao | None
    sensor_lux: float | None
    deteccoes: list[Deteccao]
    resumo: Resumo
    validacao: Validacao
    prioridade: Prioridade
    privacidade: Privacidade
    modelo: ModeloInfo
    imagem_anonimizada_base64: str | None = Field(
        default=None, description="JPEG com rostos borrados; só quando pedido")
