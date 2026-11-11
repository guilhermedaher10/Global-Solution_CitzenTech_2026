"""Contrato de saída da Visão Computacional.

É o formato que RPA, Big Data, GenAI, Maker Lab e o app consomem. Mudou aqui, avise o grupo
e atualize docs/integracao.md. A versão do contrato vai em `versao_contrato`.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

VERSAO_CONTRATO = "1.1"   # 1.1: campos do robô (ultrassônico, alertas) e fusão sensor + foto


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


class TipoAlerta(str, Enum):
    """O que disparou no robô."""
    escuro = "escuro"       # LDR marcou pouca luz
    buraco = "buraco"       # ultrassônico achou desnível


class TipoChamado(str, Enum):
    """Para qual setor da prefeitura o chamado vai."""
    conserto_poste = "conserto_poste"                 # poste existe e está apagado
    instalacao_iluminacao = "instalacao_iluminacao"   # trecho escuro sem poste
    poda_ou_obstrucao = "poda_ou_obstrucao"           # poste aceso, mas a luz não chega ao chão
    buraco = "buraco"                                 # buraco na via


class Confirmacao(str, Enum):
    confirmado = "confirmado"            # a foto confirma tudo o que o sensor apontou
    parcial = "parcial"                  # confirma parte
    nao_confirmado = "nao_confirmado"    # o sensor disparou, mas a foto não mostra
    sem_sensor = "sem_sensor"            # não veio leitura de sensor (ex.: foto de cidadão)


class AcaoRobo(str, Enum):
    led_vermelho = "led_vermelho"   # prioridade alta
    led_amarelo = "led_amarelo"     # suspeita registrada
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
    buracos: int = Field(default=0, description="Só quando o modelo tiver a classe 'buraco'")
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


class Fusao(BaseModel):
    """Cruzamento do que os sensores do robô disseram com o que a foto mostrou."""
    alertas_sensor: list[TipoAlerta] = Field(description="Enviados pelo robô ou deduzidos das leituras")
    tipos_chamado: list[TipoChamado] = Field(description="Setor(es) que devem receber o chamado")
    confirmacao: Confirmacao
    motivos: list[str]


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
    sensor_distancia_cm: float | None = None
    deteccoes: list[Deteccao]
    resumo: Resumo
    validacao: Validacao
    prioridade: Prioridade
    fusao: Fusao
    privacidade: Privacidade
    modelo: ModeloInfo
    imagem_anonimizada_base64: str | None = Field(
        default=None, description="JPEG com rostos borrados; só quando pedido")


class AlertaRobo(BaseModel):
    """O que o robô manda quando um sensor dispara (sem foto)."""
    origem: Origem = Origem.robo
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    sensor_lux: float | None = Field(default=None, ge=0, description="Leitura do LDR")
    sensor_distancia_cm: float | None = Field(default=None, ge=0, description="Leitura do ultrassônico")
    alerta: list[TipoAlerta] = Field(default_factory=list,
                                     description="O que disparou; vazio = a API deduz pelas leituras")

    model_config = {"json_schema_extra": {"examples": [
        {"origem": "robo", "latitude": -23.55, "longitude": -46.63, "sensor_lux": 3.2,
         "sensor_distancia_cm": 12, "alerta": ["escuro", "buraco"]}]}}


class RespostaAlerta(BaseModel):
    """Resposta curta, fácil de ler numa placa (ESP32/Arduino)."""
    versao_contrato: str = VERSAO_CONTRATO
    recebido: bool = True
    id_alerta: str
    timestamp: str
    status: str = Field(description="'suspeita' (vira chamado quando uma foto confirmar) ou 'descartado'")
    alertas: list[TipoAlerta]
    localizacao: Localizacao
    prioridade_previa: Prioridade
    proximo_passo: str
    acao_robo: AcaoRobo
