# config.py

# Fuentes de noticias para la recolección
RSS_FEEDS = [
    'https://www.jornada.com.mx/rss/politica.xml',
    'https://www.proceso.com.mx/feed',
    'https://aristeguinoticias.com/feed/',
]

# Rutas de archivos
DATA_PATH = 'data/noticias.csv'

# Parámetros para los modelos de ML
KMEANS_CLUSTERS = 5
LDA_TOPICS = 4
TFIDF_MAX_FEATURES = 5000