import base64
import io
import json

import pytest
from PIL import Image

from src import contrato

# Exemplo da documentacao da Visao (04-visao-computacional/docs/integracao.md), versao 1.1
EXEMPLO_VISAO = {
    "versao_contrato": "1.1",
    "id_captura": "b58cccb5-ab16-43cb-8f35-180c00b2939d",
    "timestamp": "2026-11-09T22:12:45-03:00",
    "origem": "robo",
    "localizacao": {"latitude": -23.5505, "longitude": -46.6333, "fonte": "informada"},
    "sensor_lux": 2.4,
    "resumo": {"postes_acesos": 1, "postes_apagados": 1, "buracos": 0,
               "luminosidade_media": 44.7, "status_trecho": "escura"},
    "validacao": {"foto_valida": True, "falha_detectada": True, "abrir_chamado": True,
                  "motivos": ["1 poste(s) apagado(s) detectado(s)", "trecho classificado como escuro"]},
    "prioridade": {"nivel": "alta", "pontuacao": 90,
                   "fatores": ["+25: 1 poste(s) apagado(s)", "+30: trecho escuro"]},
    "fusao": {"alertas_sensor": ["escuro"], "tipos_chamado": ["conserto_poste"],
              "confirmacao": "confirmado", "motivos": []},
    "modelo": {"nome": "yolo26n-postes", "versao": "1.0"},
    "imagem_anonimizada_base64": None,
}


def jpeg_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 10, 10)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def test_achata_o_json_da_visao():
    linha = contrato.de_visao_v11(EXEMPLO_VISAO)
    assert linha["id_captura"] == "b58cccb5-ab16-43cb-8f35-180c00b2939d"
    assert (linha["latitude"], linha["longitude"]) == ("-23.5505", "-46.6333")
    assert linha["prioridade_nivel"] == "alta" and linha["prioridade_pontuacao"] == "90"
    assert linha["tipos_chamado"] == "conserto_poste"
    assert linha["confirmacao"] == "confirmado"
    assert linha["status_trecho"] == "escura" and linha["postes_apagados"] == "1"
    assert linha["sensor_lux"] == "2.4"
    assert linha["modelo"] == "yolo26n-postes 1.0"
    assert linha["motivos"] == "1 poste(s) apagado(s) detectado(s) | trecho classificado como escuro"


def test_campos_ausentes_viram_texto_vazio_e_varios_tipos_se_juntam():
    assert contrato.de_visao_v11({"id_captura": "A"})["latitude"] == ""
    ev = {"id_captura": "A", "fusao": {"tipos_chamado": ["conserto_poste", "buraco"]}}
    assert contrato.de_visao_v11(ev)["tipos_chamado"] == "conserto_poste|buraco"


@pytest.mark.parametrize("ruim", ["../x", "a/b", "", None, 12, "x" * 65])
def test_id_captura_invalido_e_rejeitado(ruim):
    with pytest.raises(ValueError):
        contrato.de_visao_v11({"id_captura": ruim})


def test_foto_em_base64_e_gravada_e_base64_invalido_e_ignorado(tmp_path):
    ev = {"id_captura": "F-1", "imagem_anonimizada_base64": jpeg_b64()}
    assert contrato.foto_do_evento(ev, tmp_path) == "fotos/F-1.jpg"
    assert (tmp_path / "fotos" / "F-1.jpg").is_file()

    ruim = {"id_captura": "F-2", "imagem_anonimizada_base64": "isso nao e base64!!"}
    assert contrato.foto_do_evento(ruim, tmp_path) == ""
    assert contrato.foto_do_evento({"id_captura": "F-3"}, tmp_path) == ""  # sem foto


def test_importar_define_o_status_inicial(tmp_path):
    aceito = dict(EXEMPLO_VISAO, id_captura="OK-1")
    recusado = dict(EXEMPLO_VISAO, id_captura="NO-1",
                    validacao={"abrir_chamado": False, "motivos": ["parece ser de dia"]})
    linhas, avisos = contrato.importar_eventos([aceito, recusado], set(), tmp_path)
    assert {x["id_captura"]: x["status"] for x in linhas} == {"OK-1": "validado", "NO-1": "recusado"}
    assert avisos == []

    linhas, _ = contrato.importar_eventos([aceito], set(), tmp_path, confirmar=True)
    assert linhas[0]["status"] == "confirmado"


def test_importar_nao_duplica_e_avisa_sobre_id_invalido(tmp_path):
    ev = dict(EXEMPLO_VISAO, id_captura="DUP-1")
    linhas, avisos = contrato.importar_eventos(
        [ev, dict(EXEMPLO_VISAO, id_captura="../ruim")], {"DUP-1"}, tmp_path)
    assert linhas == []
    assert len(avisos) == 2 and "ja existe" in avisos[0] and "invalido" in avisos[1]


def test_ler_eventos_aceita_jsonl_json_e_pasta(tmp_path):
    a, b = dict(EXEMPLO_VISAO, id_captura="A"), dict(EXEMPLO_VISAO, id_captura="B")
    (tmp_path / "um.json").write_text(json.dumps(a), encoding="utf-8")
    (tmp_path / "lista.json").write_text(json.dumps([b]), encoding="utf-8")
    (tmp_path / "eventos.jsonl").write_text(json.dumps(a) + "\n\n" + json.dumps(b) + "\n", encoding="utf-8")
    (tmp_path / "ignorar.txt").write_text("nao e evento", encoding="utf-8")

    assert [e["id_captura"] for e in contrato.ler_eventos(tmp_path / "eventos.jsonl")] == ["A", "B"]
    assert len(contrato.ler_eventos(tmp_path / "um.json")) == 1
    assert len(contrato.ler_eventos(tmp_path)) == 4  # um.json + lista.json + 2 do jsonl
