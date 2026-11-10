"""Passo 4: recall@1, recall@3 e escolha do limiar (no conjunto dev). Rodar: python src/01_recuperacao.py"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import numpy as np
from ruaescura import Indice, ler_jsonl, RAIZ

idx = Indice()
T = ler_jsonl(RAIZ / "avaliacao" / "conjunto_teste.jsonl")
linhas = []
for t in T:
    rec = idx.buscar(t["pergunta"], 3)
    ids = [r["id"] for r in rec]
    linhas.append(dict(id=t["id"], split=t["split"], tipo=t["tipo"], top1=rec[0]["score"], ids=ids,
                       hit1=bool(set(ids[:1]) & set(t["fontes"])), hit3=bool(set(ids) & set(t["fontes"]))))

def recall(split):
    L = [l for l in linhas if l["tipo"] == "resposta" and l["split"] in split]
    return len(L), sum(l["hit1"] for l in L) / len(L), sum(l["hit3"] for l in L) / len(L)

for nome, sp in [("dev", ["dev"]), ("teste", ["teste"]), ("todos", ["dev", "teste"])]:
    n, r1, r3 = recall(sp)
    print(f"{nome:6s} n={n:2d}  recall@1={r1:.3f}  recall@3={r3:.3f}")

# limiar: escolhido SÓ no dev. Critério: o maior limiar que mantém TODAS as perguntas respondíveis do dev
# (não queremos recusar quem tem resposta). A recusa fina fica com o modelo e o verificador.
dev = [l for l in linhas if l["split"] == "dev"]
pos_dev = [l["top1"] for l in dev if l["tipo"] == "resposta"]
melhor = round(min(pos_dev) - 0.005, 4)
def taxa(th, L):
    pos = [l for l in L if l["tipo"] == "resposta"]; neg = [l for l in L if l["tipo"] == "nao_consta"]
    return sum(l["top1"] >= th for l in pos) / len(pos), sum(l["top1"] < th for l in neg) / len(neg)
teste = [l for l in linhas if l["split"] == "teste"]
print(f"limiar escolhido no dev = {melhor:.4f}")
print("  dev   : respostas mantidas=%.2f  nao_consta barradas=%.2f" % taxa(melhor, dev))
print("  teste : respostas mantidas=%.2f  nao_consta barradas=%.2f" % taxa(melhor, teste))
print("scores top1 dev  resposta :", sorted(round(l['top1'],3) for l in dev if l['tipo']=='resposta'))
print("scores top1 dev  nao_consta:", sorted(round(l['top1'],3) for l in dev if l['tipo']=='nao_consta'))
(RAIZ / "resultados").mkdir(exist_ok=True)
json.dump({"limiar": melhor}, open(RAIZ / "resultados" / "limiar.json", "w"))
json.dump(linhas, open(RAIZ / "resultados" / "recuperacao.json", "w"), ensure_ascii=False, indent=1)
print("\nFalhas de recall@3 (para analisar):")
for l in linhas:
    if l["tipo"] == "resposta" and not l["hit3"]:
        print(" ", l["id"], l["ids"])
