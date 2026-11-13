"""Contrato de saída da Visão Computacional.

É o formato que RPA, Big Data, GenAI, Maker Lab e o app consomem. Mudou aqui, avise o grupo
e atualize docs/integracao.md. A versão do contrato vai em `versao_contrato`.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

VERSAO_CONTRATO = "1.5"   # 1.1 robô/fusão · 1.2 GenAI · 1.3 breu/endereço/relato · 1.4 cena · 1.5 central/vídeo/regiões


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
    trecho_sem_luz = "trecho_sem_luz"                 # breu: poste apagado invisível no escuro ou inexistente
    falta_de_energia = "falta_de_energia"             # possível apagão na região: concessionária, não prefeitura


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
    endereco: str | None = Field(default=None, max_length=200, description="Endereço legível, se informado")


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


class StatusOrientacao(str, Enum):
    ok = "ok"                      # o GenAI respondeu citando a fonte oficial
    nao_consta = "nao_consta"      # a base oficial não cobre: não inventamos
    indisponivel = "indisponivel"  # GenAI desligado, fora do ar ou lento demais


class Orientacao(BaseModel):
    """Resposta do assistente do GenAI (01) para o tipo de chamado: prazo/canal com fonte citada."""
    tipo_chamado: TipoChamado
    pergunta: str
    status: StatusOrientacao
    resposta: str | None = None
    citacao: str | None = Field(default=None, description="Id do trecho da base oficial usado")
    trecho_citado: str | None = None
    aviso: str | None = None
    motivo: str | None = Field(default=None, description="Por que não há resposta (nao_consta/indisponivel)")


class NivelLuz(str, Enum):
    iluminada = "iluminada"
    pouca_iluminacao = "pouca_iluminacao"
    muito_escura = "muito_escura"
    breu = "breu"


class Cena(BaseModel):
    """A região está no escuro? Medida na foto inteira, não só nos postes (visao/cena.py)."""
    indice_escuridao: int = Field(ge=0, le=100, description="0 = bem iluminada, 100 = breu")
    nivel: NivelLuz
    luz_no_chao: float = Field(description="Brilho médio do terço de baixo (onde se anda), 0-255")
    area_iluminada: float = Field(ge=0, le=1, description="Fração da imagem com luz útil")
    fontes_de_luz: int = Field(ge=0, description="Pontos de luz visíveis: postes, janelas, faróis, letreiros")
    possivel_apagao: bool = Field(description="Escuro e sem nenhuma fonte de luz: possível falta de energia")
    grade_luz: list[list[int]] = Field(description="Brilho médio em 6x8 blocos (mapa de luz)")
    motivos: list[str]


class Encaminhamento(BaseModel):
    """Quem resolve: poste é da iluminação pública (prefeitura); apagão é da distribuidora de energia."""
    orgao: str
    canal: str
    motivo: str


class Video(BaseModel):
    """Resumo da análise de um vídeo curto: vários quadros analisados, o mais evidente vira a prova."""
    quadros_analisados: int
    duracao_s: float
    quadro_escolhido_s: float = Field(description="Segundo do vídeo usado como evidência")
    apagados_max: int = Field(description="Maior número de postes apagados num mesmo quadro")
    quadros_com_apagado: int
    quadros_com_apagao: int = Field(description="Quadros com sinal de possível apagão na análise de cena")


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
    cena: Cena | None = Field(default=None, description="Análise da região inteira (luz, fontes, apagão)")
    validacao: Validacao
    prioridade: Prioridade
    fusao: Fusao
    privacidade: Privacidade
    modelo: ModeloInfo
    imagem_anonimizada_base64: str | None = Field(
        default=None, description="JPEG com rostos borrados; só quando pedido")
    orientacao: list[Orientacao] | None = Field(
        default=None, description="Prazo/canal oficial via GenAI; só com incluir_orientacao e chamado aberto")
    protocolo: str | None = Field(default=None, description="Protocolo na central (quando o chamado foi aberto)")
    encaminhar_para: list[Encaminhamento] = Field(default_factory=list,
                                                  description="Órgão(s) responsável(is) por resolver")
    video: Video | None = Field(default=None, description="Só em /v1/analisar-video")


class AlertaRobo(BaseModel):
    """O que o robô manda quando um sensor dispara (sem foto)."""
    origem: Origem = Origem.robo
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    sensor_lux: float | None = Field(default=None, ge=0, description="Leitura do LDR")
    sensor_distancia_cm: float | None = Field(default=None, ge=0, description="Leitura do ultrassônico")
    endereco: str | None = Field(default=None, max_length=200)
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
    protocolo: str | None = Field(default=None, description="Protocolo da suspeita na central")
    encaminhar_para: list[Encaminhamento] = Field(default_factory=list)


class RelatoCidadao(BaseModel):
    """Relato SEM foto (só o local): vira suspeita, como o alerta do robô, até uma foto confirmar."""
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    endereco: str | None = Field(default=None, max_length=200)
    problema: list[TipoAlerta] = Field(default_factory=lambda: [TipoAlerta.escuro], min_length=1,
                                       description="O que o cidadão viu: escuro e/ou buraco")

    model_config = {"json_schema_extra": {"examples": [
        {"latitude": -23.5614, "longitude": -46.6559, "endereco": "Av. Paulista, 1578 - Bela Vista, São Paulo",
         "problema": ["escuro"]}]}}


class StatusChamado(str, Enum):
    suspeita = "suspeita"         # relato sem foto ou alerta do robô
    recebido = "recebido"         # a IA validou a evidência
    confirmado = "confirmado"     # o atendente confirmou
    encaminhado = "encaminhado"   # enviado ao órgão responsável (RPA)
    em_reparo = "em_reparo"
    resolvido = "resolvido"
    recusado = "recusado"


class Evidencia(str, Enum):
    foto = "foto"
    video = "video"
    relato = "relato"         # só o local, sem imagem
    sensores = "sensores"     # robô (luz e distância)


class EventoChamado(BaseModel):
    status: StatusChamado
    ts: str
    nota: str | None = None


class Chamado(BaseModel):
    """Um chamado na central (o que a prefeitura/distribuidora vê). Nunca guarda a foto nem o vídeo."""
    versao_contrato: str = VERSAO_CONTRATO
    protocolo: str
    id: str = Field(description="id_captura da análise ou id_alerta da suspeita")
    ts: str
    origem: str = Field(description="cidadao, relato, robo ou robo+foto")
    evidencia: Evidencia
    latitude: float | None = None
    longitude: float | None = None
    endereco: str | None = None
    nivel: NivelPrioridade
    pontos: int = Field(ge=0, le=100)
    tipos: list[str] = Field(description="TipoChamado, ou suspeita_escuro/suspeita_buraco")
    trecho: str
    cena_nivel: NivelLuz | None = None
    possivel_apagao: bool = False
    fatores: list[str] = Field(default_factory=list)
    motivos: list[str] = Field(default_factory=list)
    encaminhar_para: list[Encaminhamento] = Field(default_factory=list)
    status: StatusChamado
    historico: list[EventoChamado]


class MudancaStatus(BaseModel):
    status: StatusChamado
    nota: str | None = Field(default=None, max_length=200)

    model_config = {"json_schema_extra": {"examples": [{"status": "confirmado", "nota": "pelo atendente"}]}}


class TipoRegiao(str, Enum):
    apagao_regiao = "apagao_regiao"                         # vários relatos + sinais de falta de energia
    trecho_escuro_recorrente = "trecho_escuro_recorrente"   # vários relatos de escuro no mesmo lugar


class Regiao(BaseModel):
    """Vários relatos próximos no tempo e no espaço viram UM alerta de região."""
    id: str
    tipo: TipoRegiao
    titulo: str
    bairro: str | None = None
    latitude: float
    longitude: float
    raio_m: int
    relatos: int
    sinais_apagao: int
    protocolos: list[str]
    primeiro: str
    ultimo: str
    encaminhar_para: list[Encaminhamento]
    motivos: list[str]
