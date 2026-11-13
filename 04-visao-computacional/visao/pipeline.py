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
from .config import CLASSE_ACESO, CLASSE_APAGADO, CLASSE_BURACO, regras
from .detector import Detector
from .cena import analisar_cena
from .classificador_cena import classificador_padrao
from .fusao import fundir, ler_sensores
from .privacidade import BorradorRostos, ler_metadados
from .regras import classificar_trecho, priorizar, validar
from .schemas import Analise, Localizacao, ModeloInfo, Origem, Privacidade, Resumo, TipoAlerta

FUSO_SP = timezone(timedelta(hours=-3))


class ImagemInvalida(ValueError):
    pass


def analisar_imagem(img: np.ndarray, detector: Detector, *, origem: Origem | str = Origem.camera,
                    latitude: float | None = None, longitude: float | None = None,
                    sensor_lux: float | None = None, sensor_distancia_cm: float | None = None,
                    alerta: list[TipoAlerta | str] | None = None,
                    borrador: BorradorRostos | None = None,
                    retornar_imagem: bool = False, hora_captura: str | None = None,
                    fonte_localizacao: str = "informada", exif_removido: bool = True,
                    endereco: str | None = None,
                    deteccoes=None, metadados=None) -> Analise:
    origem = Origem(origem)
    if deteccoes is None:
        deteccoes = detector.detectar(img)
    # sanidade: nenhuma luminária ocupa metade da foto; caixa assim é erro do modelo, não evidência
    h, w = img.shape[:2]
    limite = regras()["deteccao"].get("area_maxima", 0.5) * h * w
    deteccoes = [d for d in deteccoes if (d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1]) <= limite]

    acesos = sum(d.classe == CLASSE_ACESO for d in deteccoes)
    apagados = sum(d.classe == CLASSE_APAGADO for d in deteccoes)
    buracos = sum(d.classe == CLASSE_BURACO for d in deteccoes)
    lum = im.luminosidade_media(img)
    status = classificar_trecho(acesos, apagados, lum)
    sinais = ler_sensores(sensor_lux, sensor_distancia_cm, alerta)
    cena = analisar_cena(img)
    ler_classe(img, cena, postes_acesos=acesos)
    ler_exposicao(cena, metadados)
    # sem poste visível, só uma região MUITO escura vale como evidência (ou breu); com fonte de luz
    # forte na cena (ex.: foto de um poste aceso contra o céu) não é "região no escuro"
    cena_escura = cena.nivel.value == "breu" or (cena.nivel.value == "muito_escura" and cena.fontes_de_luz == 0)

    validacao = validar(origem=origem.value, acesos=acesos, apagados=apagados, luminosidade=lum,
                        nitidez=im.nitidez(img), lado_menor=im.lado_menor(img), status=status,
                        sensor_lux=sensor_lux, buracos=buracos, sensor_escuro=sinais.escuro,
                        cena_escura=cena_escura)
    fusao = fundir(sinais, acesos=acesos, apagados=apagados, buracos=buracos, status=status,
                   foto_valida=validacao.foto_valida, luminosidade=lum, cena=cena)
    prioridade = priorizar(apagados=apagados, status=status, sensor_lux=sensor_lux,
                           abrir_chamado=validacao.abrir_chamado, buracos=buracos,
                           sensor_escuro=sinais.escuro, fusao=fusao, cena=cena)

    borrador = borrador or BorradorRostos()
    anonimizada, n_rostos = borrador.borrar(img)
    b64 = base64.b64encode(im.codificar_jpeg(anonimizada)).decode() if retornar_imagem else None

    loc = None
    if latitude is not None and longitude is not None:
        loc = Localizacao(latitude=latitude, longitude=longitude, fonte=fonte_localizacao,
                          endereco=(endereco or None) and endereco.strip()[:200])

    return Analise(
        id_captura=str(uuid.uuid4()),
        timestamp=datetime.now(FUSO_SP).isoformat(timespec="seconds"),
        hora_captura=hora_captura,
        origem=origem,
        localizacao=loc,
        sensor_lux=sensor_lux,
        sensor_distancia_cm=sensor_distancia_cm,
        deteccoes=deteccoes,
        resumo=Resumo(postes_acesos=acesos, postes_apagados=apagados,
                      buracos=buracos, luminosidade_media=lum, status_trecho=status),
        cena=cena,
        validacao=validacao,
        prioridade=prioridade,
        fusao=fusao,
        privacidade=Privacidade(rostos_borrados=n_rostos, exif_removido=exif_removido),
        modelo=ModeloInfo(nome=detector.nome, versao=detector.versao),
        imagem_anonimizada_base64=b64,
    )


def ler_classe(img: np.ndarray, cena, postes_acesos: int = 0) -> None:
    """Classificador de cena + fusão: a leitura final decide o possível apagão (falta de energia).
    Poste aceso na foto = a rede tem energia: nunca é apagão (veto do detector)."""
    leitura = classificador_padrao().ler(img, cena)
    if leitura.classe == "apagao" and postes_acesos > 0:
        leitura.classe, leitura.fonte = "trecho_escuro", "regras+classificador+detector"
        leitura.motivo = f"{postes_acesos} poste(s) aceso(s) na foto: a rede tem energia, então é falha local, não apagão"
    pelas_regras = cena.possivel_apagao
    cena.classe, cena.confianca_classe = leitura.classe, round(leitura.confianca, 3)
    cena.fonte_classe, cena.probabilidades = leitura.fonte, leitura.probabilidades or None
    cena.possivel_apagao = leitura.classe == "apagao"
    if leitura.fonte != "regras" or pelas_regras != cena.possivel_apagao:
        cena.motivos.append(f"leitura da cena: {leitura.classe.replace('_', ' ')} ({leitura.motivo})")
    if cena.possivel_apagao and not pelas_regras:
        cena.motivos.append("possível falta de energia na região (reconhecida pelo classificador de cena)")


def ler_exposicao(cena, meta) -> None:
    """EXIF de exposição: a foto está escura porque a RUA está escura ou porque a CÂMERA fechou rápido?"""
    ev = getattr(meta, "ev100", None) if meta is not None else None
    if ev is None:
        return
    c = regras().get("exposicao", {})
    cena.ev100 = ev
    escura = cena.nivel.value in ("muito_escura", "breu")
    if ev <= c.get("ev_escuro_real", 3):
        cena.motivos.append(f"a câmera precisou de muita exposição (EV {ev}): o lugar está escuro de verdade")
    elif escura and ev >= c.get("ev_subexposta", 8):
        cena.motivos.append(f"foto escura com exposição curta (EV {ev}): pode ser a câmera, não a rua")
        if cena.possivel_apagao:
            cena.possivel_apagao = False
            cena.motivos.append("possível apagão descartado: a câmera estava subexposta")
    if getattr(meta, "flash", None):
        cena.motivos.append("o flash disparou: o brilho do primeiro plano não é a luz da rua")


def analisar_bytes(dados: bytes, detector: Detector, *, origem: Origem | str = Origem.cidadao,
                   latitude: float | None = None, longitude: float | None = None,
                   sensor_lux: float | None = None, sensor_distancia_cm: float | None = None,
                   alerta: list[TipoAlerta | str] | None = None,
                   borrador: BorradorRostos | None = None, retornar_imagem: bool = False,
                   endereco: str | None = None) -> Analise:
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
                           sensor_lux=sensor_lux, sensor_distancia_cm=sensor_distancia_cm, alerta=alerta,
                           borrador=borrador, retornar_imagem=retornar_imagem, endereco=endereco,
                           hora_captura=meta.hora_captura, fonte_localizacao=fonte, metadados=meta)
