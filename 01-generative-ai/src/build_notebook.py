"""Gera notebooks/pipeline.ipynb (depois executado com nbconvert). Rodar: python src/build_notebook.py"""
import nbformat as nbf, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
nb = nbf.v4.new_notebook(); c = []
md = lambda s: c.append(nbf.v4.new_markdown_cell(s)); code = lambda s: c.append(nbf.v4.new_code_cell(s))
md("# Assistente de Iluminação Pública (rua escura) – RAG local\n"
   "GS 2026.2 CitizenTech · Generative AI for Engineering\n\n"
   "Pipeline: base de trechos com fonte → embeddings locais (Ollama) → busca top-k + limiar → LLM local com JSON, citação e recusa → agente com verificador.\n"
   "Configurações comparadas: **A** LLM sem contexto · **B** RAG simples · **C** agente com verificador.")
code("import os, sys, json, subprocess, pathlib, requests\nimport pandas as pd\nROOT = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == 'notebooks' else pathlib.Path.cwd()\nos.chdir(ROOT); sys.path.insert(0, str(ROOT / 'src'))\nimport ruaescura as r\nprint('Modelo LLM:', r.LLM, '| Embeddings:', r.EMB)\nprint('Ollama:', requests.get(r.OLLAMA + '/api/version').json())")
md("## 1. Base de conhecimento (trechos com fonte)")
code("T = pd.DataFrame(r.ler_jsonl(ROOT / 'base' / 'trechos.jsonl'))\nprint(len(T), 'trechos')\ndisplay(pd.read_csv(ROOT / 'base' / 'fontes.csv'))\nT.head(6)")
md("## 2. Tarefa e conjunto de teste com gabarito (inclui 'não consta')")
code("G = pd.DataFrame(r.ler_jsonl(ROOT / 'avaliacao' / 'conjunto_teste.jsonl'))\ndisplay(G.groupby(['split', 'tipo']).size().unstack())\nG[['id','split','tipo','pergunta']].head(8)")
md("## 3. Busca: recall@1, recall@3 e limiar (escolhido no conjunto dev)")
code("out = subprocess.run([sys.executable, 'src/01_recuperacao.py'], capture_output=True, text=True, cwd=ROOT); print(out.stdout, out.stderr[-500:])")
md("## 4. Placar das 3 configurações (conjunto de teste)\nOs resultados por pergunta ficam em `resultados/placar_*.jsonl`, gerados por `python src/02_placar.py` (leva de 30 a 60 min em CPU).")
code("out = subprocess.run([sys.executable, 'src/03_resumo.py'], capture_output=True, text=True, cwd=ROOT); print(out.stdout, out.stderr[-500:])")
md("## 5. Demonstração de alucinação: a mesma pergunta nas 3 configurações")
code("idx = r.Indice(); lim = json.load(open(ROOT / 'resultados' / 'limiar.json'))['limiar']\nfor q in ['Qual o prazo para consertar poste apagado em Fortaleza?', 'Qual o prazo de atendimento para um poste de iluminação caído em Porto Alegre?']:\n    print('PERGUNTA:', q)\n    for nome, fn in r.CONFIGS.items():\n        s = fn(q, idx, lim)\n        print(f\"  {nome:22s} status={s['status']:10s} resposta={s['resposta'][:90]!r} citacao={s['citacao']!r}\")\n    print()")
md("## 6. Uso integrado (mesma função da API)")
code("s = r.config_C('Como solicito o conserto de uma luminária faiscando em Porto Alegre?', idx, lim)\nprint(json.dumps(s, ensure_ascii=False, indent=2))")
nb["cells"] = c
(R / "notebooks").mkdir(exist_ok=True)
nbf.write(nb, R / "notebooks" / "pipeline.ipynb")
