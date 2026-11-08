# Dockerfile para Sistema Inteligente NNA — Producción v2026 (Ligero ~220MB)
FROM python:3.11-slim

LABEL maintainer="Futuro Con Derechos — Sistema NNA"
LABEL description="Sistema Inteligente para Identificación y Seguimiento de NNA en Orfandad por Feminicidio"
LABEL version="2026.2"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WORKDIR=/app

RUN groupadd -r appuser && useradd -r -g appuser -m appuser

RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    curl \
    ca-certificates \
    libpq-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR $WORKDIR

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data logs && \
    chown -R appuser:appuser $WORKDIR

USER appuser

ENV PYTHONPATH=/app \
    DATA_DIR=/app/data \
    LOGS_DIR=/app/logs

RUN python -c "import pandas, requests, bs4, pydantic, scrapling, curl_cffi, trafilatura, flask_login, flask_sqlalchemy, argon2; print('Dependencias ligeras NNA Monitor 2026 OK')"

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:5000/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "wsgi:app"]
