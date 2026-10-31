FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY app.py analizar_planos.py ./
COPY computos ./computos
COPY configuraciones ./configuraciones

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "computos.api.aplicacion:app", "--host", "0.0.0.0", "--port", "8000"]
