# Assistente de Iluminação Pública (rua escura) – RAG local

GS 2026.2 CitizenTech · FIAP · Generative AI for Engineering

**Integrantes:**

| Nome | RM |
|---|---|
| Guilherme Daher | 98611 |
| Gabriel Freitas | 550187 |
| Heitor Nobre | 551539 |
| Vinicius Yamashita | 550908 |
| Lucca Alexandre | 99700 |

Assistente que recebe uma pergunta sobre iluminação pública (poste apagado, lâmpada piscando, prazo, canal de atendimento) e responde **somente com base em trechos de fontes oficiais**, em JSON, com **citação do trecho** e **recusa** ("não consta") quando a base não cobre. Tudo roda local, com LLM `qwen2.5:1.5b-instruct` e embeddings `nomic-embed-text`, via Ollama. Não usa chave de API nem dado pessoal.

Relatório completo: [RELATORIO.md](RELATORIO.md)

## Estrutura
```
base/        trechos.jsonl (31 trechos com fonte) e fontes.csv
avaliacao/   conjunto_teste.jsonl (40 perguntas com gabarito, 14 "não consta")
src/         ruaescura.py (núcleo), 01_recuperacao.py, 02_placar.py, 03_resumo.py, api.py
notebooks/   pipeline.ipynb (com saídas salvas)
resultados/  limiar.json, recuperacao.json, placar.csv, placar_*.jsonl
```

## Como reproduzir
Pré-requisitos: Python 3.11+ e o [Ollama](https://ollama.com) instalado e em execução (no Windows e no Mac ele fica ativo depois de instalado; no Linux rode `ollama serve`).

```bash
# 1. modelos locais (cerca de 1,3 GB no total)
ollama pull qwen2.5:1.5b-instruct
ollama pull nomic-embed-text

# 2. ambiente Python
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. (opcional) regerar base e gabarito
python src/build_base.py
python src/build_teste.py

# 4. busca: recall@1, recall@3 e limiar (rápido)
python src/01_recuperacao.py

# 5. placar das 3 configurações no conjunto de teste (30 a 60 min em CPU; pode interromper e rodar de novo)
python src/02_placar.py

# 6. placar e erros
python src/03_resumo.py

# 7. notebook com saídas
jupyter lab notebooks/pipeline.ipynb

# 8. API
python src/api.py      # http://127.0.0.1:8000/docs
```

Teste da API (também funciona no Postman: `POST http://127.0.0.1:8000/consulta`, body JSON):
```bash
curl -X POST http://127.0.0.1:8000/consulta -H "Content-Type: application/json" \
  -d '{"pergunta":"Qual o prazo para consertar poste caído em Porto Alegre?"}'
```

Variáveis opcionais: `LLM_MODEL` (padrão `qwen2.5:1.5b-instruct`), `EMB_MODEL`, `OLLAMA_URL`.

Observação: com temperatura 0 o resultado é quase determinístico, mas pode variar um pouco entre máquinas e versões do Ollama.

## Resultados (conjunto de teste, 30 perguntas)
| Configuração | Acertos | Com resposta | Recusa correta | JSON válido | Citação válida |
|---|---|---|---|---|---|
| A. LLM sem contexto | 3/30 (10%) | 1/19 | 2/11 | 93% | 0% |
| B. RAG simples | 25/30 (83%) | 17/19 | 8/11 | 100% | 82% |
| C. Agente com verificador | 22/30 (73%) | 12/19 | 10/11 | 100% | 100% |

Detalhes, interpretação e os 5 erros no [relatório](RELATORIO.md).

## LGPD e uso responsável
A base contém só informação pública de órgãos oficiais. O sistema não pede nem guarda nome, telefone ou endereço. A resposta é uma pré-orientação e traz o aviso para confirmar no canal oficial da prefeitura (humano no circuito). Cada resposta mostra o trecho citado, o que a torna explicável.
