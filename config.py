# config.py — Configuración centralizada del Sistema NNA
"""
Toda la configuración sensible se lee de variables de entorno.
En Docker, estas se inyectan desde el archivo .env vía docker-compose.

IMPORTANTE: La clase Config se define DESPUÉS de las variables de nivel
de módulo (RSS_FEEDS, HTTP_HEADERS, etc.) para que los servicios que solo
necesitan esas constantes (ej. nna-analyzer) puedan hacer `import config`
sin requerir SECRET_KEY ni PostgreSQL.
"""

import os
from datetime import timedelta
from urllib.parse import quote_plus


# ============================================================
# Configuración de Recolección de Noticias (nivel de módulo)
# ============================================================

# Fuentes de noticias para la recolección
RSS_FEEDS = [
    'https://www.jornada.com.mx/rss/politica.xml',
    'https://www.proceso.com.mx/feed',
    'https://aristeguinoticias.com/feed/',
    'https://www.animalpolitico.com/feed/',
    'https://www.sinembargo.mx/feed/',
    'https://www.forbes.com.mx/feed/',
    'https://www.elsoldemexico.com.mx/rss.xml',
    'https://www.elfinanciero.com.mx/rss/',
]

# Rutas de archivos
DATA_PATH = 'data/noticias.csv'

# Headers para evitar bloqueos por User-Agent
HTTP_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    )
}

# Parámetros para los modelos de ML
KMEANS_CLUSTERS = 5
LDA_TOPICS = 6
TFIDF_MAX_FEATURES = 5000


# ============================================================
# Configuración Flask y Seguridad (clase Config)
# ============================================================
# Se define al final para que `import config` no falle en servicios
# que no necesitan autenticación (ej. nna-analyzer).

class Config:
    """Configuración base — se usa en producción (Docker)."""

    # --- Clave secreta (se valida en create_app(), no aquí) ---
    SECRET_KEY = os.environ.get('SECRET_KEY', '')

    # --- Base de datos PostgreSQL ---
    _PG_USER = os.environ.get('POSTGRES_USER', 'nna_admin')
    _PG_PASS = quote_plus(os.environ.get('POSTGRES_PASSWORD', ''))
    _PG_HOST = os.environ.get('POSTGRES_HOST', 'nna-postgres')
    _PG_PORT = os.environ.get('POSTGRES_PORT', '5432')
    _PG_DB   = os.environ.get('POSTGRES_DB', 'nna_auth_db')

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{_PG_USER}:{_PG_PASS}@{_PG_HOST}:{_PG_PORT}/{_PG_DB}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,       # Verifica conexión antes de usarla
        'pool_recycle': 300,         # Recicla conexiones cada 5 min
        'pool_size': 5,
        'max_overflow': 10,
    }

    # --- Sesiones seguras ---
    SESSION_COOKIE_HTTPONLY = True    # JS no puede leer la cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # Protección CSRF implícita
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.environ.get('SESSION_LIFETIME_MINUTES', 60))
    )
    SESSION_COOKIE_NAME = 'nna_session'

    # --- CSRF ---
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600      # Token válido por 1 hora

    # --- Otras ---
    JSON_AS_ASCII = False