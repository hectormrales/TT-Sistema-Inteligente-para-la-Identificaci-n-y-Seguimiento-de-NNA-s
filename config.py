# config.py

# Fuentes de noticias para la recolección
# ACTUALIZADAS: Fuentes especializadas en género, feminicidios y violencia contra mujeres
RSS_FEEDS = [
    # === MEDIOS ESPECIALIZADOS EN GÉNERO Y FEMINICIDIOS ===
    'https://cimacnoticias.com.mx/feed/',  # CIMAC - Comunicación e Información de la Mujer
    'https://www.semmexico.mx/feed/',      # SEM México - Periodismo con perspectiva de género
    
    # === SECCIONES DE SEGURIDAD Y ESTADOS (incluyen feminicidios) ===
    'https://www.jornada.com.mx/rss/estados.xml',      # La Jornada - Estados (casos locales)
    'https://www.animalpolitico.com/category/seguridad/feed/',  # Animal Político - Seguridad
    'https://www.proceso.com.mx/seccion/nacional/feed',  # Proceso - Nacional
    
    # === MEDIOS GENERALISTAS CON COBERTURA DE FEMINICIDIOS ===
    'https://aristeguinoticias.com/feed/',  # Aristegui Noticias (buena cobertura)
    'https://www.sinembargo.mx/feed/',      # Sin Embargo (cobertura social)
    
    # === BACKUP: Medio general ===
    'https://www.jornada.com.mx/rss/politica.xml',  # La Jornada - Política (backup)
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