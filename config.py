# config.py

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

#Headers para evitar bloqueos po User-Agents
HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win63; x64)'
    'AppleWebKit/573 (HTML, like Gecko)'
    'Chrome/124.0 Safari/537.36'
}
# Parámetros para los modelos de ML
KMEANS_CLUSTERS = 5
LDA_TOPICS = 6
TFIDF_MAX_FEATURES = 5000