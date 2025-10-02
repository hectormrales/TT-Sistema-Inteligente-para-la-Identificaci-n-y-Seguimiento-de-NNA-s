# Dockerfile para Sistema Inteligente NNA
FROM python:3.11-slim

# Metadata
LABEL maintainer="Sistema-NNA"
LABEL description="Sistema Inteligente para Identificación y Seguimiento de NNA"
LABEL version="2.0"

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WORKDIR=/app

# Crear usuario no-root para seguridad
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Instalar dependencias del sistema para Chrome/Selenium
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    curl \
    wget \
    gnupg2 \
    ca-certificates \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR $WORKDIR

# Copiar requirements primero para aprovechar cache de Docker
COPY requirements.txt .

# Instalar dependencias Python básicas
RUN pip install --no-cache-dir -r requirements.txt

# Instalar dependencias avanzadas del sistema de scraping
RUN pip install --no-cache-dir \
    selenium==4.15.2 \
    aiohttp==3.8.6 \
    fake-useragent==1.4.0

# Copiar código fuente
COPY . .

# Crear directorios necesarios
RUN mkdir -p data logs && \
    chown -R appuser:appuser $WORKDIR

# Cambiar a usuario no-root
USER appuser

# Variables de entorno para Chrome en Docker
ENV CHROME_BIN=/usr/bin/chromium \
    CHROME_DRIVER=/usr/bin/chromedriver \
    DISPLAY=:99

# Verificar que las dependencias están instaladas correctamente
RUN python -c "import pandas, sklearn, requests, bs4, selenium, aiohttp; print('✅ Todas las dependencias importadas correctamente')"

# Puerto por defecto
EXPOSE 5000

# Health check para verificar que la aplicación está funcionando
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Comando por defecto - aplicación web avanzada
CMD ["python", "app_docker.py"]