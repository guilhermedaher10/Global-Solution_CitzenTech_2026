"""Gêmeo digital: mesma IA do ESP32, leituras reais e o mesmo contrato do firmware (Vesper.h)."""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "ia"))

import gemeo_digital as g  # noqa: E402

VESPER_H = RAIZ / "firmware" / "MakerLab_Controle_Independente_TinyML" / "Vesper.h"


def test_modelo_lido_do_firmware_acerta_os_csvs_de_teste():
    m = g.carregar_modelo()
    assert len(m.w1) == 4 and len(m.w1[0]) == 12 and len(m.w2) == 12 and len(m.b2) == 4
    acertos, total = g.avaliar(m)
    assert total == 40 and acertos / total >= 0.95


def test_patrulha_avisa_os_trechos_escuros_respeitando_o_intervalo():
    carrinho = g.Carrinho(g.carregar_modelo())
    eventos = [e for i, (d, esc, _) in enumerate(g.leituras_do_percurso())
               if (e := carrinho.ler(i, d, esc)) is not None]
    escuros = [e for e in eventos if e.classe.startswith("escuro_")]
    assert {e.classe for e in escuros} == {"escuro_livre", "escuro_obstaculo"}
    # intervalo de 30 s: o percurso tem dois trechos escuros bem separados
    enviados, ultimo = [], None
    for e in escuros:
        t = e.indice * g.PERIODO_S
        if ultimo is None or t - ultimo >= g.INTERVALO_MIN_S:
            enviados.append(e)
            ultimo = t
    assert len(enviados) == 2
    assert enviados[0].longitude != enviados[1].longitude   # o carrinho andou


def test_json_igual_ao_do_firmware():
    ev = g.Evento(indice=100, classe="escuro_obstaculo", confianca=0.9734, latitude=-23.5641, longitude=-46.65)
    corpo = g.corpo_alerta(ev)
    assert corpo == {"origem": "robo", "latitude": -23.5641, "longitude": -46.65, "alerta": ["escuro"],
                     "classe_ia": "escuro_obstaculo", "confianca_ia": 0.973}
    firmware = VESPER_H.read_text(encoding="utf-8")
    for chave in corpo:
        assert f'\\"{chave}\\"' in firmware, f"Vesper.h não manda '{chave}'"
    assert '/v1/alerta-robo' in firmware
    url = re.search(r'URL = "([^"]+)"', firmware).group(1)
    assert url == g.API_PADRAO
