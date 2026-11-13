"""API local. Rodar (na pasta do projeto): uvicorn src.api:app --port 8000   (ou: python src/api.py)
Exemplo:  curl -X POST localhost:8000/consulta -H "Content-Type: application/json" -d '{"pergunta":"Qual o prazo para poste caído em Porto Alegre?"}'
"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fastapi import FastAPI
from pydantic import BaseModel
from ruaescura import Indice, config_C, RAIZ

app = FastAPI(title="Assistente de Iluminação Pública (RAG local)")
idx = Indice()
limiar = json.load(open(RAIZ / "resultados" / "limiar.json"))["limiar"]

class Consulta(BaseModel):
    pergunta: str

@app.get("/saude")
def saude():
    return {"ok": True, "trechos": len(idx.trechos), "limiar": limiar}

@app.post("/consulta")
def consulta(c: Consulta):
    s = config_C(c.pergunta, idx, limiar)
    s["trecho_citado"] = idx.por_id[s["citacao"]]["texto"] if s["citacao"] in idx.por_id else None
    s["aviso"] = "Pré-orientação automática. Confirme com o canal oficial da prefeitura (humano no circuito)."
    return s

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
