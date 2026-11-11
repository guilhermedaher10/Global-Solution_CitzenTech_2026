"""Simula o robô do Maker Lab (LDR + ultrassônico + GPS) mandando alertas para a API da Visão.

Serve para testar a integração antes do robô ficar pronto, e de exemplo para o firmware.

    # suba a API em outro terminal:  uvicorn api.main:app --port 8000
    python scripts/simular_robo.py                       # 4 cenários: escuro, buraco, os dois, normal
    python scripts/simular_robo.py --patrulha 20         # 20 leituras andando por uma rua
    python scripts/simular_robo.py --cenario ambos --foto data/exemplos/rua.jpg
                                                         # alerta + foto do mesmo ponto (fusão)

O JSON que o robô manda (POST /v1/alerta-robo):
    {"origem":"robo","latitude":-23.55,"longitude":-46.63,
     "sensor_lux":3.2,"sensor_distancia_cm":12,"alerta":["escuro","buraco"]}
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.error
import urllib.request

# Av. Paulista (SP), só para a demo
LAT0, LON0 = -23.5614, -46.6559

CENARIOS = {
    "escuro": {"sensor_lux": 2.1, "sensor_distancia_cm": 8, "alerta": ["escuro"]},
    "buraco": {"sensor_lux": 40.0, "sensor_distancia_cm": 26, "alerta": ["buraco"]},
    "ambos": {"sensor_lux": 3.2, "sensor_distancia_cm": 22, "alerta": ["escuro", "buraco"]},
    "normal": {"sensor_lux": 35.0, "sensor_distancia_cm": 8, "alerta": []},
}


def enviar_alerta(api: str, corpo: dict) -> dict:
    req = urllib.request.Request(f"{api}/v1/alerta-robo", data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def enviar_foto(api: str, foto: str, corpo: dict) -> dict:
    import httpx  # só para multipart; está no requirements-dev

    dados = {k: str(v) for k, v in corpo.items() if k != "alerta" and v is not None}
    dados["alerta"] = ",".join(corpo.get("alerta", []))
    with open(foto, "rb") as f:
        r = httpx.post(f"{api}/v1/analisar", files={"imagem": (foto, f, "image/jpeg")}, data=dados,
                       timeout=60)
    r.raise_for_status()
    return r.json()


def mostrar_alerta(nome: str, corpo: dict, resp: dict) -> None:
    led = {"led_vermelho": "🔴", "led_amarelo": "🟡", "nenhuma": "⚪"}[resp["acao_robo"]]
    p = resp["prioridade_previa"]
    print(f"{led} {nome:<8} lux={corpo['sensor_lux']:<5} dist={corpo['sensor_distancia_cm']:<4}cm "
          f"-> {resp['status']:<10} prioridade {p['nivel']} ({p['pontuacao']})")
    for f in p["fatores"]:
        print(f"      · {f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--cenario", choices=list(CENARIOS), help="manda só este cenário")
    ap.add_argument("--patrulha", type=int, metavar="N", help="N leituras aleatórias ao longo de uma rua")
    ap.add_argument("--foto", help="também manda esta foto para /v1/analisar com as mesmas leituras")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    if args.patrulha:
        rnd = random.Random(args.seed)
        envios = []
        for i in range(args.patrulha):
            trecho_apagado = 6 <= i < 10          # um trecho escuro no meio da rua
            envios.append((f"ponto {i + 1}", {
                "origem": "robo", "latitude": round(LAT0 + i * 0.0002, 6), "longitude": LON0,
                "sensor_lux": round(rnd.uniform(0.5, 4) if trecho_apagado else rnd.uniform(12, 40), 1),
                "sensor_distancia_cm": 24 if i == 8 else round(rnd.uniform(6, 10), 1),
            }))
    else:
        nomes = [args.cenario] if args.cenario else list(CENARIOS)
        envios = [(n, {"origem": "robo", "latitude": LAT0, "longitude": LON0, **CENARIOS[n]}) for n in nomes]

    try:
        for nome, corpo in envios:
            resp = enviar_alerta(args.api, corpo)
            mostrar_alerta(nome, corpo, resp)
            if args.foto:
                a = enviar_foto(args.api, args.foto, corpo)
                fz = a["fusao"]
                print(f"   📷 foto: {a['resumo']['postes_apagados']} apagado(s), trecho {a['resumo']['status_trecho']}"
                      f" -> {fz['confirmacao']}, chamado: {', '.join(fz['tipos_chamado']) or 'nenhum'}"
                      f", prioridade {a['prioridade']['nivel']} ({a['prioridade']['pontuacao']})")
    except urllib.error.URLError as e:
        print(f"Não consegui falar com a API em {args.api} ({e.reason}). Ela está rodando?\n"
              "  uvicorn api.main:app --port 8000")
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
