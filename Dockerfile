# Dockerfile para Sistema Inteligente NNA
FROM python:3.11-slim

LABEL maintainer="Sistema-NNA"
LABEL description="Sistema Inteligente para Identificación y Seguimiento de NNA"
LABEL version="2.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WORKDIR=/app

RUN groupadd -r appuser && useradd -r -g appuser appuser

RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    curl \
    libpq-dev \
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

RUN python -c "import pandas, sklearn, requests, bs4, flask_login, flask_sqlalchemy, argon2; print('Dependencias OK')"

EXPOSE 5000

CMD ["python", "wsgi.py"]