# Imagem do assistente GenAI (01-generative-ai). Fica na pasta do DevOps para não mexer na pasta
# do colega; o build usa o código dele como contexto (ver docker-compose.yml).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
# só o que a API usa (o requirements dele inclui Jupyter, que não vai para produção)
RUN pip install requests==2.32.3 numpy==2.2.6 fastapi==0.162.2 "uvicorn[standard]==0.54.0"

COPY src/ src/
COPY base/ base/
COPY resultados/limiar.json resultados/emb.npy resultados/

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/saude').status==200 else 1)"
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8001"]
