# API da Visão Computacional (CPU). Build a partir de 04-visao-computacional/:
#   docker build -t ruas-escuras-visao .
#   docker run -p 8000:8000 ruas-escuras-visao
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    MODELO_PATH=/app/models/best.pt

# upgrade: aplica as correções de segurança do Debian publicadas depois da imagem base (Trivy)
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# setuptools/wheel novos: os antigos trazem dependências embutidas com CVE (Trivy)
RUN pip install --upgrade pip "setuptools>=80" "wheel>=0.46.2"
# PyTorch CPU (imagem ~1 GB menor que a versão com CUDA); 2.10: corrige CVE da 2.6 (Trivy)
RUN pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY configs/ configs/
COPY visao/ visao/
COPY api/ api/
COPY web/ web/
COPY models/ models/

# usuário sem privilégios
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/saude').status==200 else 1)"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
