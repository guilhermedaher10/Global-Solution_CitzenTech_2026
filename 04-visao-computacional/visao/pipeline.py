"""Fluxo completo de uma análise: bytes da foto -> JSON do contrato (schemas.Analise).

    metadados (EXIF) -> detecção -> medidas da cena -> status do trecho
    -> validação -> prioridade -> anonimização -> Analise
"""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np

from . import imagem as im
from .config import CLASSE_ACESO, CLASSE_APAGADO
from .detector import Detector
from .privacidade import BorradorRostos, ler_metadados
from .regras import classificar_trecho, priorizar, validar
from .schemas import Analise, Localizacao, ModeloInfo, Origem, Privacidade, Resumo

FUSO_SP = timezone(timedelta(hours=-3))


class ImagemInvalida(ValueError):
    pass


def analisar_imagem(img: np.ndarray, detector: Detector, *, origem: Origem | str = Origem.camera,
                    latitude: float | None = None, longitude: float | None = None,
                    sensor_lux: float | None = None, borrador: BorradorRostos | None = None,
                    retornar_imagem: bool = False, hora_captura: str | None = None,
                    fonte_localizacao: str = "informada", exif_removido: bool = True,
                    deteccoes=None) -> Analise:
    origem = Origem(origem)
    if deteccoes is None:
        deteccoes = detector.detectar(img)

    acesos = sum(d.classe == CLASSE_ACESO for d in deteccoes)
    apagados = sum(d.classe == CLASSE_APAGADO for d in deteccoes)
    lum = im.luminosidade_media(img)
    status = classificar_trecho(acesos, apagados, lum)

    validacao = validar(origem=origem.value, acesos=acesos, apagados=apagados, luminosidade=lum,
                        nitidez=im.nitidez(img), lado_menor=im.lado_menor(img), status=status,
                        sensor_lux=sensor_lux)
    prioridade = priorizar(apagados=apagados, status=status, sensor_lux=sensor_lux,
                           abrir_chamado=validacao.abrir_chamado)

    borrador = borrador or BorradorRostos()
    anonimizada, n_rostos = borrador.borrar(img)
    b64 = base64.b64encode(im.codificar_jpeg(anonimizada)).decode() if retornar_imagem else None

    loc = None
    if latitude is not None and longitude is not None:
        loc = Localizacao(latitude=latitude, longitude=longitude, fonte=fonte_localizacao)

    return Analise(
        id_captura=str(uuid.uuid4()),
        timestamp=datetime.now(FUSO_SP).isoformat(timespec="seconds"),
        hora_captura=hora_captura,
        origem=origem,
        localizacao=loc,
        sensor_lux=sensor_lux,
        deteccoes=deteccoes,
        resumo=Resumo(postes_acesos=acesos, postes_apagados=apagados,
                      luminosidade_media=lum, status_trecho=status),
        validacao=validacao,
        prioridade=prioridade,
        privacidade=Privacidade(rostos_borrados=n_rostos, exif_removido=exif_removido),
        modelo=ModeloInfo(nome=detector.nome, versao=detector.versao),
        imagem_anonimizada_base64=b64,
    )


def analisar_bytes(dados: bytes, detector: Detector, *, origem: Origem | str = Origem.cidadao,
                   latitude: float | None = None, longitude: float | None = None,
                   sensor_lux: float | None = None, borrador: BorradorRostos | None = None,
                   retornar_imagem: bool = False) -> Analise:
    """Entrada da API: lê EXIF (GPS/hora) antes de decodificar; a imagem decodificada já não tem EXIF."""
    img = im.decodificar(dados)
    if img is None:
        raise ImagemInvalida("arquivo não é uma imagem JPEG/PNG/WebP válida")

    meta = ler_metadados(dados)
    fonte = "informada"
    if latitude is None or longitude is None:
        if meta.latitude is not None:
            latitude, longitude, fonte = meta.latitude, meta.longitude, "exif"
        else:
            latitude = longitude = None

    return analisar_imagem(img, detector, origem=origem, latitude=latitude, longitude=longitude,
                           sensor_lux=sensor_lux, borrador=borrador, retornar_imagem=retornar_imagem,
                           hora_captura=meta.hora_captura, fonte_localizacao=fonte)
