"""Núcleo do assistente de iluminação pública (RAG local com Ollama).

Três configurações:
  A = LLM sem contexto
  B = RAG simples (top-k + limiar de 'não consta')
  C = agente com verificador (cita trecho recuperado, números e entidades conferem)
"""
import json, os, re, pathlib, unicodedata
import numpy as np
import requests

RAIZ = pathlib.Path(__file__).resolve().parent.parent
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LLM = os.environ.get("LLM_MODEL", "qwen2.5:1.5b-instruct")
EMB = os.environ.get("EMB_MODEL", "nomic-embed-text")

SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["ok", "nao_consta"]},
        "resposta": {"type": "string"},
        "citacao": {"type": "string"},
    },
    "required": ["status", "resposta", "citacao"],
}


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def ler_jsonl(caminho):
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


# ---------------------------------------------------------------- embeddings
def embed(textos, prefixo):
    r = requests.post(f"{OLLAMA}/api/embed",
                      json={"model": EMB, "input": [prefixo + t for t in textos]}, timeout=600)
    r.raise_for_status()
    v = np.array(r.json()["embeddings"], dtype="float32")
    return v / np.linalg.norm(v, axis=1, keepdims=True)


class Indice:
    def __init__(self):
        self.trechos = ler_jsonl(RAIZ / "base" / "trechos.jsonl")
        self.por_id = {t["id"]: t for t in self.trechos}
        cache = RAIZ / "resultados" / "emb.npy"
        cache.parent.mkdir(exist_ok=True)
        if cache.exists() and np.load(cache).shape[0] == len(self.trechos):
            self.vet = np.load(cache)
        else:
            self.vet = embed([t["texto"] for t in self.trechos], "search_document: ")
            np.save(cache, self.vet)

    def buscar(self, pergunta, k=3):
        q = embed([pergunta], "search_query: ")[0]
        sc = self.vet @ q
        idx = np.argsort(-sc)[:k]
        return [dict(self.trechos[i], score=float(sc[i])) for i in idx]


# ---------------------------------------------------------------- LLM
def chamar_llm(sistema, usuario):
    r = requests.post(f"{OLLAMA}/api/chat", json={
        "model": LLM, "stream": False, "format": SCHEMA,
        "options": {"temperature": 0, "num_ctx": 2048, "num_predict": 200},
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
    }, timeout=900)
    r.raise_for_status()
    bruto = r.json()["message"]["content"]
    try:
        d = json.loads(bruto)
        assert d["status"] in ("ok", "nao_consta")
        return {"status": d["status"], "resposta": str(d.get("resposta", "")),
                "citacao": str(d.get("citacao", "")).strip().strip("[]() '\"").strip(), "json_valido": True}
    except Exception:
        return {"status": "nao_consta", "resposta": bruto[:200], "citacao": "", "json_valido": False}


SIS_SEM_CTX = ("Você responde perguntas sobre iluminação pública no Brasil. "
               "Responda em JSON com status ('ok'), resposta curta e citacao (a lei ou fonte que usou).")

SIS_RAG = ("Você é um assistente de iluminação pública. Responda SOMENTE com base nos TRECHOS fornecidos. "
           "Se os trechos não trazem a resposta, ou a pergunta é sobre outra cidade ou assunto que não aparece neles, "
           "responda status 'nao_consta', resposta 'Não consta na base.' e citacao vazia. "
           "Se trazem, responda status 'ok', com resposta curta e direta, e em citacao coloque o id do trecho usado. "
           "Responda em JSON.")


def montar_contexto(trechos):
    return "\n".join(f"[{t['id']}] {t['texto']}" for t in trechos)


# ---------------------------------------------------------------- configurações
def config_A(pergunta, idx=None, limiar=None):
    r = chamar_llm(SIS_SEM_CTX, pergunta)
    r["recuperados"] = []
    return r


def config_B(pergunta, idx, limiar):
    rec = idx.buscar(pergunta, 3)
    out = {"recuperados": [t["id"] for t in rec], "score_top1": rec[0]["score"]}
    if rec[0]["score"] < limiar:
        out.update(status="nao_consta", resposta="Não consta na base.", citacao="", json_valido=True,
                   motivo="abaixo do limiar")
        return out
    r = chamar_llm(SIS_RAG, f"TRECHOS:\n{montar_contexto(rec)}\n\nPERGUNTA: {pergunta}")
    out.update(r)
    return out


NUM = re.compile(r"\d+(?:[.,/]\d+)*")


def verificar(pergunta, resposta, citacao, trecho_citado):
    """Devolve (ok, motivo). Verificações determinísticas e explicáveis."""
    if trecho_citado is None:
        return False, "citação não está entre os trechos recuperados"
    base = norm(trecho_citado["texto"])
    # 1) números da resposta precisam aparecer no trecho citado
    for n in NUM.findall(resposta):
        if n.lstrip("0") and n not in trecho_citado["texto"] and n.lstrip("0") not in trecho_citado["texto"]:
            return False, f"número '{n}' da resposta não está no trecho citado"
    # 2) nomes próprios da pergunta (fora o início) precisam aparecer no trecho citado
    palavras = re.findall(r"[A-Za-zÀ-ú]+", pergunta)
    for i, p in enumerate(palavras):
        if i == 0 or not (p[0].isupper() or (len(p) > 1 and p.isupper())):
            continue
        if norm(p) not in base and norm(p) not in ("sp",):
            return False, f"'{p}' (da pergunta) não aparece no trecho citado"
    return True, "ok"


def config_C(pergunta, idx, limiar):
    r = config_B(pergunta, idx, limiar)
    if r["status"] == "nao_consta":
        r["motivo"] = r.get("motivo", "modelo recusou")
        return r
    rec = idx.buscar(pergunta, 3)
    por_id = {t["id"]: t for t in rec}
    tent = 0
    while True:
        ok, mot = verificar(pergunta, r["resposta"], r["citacao"], por_id.get(r["citacao"]))
        if ok:
            r["motivo"] = "verificado"
            r["tentativas"] = tent + 1
            return r
        tent += 1
        if tent >= 2:
            return {"status": "nao_consta", "resposta": "Não consta na base.", "citacao": "",
                    "json_valido": True, "recuperados": r.get("recuperados", []),
                    "motivo": f"verificador reprovou: {mot}", "tentativas": tent}
        # segunda tentativa: só o melhor trecho e instrução mais rígida
        melhor = rec[0]
        r2 = chamar_llm(SIS_RAG + " Use exatamente o id do trecho e copie números do trecho.",
                        f"TRECHOS:\n{montar_contexto([melhor])}\n\nPERGUNTA: {pergunta}")
        r2["recuperados"] = r.get("recuperados", [])
        r2["score_top1"] = r.get("score_top1")
        r = r2
        por_id = {melhor["id"]: melhor}
        if r["status"] == "nao_consta":
            r["motivo"] = "modelo recusou na 2ª tentativa"
            r["tentativas"] = tent + 1
            return r


CONFIGS = {"A_sem_contexto": config_A, "B_rag_simples": config_B, "C_agente_verificador": config_C}


# ---------------------------------------------------------------- avaliação
def avaliar_resposta(item, saida):
    if item["tipo"] == "nao_consta":
        return saida["status"] == "nao_consta"
    if saida["status"] != "ok":
        return False
    return all(re.search(c, saida["resposta"], re.I) for c in item["chaves"])


def citacao_valida(saida, idx):
    return saida["status"] == "ok" and saida["citacao"] in idx.por_id
