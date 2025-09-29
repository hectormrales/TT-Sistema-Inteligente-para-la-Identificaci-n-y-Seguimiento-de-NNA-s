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

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR $WORKDIR

# Copiar requirements primero para aprovechar cache de Docker
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Crear directorios necesarios
RUN mkdir -p data logs && \
    chown -R appuser:appuser $WORKDIR

# Cambiar a usuario no-root
USER appuser

# Verificar que las dependencias están instaladas correctamente
RUN python -c "import pandas, sklearn, requests, bs4; print('✅ Todas las dependencias importadas correctamente')"

# Puerto por defecto
EXPOSE 5000

# Comando por defecto - análisis
CMD ["python", "demo_simplified.py"]