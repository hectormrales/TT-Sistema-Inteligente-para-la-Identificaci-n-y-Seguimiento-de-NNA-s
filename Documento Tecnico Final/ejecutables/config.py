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

# ── Feeds RSS: secciones de seguridad/justicia/sociedad
#    + Google News queries para feminicidios con NNA ──────────
RSS_FEEDS = [
    # ── Medios mexicanos (generales y de seguridad) ─────────
    'https://www.jornada.com.mx/rss/politica.xml',
    'https://www.jornada.com.mx/rss/estados.xml',
    'https://www.jornada.com.mx/rss/sociedad.xml',
    'https://www.proceso.com.mx/rss',
    # 'https://aristeguinoticias.com/feed/',   # Verifica si funciona con cloudscraper
    # 'https://www.animalpolitico.com/feed/',  # 404 — feed discontinuado
    # 'https://www.sinembargo.mx/feed/',       # 403 persistente, circuit breaker
    'https://www.elsoldemexico.com.mx/rss.xml',
    'https://www.elfinanciero.com.mx/rss/',
    # 'https://www.eluniversal.com.mx/rss.xml',  # 404 — feed discontinuado
    # 'https://www.milenio.com/rss',             # 404 — feed discontinuado
    'https://www.excelsior.com.mx/rss/nacional',
    # 'https://www.reporteindigo.com/feed/',     # 403 — bloqueado
    'https://piedepagina.mx/feed/',
    'https://www.contralinea.com.mx/feed/',
    # 'https://www.sdpnoticias.com/feed',        # 404 — feed discontinuado
    # 'https://www.debate.com.mx/rss/rss.xml',   # 403/404 — feed discontinuado
    'https://www.razon.com.mx/feed/',
    # 'https://www.elheraldodemexico.com/rss.xml', # 404 — feed discontinuado
    'https://www.informador.mx/rss/ultimas-noticias.xml',
    # 'https://www.zocalo.com.mx/rss.xml',       # 404 — feed discontinuado
    'https://www.lajornadadeoriente.com.mx/feed/',
    # ── Medios especializados en género y DDHH ──────────────
    'https://cimacnoticias.com.mx/feed/',
    'https://luchadoras.mx/feed/',
    'https://www.eleconomista.com.mx/rss/',
    'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/mexico/portada',
    'https://feeds.bbci.co.uk/mundo/rss.xml',
    # ── Medios estatales / regionales ───────────────────────
    'https://www.elsoldetoluca.com.mx/rss.xml',
    'https://www.elsoldepuebla.com.mx/rss.xml',
    'https://www.diariodexalapa.com.mx/rss.xml',
    'https://www.noroeste.com.mx/rss/portada.xml',
    # ── Google News queries (feminicidio + NNA) — SOLO MÉXICO ─
    # Todos los queries incluyen "México" explícito Y parámetros de geo:
    # hl=es-419 (español latinoamericano), gl=MX (México), ceid=MX:es-419
    # + "location:México" en el query para forzar noticias del país.
    'https://news.google.com/rss/search?q=feminicidio+M%C3%A9xico+location%3AM%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+hijos+hu%C3%A9rfanos+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+ni%C3%B1os+ni%C3%B1as+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=orfandad+feminicidio+menores+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=%22v%C3%ADctimas+indirectas%22+feminicidio+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+menores+hu%C3%A9rfanos+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    # ── Google News queries adicionales (v5.0 — Mexico-explicit) ──
    'https://news.google.com/rss/search?q=feminicidio+hijos+menores+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=%22violencia+feminicida%22+ni%C3%B1os+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=asesinato+mujer+hijos+quedaron+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=%22alerta+de+g%C3%A9nero%22+menores+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=orfandad+violencia+genero+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=DIF+custodia+feminicidio+hijos+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=%22violencia+contra+la+mujer%22+menores+hu%C3%A9rfanos+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+NNA+victimas+indirectas+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419',
    # ── Queries por estado/ciudad clave de México ───────────
    'https://news.google.com/rss/search?q=feminicidio+CDMX+hijos+menores&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+Jalisco+NNA+hu%C3%A9rfanos&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+Estado+de+M%C3%A9xico+menores&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+Veracruz+hijos&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+Chihuahua+menores&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+Nuevo+Le%C3%B3n+ni%C3%B1os&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+Guerrero+NNA+hu%C3%A9rfanos&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+Puebla+menores+hijos&hl=es-419&gl=MX&ceid=MX:es-419',
    # ── Queries relacionados a Facebook y redes sociales ────
    'https://news.google.com/rss/search?q=feminicidio+mexico+deja+ni%C3%B1o+facebook&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=feminicidio+orfandad+facebook+mexico&hl=es-419&gl=MX&ceid=MX:es-419',
    'https://news.google.com/rss/search?q=%22feminicidio%22+%22redes+sociales%22+hijos+mexico&hl=es-419&gl=MX&ceid=MX:es-419',
]

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

class Config:
    """Configuración base para la aplicación Flask."""

    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()

    # --- PostgreSQL ---
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
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 5,
        'max_overflow': 10,
    }

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