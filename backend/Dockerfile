
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    COMPUTOESTIA_TESSERACT_CMD=/usr/bin/tesseract

# Instalar Tesseract OCR y el idioma español
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-spa \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY app.py analizar_planos.py ./
COPY computos ./computos
COPY configuraciones ./configuraciones
COPY data ./data

EXPOSE 8000

CMD ["uvicorn", "computos.api.aplicacion:app", "--host", "0.0.0.0", "--port", "8000"]
