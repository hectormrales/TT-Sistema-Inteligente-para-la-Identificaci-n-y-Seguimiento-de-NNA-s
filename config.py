# config.py — Configuración centralizada del Sistema NNA
"""
Toda la configuración sensible se lee de variables de entorno.
En Docker se inyectan desde .env vía docker-compose.
"""

import os
from datetime import timedelta
from urllib.parse import quote_plus


# ============================================================
# Recolección de noticias (usado por src/collection)
# ============================================================

# ── Feeds RSS Dirigidos: Búsqueda focalizada en Feminicidio + NNA en Orfandad (México) ──
# Se eliminaron los RSS generales de portadas de periódicos (política, finanzas, deportes)
# para evitar ruido masivo y bloqueos 403 en dominios obsoletos.
RSS_FEEDS = [
    # ── Google News queries focalizados (Feminicidio + NNA/Orfandad — SOLO MÉXICO) ──
    'https://news.google.com/rss/search?q=feminicidio+hijos+hu%C3%A9rfanos+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+menores+orfandad+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=asesinato+mujer+hijos+quedaron+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=DIF+custodia+feminicidio+hijos+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=%22v%C3%ADctimas+indirectas%22+feminicidio+ni%C3%B1os+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+%22frente+a+sus+hijos%22+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+%22era+madre+de%22+hijos+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+Estado+de+M%C3%A9xico+menores+hijos&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+CDMX+Jalisco+Puebla+Veracruz+hijos+menores&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+orfandad+redes+sociales+hijos+mexico&hl=es-419&gl=MX&ceid=MX:es-419',
    # ── Bing News RSS queries (URLs directas + snippets reales, México) ──
    'https://www.bing.com/news/search?q=feminicidio+hijos+orfandad+Mexico&format=rss&cc=MX&setlang=es-MX',
    'https://www.bing.com/news/search?q=feminicidio+menor+huerfano+Mexico&format=rss&cc=MX&setlang=es-MX',
    'https://www.bing.com/news/search?q=asesinan+mujer+frente+a+sus+hijos+Mexico&format=rss&cc=MX&setlang=es-MX',
    'https://www.bing.com/news/search?q=feminicidio+DIF+resguardo+menores+Mexico&format=rss&cc=MX&setlang=es-MX',
    'https://www.bing.com/news/search?q=mujer+asesinada+era+madre+de+hijos+Mexico&format=rss&cc=MX&setlang=es-MX',
    'https://www.bing.com/news/search?q=feminicidio+victimas+indirectas+ninos+Mexico&format=rss&cc=MX&setlang=es-MX',
    # ── Medio especializado en género y DDHH en México ──
    'https://cimacnoticias.com.mx/feed/',
]

# Queries dirigidos para DuckDuckGo (soporta rango de fechas df=start..end y redes sociales)
TARGETED_SEARCH_QUERIES = [
    'feminicidio "dejó en orfandad" menor México',
    'asesinan a mujer "frente a sus hijos" México',
    'feminicidio "era madre de" hijos México',
    'feminicidio "bajo resguardo del DIF" menor México',
    'feminicidio mexico deja niño facebook',
    'feminicidio orfandad hijos site:facebook.com mexico',
    'feminicidio hijos orfandad site:x.com mexico',
]

# Máximo de artículos candidatos por ciclo a los que se les descarga el cuerpo completo en paralelo
MAX_FULLTEXT_ENRICH_ARTICLES = int(os.environ.get('MAX_FULLTEXT_ENRICH_ARTICLES', '40'))

HTTP_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
}

# ============================================================
# Scoring de relevancia (dual-axis)
# ============================================================

# Pesos para la puntuación compuesta
RELEVANCE_WEIGHT_FEMINICIDIO = 0.55   # eje feminicidio
RELEVANCE_WEIGHT_NNA = 0.45           # eje NNA / víctimas indirectas

# Umbral mínimo para considerar una noticia "relevante"
RELEVANCE_THRESHOLD = 0.25

# Multiplicador cuando el keyword match está en el título
TITLE_BOOST = 3.0

# Parámetros de ML
KMEANS_CLUSTERS = 5
LDA_TOPICS = 6
TFIDF_MAX_FEATURES = 5000


# ============================================================
# Configuración Flask + Seguridad
# ============================================================

def _resolve_database_uri() -> str:
    """
    Determina la URI de base de datos:
    1. Si existe DATABASE_URL en el entorno, la utiliza directamente.
    2. Si corre dentro de Docker (/.dockerenv) o si PostgreSQL responde en el host configurado, usa PostgreSQL.
    3. En ejecución local directa (sin Docker ni PostgreSQL local encendido), usa SQLite en data/nna_local.db
       para permitir pruebas inmediatas sin fricción.
    """
    explicit_url = os.environ.get('DATABASE_URL', '').strip()
    if explicit_url:
        return explicit_url

    pg_user = os.environ.get('POSTGRES_USER', 'nna_admin')
    pg_pass = quote_plus(os.environ.get('POSTGRES_PASSWORD', ''))
    pg_host = os.environ.get('POSTGRES_HOST', 'nna-postgres')
    pg_port = os.environ.get('POSTGRES_PORT', '5432')
    pg_db = os.environ.get('POSTGRES_DB', 'nna_auth_db')
    pg_uri = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"

    # Si estamos dentro de un contenedor Docker, usar siempre PostgreSQL
    if os.path.exists('/.dockerenv'):
        return pg_uri

    # Fuera de Docker: verificar conectividad rápida al puerto de PostgreSQL
    import socket
    check_host = '127.0.0.1' if pg_host == 'nna-postgres' else pg_host
    try:
        with socket.create_connection((check_host, int(pg_port)), timeout=0.6):
            return f"postgresql://{pg_user}:{pg_pass}@{check_host}:{pg_port}/{pg_db}"
    except OSError:
        base_dir = os.path.abspath(os.path.dirname(__file__))
        data_dir = os.path.join(base_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        sqlite_path = os.path.join(data_dir, 'nna_local.db').replace('\\', '/')
        return f"sqlite:///{sqlite_path}"


class Config:
    """Configuración base para la aplicación Flask."""

    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()

    SQLALCHEMY_DATABASE_URI = _resolve_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = (
        {'pool_pre_ping': True}
        if SQLALCHEMY_DATABASE_URI.startswith('sqlite')
        else {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 5,
            'max_overflow': 10,
        }
    )

    # --- Sesiones ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.environ.get('SESSION_LIFETIME_MINUTES', 60))
    )
    SESSION_COOKIE_NAME = 'nna_session'

    # --- CSRF ---
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # --- Otras ---
    JSON_AS_ASCII = False
    DATA_PATH = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        "data",
        "noticias_analyzed_simplified.csv",
    )
