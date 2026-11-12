"""Passo 6: roda as 3 configurações no conjunto de TESTE e grava resultados/. Rodar: python src/02_placar.py
Pode ser interrompido e rodado de novo: continua de onde parou."""
import json, sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ruaescura import Indice, ler_jsonl, RAIZ, CONFIGS, avaliar_resposta, citacao_valida

idx = Indice()
limiar = json.load(open(RAIZ / "resultados" / "limiar.json"))["limiar"]
T = [t for t in ler_jsonl(RAIZ / "avaliacao" / "conjunto_teste.jsonl") if t["split"] == "teste"]
LIM = int(sys.argv[1]) if len(sys.argv) > 1 else None
if LIM: T = T[:LIM]
for nome, fn in CONFIGS.items():
    arq = RAIZ / "resultados" / f"placar_{nome}.jsonl"
    feitos = {json.loads(l)["id"] for l in open(arq, encoding="utf-8")} if arq.exists() else set()
    with open(arq, "a", encoding="utf-8") as f:
        for t in T:
            if t["id"] in feitos: continue
            t0 = time.time()
            s = fn(t["pergunta"], idx, limiar)
            s.update(id=t["id"], tipo=t["tipo"], pergunta=t["pergunta"], segundos=round(time.time() - t0, 1),
                     acerto=avaliar_resposta(t, s), citacao_ok=citacao_valida(s, idx),
                     citacao_gabarito=bool(set([s.get("citacao", "")]) & set(t["fontes"])))
            f.write(json.dumps(s, ensure_ascii=False) + "\n"); f.flush()
            print(nome, t["id"], "acerto" if s["acerto"] else "ERRO", s["segundos"], "s", flush=True)
