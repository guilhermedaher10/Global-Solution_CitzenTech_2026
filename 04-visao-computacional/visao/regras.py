"""Regras de negócio: transformam detecções + medidas da imagem em decisão.

Tudo aqui é determinístico e explicável (cada decisão vem com o motivo). O modelo enxerga;
quem decide se abre chamado e com que prioridade são estas regras, configuráveis em
configs/regras.yaml. Isso facilita auditoria pela prefeitura e ajuste sem retreinar.
"""
from __future__ import annotations

from .config import regras
from .schemas import NivelPrioridade, Prioridade, StatusTrecho, Validacao


def classificar_trecho(acesos: int, apagados: int, luminosidade: float) -> StatusTrecho:
    escuro = luminosidade < regras()["luminosidade"]["limiar_escuro"]
    total = acesos + apagados
    if total == 0:
        return StatusTrecho.escura if escuro else StatusTrecho.sem_postes_visiveis
    if apagados / total >= 0.5 or (escuro and apagados > 0):
        return StatusTrecho.escura
    if apagados > 0:
        return StatusTrecho.parcial
    return StatusTrecho.iluminada


def validar(*, origem: str, acesos: int, apagados: int, luminosidade: float, nitidez: float,
            lado_menor: int, status: StatusTrecho, sensor_lux: float | None = None) -> Validacao:
    r = regras()
    motivos: list[str] = []
    foto_valida = True

    if lado_menor < r["validacao"]["lado_minimo_px"]:
        foto_valida = False
        motivos.append(f"imagem pequena demais ({lado_menor}px; mínimo {r['validacao']['lado_minimo_px']}px)")
    if nitidez < r["validacao"]["nitidez_minima"]:
        foto_valida = False
        motivos.append("imagem muito tremida ou desfocada")
    if luminosidade > r["luminosidade"]["limiar_dia"]:
        foto_valida = False
        motivos.append("a foto parece ter sido tirada de dia; poste apagado de dia não é falha")
    # Foto do cidadão precisa mostrar pelo menos um poste; robô/câmera fixa têm sensor e posição
    # conhecida, então uma cena escura sem poste visível também vale como evidência.
    if origem == "cidadao" and acesos + apagados == 0:
        foto_valida = False
        motivos.append("nenhum poste identificado na foto; enquadre o poste")

    lux_baixo = sensor_lux is not None and sensor_lux < r["prioridade"]["limiar_sensor_lux"]
    falha = apagados > 0 or status == StatusTrecho.escura or lux_baixo
    if apagados > 0:
        motivos.append(f"{apagados} poste(s) apagado(s) detectado(s)")
    if status == StatusTrecho.escura:
        motivos.append("trecho classificado como escuro")
    if lux_baixo:
        motivos.append(f"sensor de luz do robô marcou {sensor_lux} lux")
    if not falha:
        motivos.append("nenhum sinal de falha na iluminação")

    return Validacao(foto_valida=foto_valida, falha_detectada=falha,
                     abrir_chamado=foto_valida and falha, motivos=motivos)


def priorizar(*, apagados: int, status: StatusTrecho, sensor_lux: float | None,
              abrir_chamado: bool) -> Prioridade:
    if not abrir_chamado:
        return Prioridade(nivel=NivelPrioridade.nenhuma, pontuacao=0, fatores=["sem chamado a abrir"])

    p = regras()["prioridade"]
    pontos, fatores = 0, []

    pts = min(apagados * p["pontos_por_poste_apagado"], p["max_pontos_postes"])
    if pts:
        pontos += pts
        fatores.append(f"+{pts}: {apagados} poste(s) apagado(s)")
    if status == StatusTrecho.escura:
        pontos += p["pontos_trecho_escuro"]
        fatores.append(f"+{p['pontos_trecho_escuro']}: trecho escuro")
    elif status == StatusTrecho.parcial:
        pontos += p["pontos_trecho_parcial"]
        fatores.append(f"+{p['pontos_trecho_parcial']}: trecho parcialmente escuro")
    if sensor_lux is not None and sensor_lux < p["limiar_sensor_lux"]:
        pontos += p["pontos_sensor_lux_baixo"]
        fatores.append(f"+{p['pontos_sensor_lux_baixo']}: sensor de luz abaixo de {p['limiar_sensor_lux']} lux")

    pontos = min(pontos, 100)
    if pontos >= p["faixas"]["alta"]:
        nivel = NivelPrioridade.alta
    elif pontos >= p["faixas"]["media"]:
        nivel = NivelPrioridade.media
    else:
        nivel = NivelPrioridade.baixa
    return Prioridade(nivel=nivel, pontuacao=pontos, fatores=fatores)
