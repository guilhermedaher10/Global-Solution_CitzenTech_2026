"""Fusão sensor + visão: o robô DESCONFIA, a foto CONFIRMA e diz o tipo do problema.

O robô do Maker Lab não tem câmera: tem LDR (luz), ultrassônico (buraco) e GPS.
- Só com os sensores (`triar_alerta`): o ponto vira uma SUSPEITA com prioridade prévia.
- Com uma foto do mesmo lugar (`fundir`): a suspeita é confirmada ou não, e o chamado ganha
  um tipo (conserto, instalação, poda, buraco), que decide o setor da prefeitura.

Tudo determinístico e explicável; limiares em configs/regras.yaml.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .config import regras
from .schemas import (
    AcaoRobo, AlertaRobo, Confirmacao, Fusao, Localizacao, NivelPrioridade, Prioridade,
    RespostaAlerta, StatusTrecho, TipoAlerta, TipoChamado,
)

FUSO_SP = timezone(timedelta(hours=-3))


@dataclass
class Sinais:
    """Leitura dos sensores já interpretada."""
    alertas: list[TipoAlerta] = field(default_factory=list)
    motivos: list[str] = field(default_factory=list)

    @property
    def escuro(self) -> bool:
        return TipoAlerta.escuro in self.alertas

    @property
    def buraco(self) -> bool:
        return TipoAlerta.buraco in self.alertas


def ler_sensores(sensor_lux: float | None = None, sensor_distancia_cm: float | None = None,
                 alerta: list[TipoAlerta | str] | None = None) -> Sinais:
    """Junta o que o robô disse que disparou com o que as leituras indicam."""
    r = regras()
    limiar_lux = r["prioridade"]["limiar_sensor_lux"]
    limiar_dist = r["sensores"]["distancia_buraco_cm"]
    s = Sinais()
    for a in alerta or []:
        a = TipoAlerta(a)
        if a not in s.alertas:
            s.alertas.append(a)
            s.motivos.append(f"o robô sinalizou '{a.value}'")
    if sensor_lux is not None and sensor_lux < limiar_lux and not s.escuro:
        s.alertas.append(TipoAlerta.escuro)
        s.motivos.append(f"LDR marcou {sensor_lux} lux (abaixo de {limiar_lux})")
    if sensor_distancia_cm is not None and sensor_distancia_cm >= limiar_dist and not s.buraco:
        s.alertas.append(TipoAlerta.buraco)
        s.motivos.append(f"ultrassônico marcou {sensor_distancia_cm} cm (desnível a partir de {limiar_dist} cm)")
    return s


def fundir(sinais: Sinais, *, acesos: int, apagados: int, buracos: int,
           status: StatusTrecho, foto_valida: bool = True, luminosidade: float | None = None) -> Fusao:
    if not foto_valida:
        # foto ruim não confirma nem desmente o sensor: a suspeita do robô continua aberta
        return Fusao(alertas_sensor=sinais.alertas, tipos_chamado=[],
                     confirmacao=Confirmacao.nao_confirmado if sinais.alertas else Confirmacao.sem_sensor,
                     motivos=["a foto não serve de evidência (veja validacao.motivos)"
                              + ("; a suspeita do robô continua aberta" if sinais.alertas else "")])
    tipos: list[TipoChamado] = []
    motivos: list[str] = []
    sem_poste = acesos + apagados == 0
    trecho_escuro = status == StatusTrecho.escura

    if apagados > 0:
        tipos.append(TipoChamado.conserto_poste)
        motivos.append("poste apagado na foto: conserto")
    breu = luminosidade is not None and luminosidade < regras()["luminosidade"]["limiar_breu"]
    if sem_poste and breu:
        tipos.append(TipoChamado.trecho_sem_luz)
        motivos.append("breu sem poste visível: poste apagado no escuro ou inexistente; inspeção no local")
    elif sem_poste and (trecho_escuro or sinais.escuro):
        tipos.append(TipoChamado.instalacao_iluminacao)
        motivos.append("trecho escuro sem poste visível: pedido de instalação de iluminação")
    if sinais.escuro and acesos > 0 and apagados == 0 and not trecho_escuro:
        tipos.append(TipoChamado.poda_ou_obstrucao)
        motivos.append("o robô mediu pouca luz, mas o poste está aceso: árvore ou obstáculo "
                       "bloqueando a luz, ou lâmpada fraca")
    if buracos > 0:
        tipos.append(TipoChamado.buraco)
        motivos.append(f"{buracos} buraco(s) na foto")

    if not sinais.alertas:
        return Fusao(alertas_sensor=[], tipos_chamado=tipos, confirmacao=Confirmacao.sem_sensor,
                     motivos=motivos or ["sem leitura de sensor"])

    confirmados = 0
    if sinais.escuro:
        if apagados > 0 or trecho_escuro:
            confirmados += 1
            motivos.append("escuro: a foto confirma o sensor de luz")
        else:
            motivos.append("escuro: a foto não mostra trecho escuro")
    if sinais.buraco:
        if buracos > 0:
            confirmados += 1
            motivos.append("buraco: a foto confirma o ultrassônico")
        else:
            motivos.append("buraco: não aparece na foto; segue como suspeita")

    if confirmados == len(sinais.alertas):
        conf = Confirmacao.confirmado
    elif confirmados:
        conf = Confirmacao.parcial
    else:
        conf = Confirmacao.nao_confirmado
    return Fusao(alertas_sensor=sinais.alertas, tipos_chamado=tipos, confirmacao=conf, motivos=motivos)


def triar_alerta(alerta: AlertaRobo) -> RespostaAlerta:
    """Alerta só de sensores (sem foto): vira suspeita com prioridade prévia e ação para o robô."""
    sinais = ler_sensores(alerta.sensor_lux, alerta.sensor_distancia_cm, alerta.alerta)
    p = regras()["alerta_robo"]
    faixas = regras()["prioridade"]["faixas"]
    loc = Localizacao(latitude=alerta.latitude, longitude=alerta.longitude, fonte="informada",
                      endereco=alerta.endereco)
    cidadao = alerta.origem.value == "cidadao"
    base = dict(id_alerta=str(uuid.uuid4()),
                timestamp=datetime.now(FUSO_SP).isoformat(timespec="seconds"),
                alertas=sinais.alertas, localizacao=loc)

    if not sinais.alertas:
        return RespostaAlerta(**base, status="descartado",
                              prioridade_previa=Prioridade(nivel=NivelPrioridade.nenhuma, pontuacao=0,
                                                           fatores=["nenhum sensor disparou"]),
                              proximo_passo="nada a fazer", acao_robo=AcaoRobo.nenhuma)

    pontos, fatores = 0, list(sinais.motivos)
    if sinais.escuro:
        pontos += p["pontos_escuro"]
        fatores.append(f"+{p['pontos_escuro']}: trecho escuro")
    if sinais.buraco:
        pontos += p["pontos_buraco"]
        fatores.append(f"+{p['pontos_buraco']}: possível buraco")
    if sinais.escuro and sinais.buraco:
        pontos += p["pontos_escuro_e_buraco"]
        fatores.append(f"+{p['pontos_escuro_e_buraco']}: buraco no escuro (risco de queda)")
    pontos = min(pontos, 100)
    nivel = (NivelPrioridade.alta if pontos >= faixas["alta"]
             else NivelPrioridade.media if pontos >= faixas["media"] else NivelPrioridade.baixa)

    return RespostaAlerta(
        **base, status="suspeita",
        prioridade_previa=Prioridade(nivel=nivel, pontuacao=pontos, fatores=fatores),
        proximo_passo=("relato registrado: envie uma foto do local para confirmar e acelerar o atendimento"
                       if cidadao else
                       "aguardando foto de confirmação (cidadão próximo ou patrulha) para virar chamado"),
        acao_robo=AcaoRobo.led_vermelho if nivel == NivelPrioridade.alta else AcaoRobo.led_amarelo,
    )
