"""Passo 6/7: monta o placar e lista erros reais. Rodar: python src/03_resumo.py"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pandas as pd
from ruaescura import RAIZ
linhas = []
for nome in ["A_sem_contexto", "B_rag_simples", "C_agente_verificador"]:
    arq = RAIZ / "resultados" / f"placar_{nome}.jsonl"
    if not arq.exists(): continue
    D = pd.DataFrame([json.loads(l) for l in open(arq, encoding="utf-8")])
    r = D[D.tipo == "resposta"]; n = D[D.tipo == "nao_consta"]
    linhas.append(dict(config=nome, perguntas=len(D),
        acertos=f"{int(D.acerto.sum())}/{len(D)}", acuracia=round(D.acerto.mean(), 3),
        acerto_com_resposta=f"{int(r.acerto.sum())}/{len(r)}",
        recusa_correta=f"{int(n.acerto.sum())}/{len(n)}",
        json_valido=round(D.json_valido.mean(), 3),
        citacao_valida_nas_ok=round(r[r.status == 'ok'].citacao_ok.mean(), 3) if (r.status == 'ok').any() else 0,
        seg_medio=round(D.segundos.mean(), 1)))
P = pd.DataFrame(linhas)
print(P.to_string(index=False))
P.to_csv(RAIZ / "resultados" / "placar.csv", index=False)
print("\nERROS (todas as configurações):")
for nome in P.config:
    for l in open(RAIZ / "resultados" / f"placar_{nome}.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if not d["acerto"]:
            print(f"[{nome}] {d['id']} ({d['tipo']}) {d['pergunta']}\n    -> status={d['status']} resp={d['resposta'][:110]!r} cit={d['citacao']!r} motivo={d.get('motivo')}")
