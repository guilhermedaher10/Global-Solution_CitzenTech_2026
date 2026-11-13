from datetime import date

from src.agrupamento import distancia_m, montar_plano

HOJE = date(2026, 11, 9)
LAT, LON = -23.5505, -46.6333
UM_DECIMILESIMO = 0.0001  # ~11 m de latitude


def c(cid, dlat=0.0, pont=50, tipos="conserto_poste", ts="2026-11-08T20:00:00", **kw) -> dict:
    base = {
        "id_captura": cid, "latitude": str(LAT + dlat), "longitude": str(LON),
        "prioridade_pontuacao": str(pont), "tipos_chamado": tipos, "timestamp": ts,
        "status": "confirmado", "rpa_etapa": "", "chamado_principal": "",
        "protocolo": "", "data_encaminhamento": "",
    }
    base.update(kw)
    return base


def existente(cid, status="encaminhado", dias_atras=5, dlat=0.0, **kw) -> dict:
    envio = date.fromordinal(HOJE.toordinal() - dias_atras).isoformat()
    return c(cid, dlat=dlat, status=status, protocolo="CH-X", data_encaminhamento=envio, **kw)


def ids_principais(plano):
    return [g.principal["id_captura"] for g in plano.novos]


def test_distancia_de_um_decimilesimo_de_grau_e_cerca_de_11_metros():
    d = distancia_m(LAT, LON, LAT + UM_DECIMILESIMO, LON)
    assert 10.5 < d < 11.7
    assert distancia_m(LAT, LON, LAT, LON) == 0


def test_agrupa_dentro_do_raio_e_o_de_maior_pontuacao_vira_principal(cfg):
    a, b = c("A", pont=40), c("B", dlat=UM_DECIMILESIMO, pont=90)
    plano = montar_plano([a, b], [a, b], HOJE, cfg)
    assert ids_principais(plano) == ["B"]
    assert [m["id_captura"] for m, _ in plano.novos[0].membros] == ["A"]
    assert not plano.anexos


def test_nao_agrupa_alem_do_raio(cfg):
    a, b = c("A"), c("B", dlat=0.001)  # ~111 m
    plano = montar_plano([a, b], [a, b], HOJE, cfg)
    assert sorted(ids_principais(plano)) == ["A", "B"]


def test_nao_agrupa_tipos_diferentes_no_mesmo_ponto(cfg):
    a, b = c("A", tipos="conserto_poste"), c("B", tipos="buraco")
    plano = montar_plano([a, b], [a, b], HOJE, cfg)
    assert sorted(ids_principais(plano)) == ["A", "B"]


def test_agrupa_quando_ha_um_tipo_em_comum(cfg):
    a = c("A", pont=100, tipos="conserto_poste|buraco")
    b = c("B", dlat=UM_DECIMILESIMO, pont=40, tipos="buraco")
    plano = montar_plano([a, b], [a, b], HOJE, cfg)
    assert ids_principais(plano) == ["A"] and len(plano.novos[0].membros) == 1


def test_desempate_por_horario_e_depois_por_id(cfg):
    a = c("B", pont=50, ts="2026-11-08T21:00:00")
    b = c("A", pont=50, ts="2026-11-08T20:00:00")
    plano = montar_plano([a, b], [a, b], HOJE, cfg)
    assert ids_principais(plano) == ["A"]  # o mais antigo e o principal


def test_anexa_a_chamado_ja_encaminhado_recente(cfg):
    ja = existente("EXISTENTE")
    novo = c("NOVO", dlat=UM_DECIMILESIMO)
    plano = montar_plano([novo], [ja, novo], HOJE, cfg)
    assert not plano.novos
    (o, alvo, dist), = plano.anexos
    assert (o["id_captura"], alvo["id_captura"]) == ("NOVO", "EXISTENTE") and dist < 12


def test_anexa_a_chamado_em_reparo_e_a_chamado_na_fila_do_portal(cfg):
    for ja in (existente("R", status="em_reparo"),
               existente("P", status="confirmado", rpa_etapa="na_fila_portal")):
        novo = c("NOVO")
        plano = montar_plano([novo], [ja, novo], HOJE, cfg)
        assert len(plano.anexos) == 1 and not plano.novos


def test_nao_anexa_a_chamado_antigo_resolvido_ou_que_e_membro(cfg):
    antigos = [
        existente("VELHO", dias_atras=45),                      # fora da janela de 30 dias
        existente("RESOLVIDO", status="resolvido"),             # ja consertado: falha nova e outro chamado
        existente("MEMBRO", chamado_principal="OUTRO"),         # so anexa a principais
        existente("LONGE", dlat=0.001),                         # fora do raio
        existente("OUTRO_SETOR", tipos="buraco"),               # setor diferente
    ]
    novo = c("NOVO")
    plano = montar_plano([novo], antigos + [novo], HOJE, cfg)
    assert ids_principais(plano) == ["NOVO"] and not plano.anexos


def test_raio_e_configuravel(cfg):
    from dataclasses import replace
    a, b = c("A"), c("B", dlat=0.001)  # ~111 m
    plano = montar_plano([a, b], [a, b], HOJE, replace(cfg, raio_agrupamento_m=150))
    assert len(plano.novos) == 1
