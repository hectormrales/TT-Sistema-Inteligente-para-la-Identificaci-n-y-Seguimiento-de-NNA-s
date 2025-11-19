# config.py
# -*- coding: utf-8 -*-
"""
Configuración centralizada del Sistema NNA
Trabajo Terminal 1 - ESIME Zacatenco IPN
"""

import os
from pathlib import Path

# ============================================================================
# CONFIGURACIÓN DE DIRECTORIOS
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
LOGS_DIR = BASE_DIR / 'logs'

# Crear directorios si no existen
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Archivos de datos
DATA_PATH = str(DATA_DIR / 'noticias.csv')
ANALYZED_DATA_PATH = str(DATA_DIR / 'noticias_analyzed_simplified.csv')
SYNONYM_DICT_PATH = str(DATA_DIR / 'synonym_dictionary.json')
CLUSTERS_INFO_PATH = str(DATA_DIR / 'clusters_info.csv')

# ============================================================================
# FUENTES RSS - MEDIOS ESPECIALIZADOS EN GÉNERO Y FEMINICIDIOS
# ============================================================================

RSS_FEEDS = [
    # === MEDIOS ESPECIALIZADOS EN GÉNERO Y FEMINICIDIOS ===
    'https://cimacnoticias.com.mx/feed/',  # CIMAC - Comunicación e Información de la Mujer
    'https://www.semmexico.mx/feed/',      # SEM México - Periodismo con perspectiva de género
    
    # === SECCIONES DE SEGURIDAD Y ESTADOS (incluyen feminicidios) ===
    'https://www.jornada.com.mx/rss/estados.xml',      # La Jornada - Estados (casos locales)
    # 'https://www.animalpolitico.com/category/seguridad/feed/',  # DESHABILITADO - 404 Error
    # 'https://www.proceso.com.mx/seccion/nacional/feed',  # DESHABILITADO - 404 Error
    
    # === MEDIOS GENERALISTAS CON COBERTURA DE FEMINICIDIOS ===
    'https://aristeguinoticias.com/feed/',  # Aristegui Noticias (buena cobertura)
    'https://www.sinembargo.mx/feed/',      # Sin Embargo (cobertura social)
    
    # === MEDIOS ADICIONALES ===
    'https://www.jornada.com.mx/rss/politica.xml',  # La Jornada - Política
    'https://www.jornada.com.mx/rss/edicion.xml',   # La Jornada - Edición completa
    'https://www.eluniversal.com.mx/rss/metropoli.xml',  # El Universal - Metrópoli (CDMX)
    
    # === MEDIOS LOCALES (Estado de México - zona con más feminicidios) ===
    'https://www.milenio.com/rss/edo-de-mexico',  # Milenio - Edomex
]

# ============================================================================
# CONFIGURACIÓN HTTP
# ============================================================================

HTTP_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    )
}

HTTP_TIMEOUT = 15  # segundos
MAX_RETRIES = 3

# ============================================================================
# PARÁMETROS DE MACHINE LEARNING
# ============================================================================

# NOTA IMPORTANTE: Los pasos de ML (TF-IDF, LDA, DBSCAN) solo son útiles con
# cientos/miles de noticias. Con <100 noticias, el detector es suficiente.

# TF-IDF Vectorization (Solo necesario si quieres similitud o temas)
TFIDF_CONFIG = {
    'max_features': 1500,      # Reducido de 3000 (más eficiente para pocos docs)
    'min_df': 1,               # Frecuencia mínima (permite palabras únicas)
    'max_df': 0.85,            # Frecuencia máxima (85% de documentos)
    'ngram_range': (1, 2),     # Unigramas y bigramas
    'lowercase': True,
    'strip_accents': None,     # Preservar acentos para español
    'stop_words': 'spanish'    # ← AGREGADO: Elimina palabras comunes (de, la, el, etc.)
}

# LDA Topic Modeling (Solo útil con >200 noticias objetivo)
LDA_CONFIG = {
    'n_components': 4,         # Reducido de 6 (mejor para pocos docs)
    'random_state': 42,
    'max_iter': 30,            # Aumentado de 20 (mejor convergencia)
    'learning_method': 'online',
    'learning_offset': 50.0
}

# DBSCAN Clustering (Deshabilitado por defecto - no funciona con pocos docs)
DBSCAN_CONFIG = {
    'eps': 0.75,               # Aumentado de 0.6 (más permisivo)
    'min_samples': 2,          # Mínimo de noticias por cluster
    'metric': 'cosine',        # Métrica de similitud
    'n_jobs': -1               # Usar todos los cores
}

# Pipeline simplificado (recomendado para producción)
PIPELINE_SIMPLE = True  # Si True, solo usa Recolección + Detector

# K-Means Clustering (Legacy - para comparación)
KMEANS_CONFIG = {
    'n_clusters': 5,
    'random_state': 42,
    'n_init': 10
}

# ============================================================================
# CONFIGURACIÓN DE GOOGLE NEWS
# ============================================================================

GOOGLE_NEWS_CONFIG = {
    # Query mejorado con operadores booleanos
    'query': '(feminicidio OR "violencia de género" OR "asesinato mujer") AND (hijos OR huérfanos OR menores OR niños) AND méxico',
    'max_results': 50,         # Aumentado de 30 (más noticias)
    'language': 'es-MX',
    'country': 'MX'
}

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(LOGS_DIR / 'sistema_nna.log'),
            'formatter': 'default',
            'encoding': 'utf-8'
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['file', 'console']
    }
}

# ============================================================================
# CONFIGURACIÓN DEL DETECTOR DE FEMINICIDIOS
# ============================================================================

# Umbrales de confianza
CONFIDENCE_THRESHOLDS = {
    'ALTA': 0.70,      # >= 70% confianza
    'MEDIA': 0.40,     # >= 40% confianza
    'BAJA': 0.20,      # >= 20% confianza
    'IRRELEVANTE': 0   # < 20% confianza
}

# ============================================================================
# VARIABLES DE ENTORNO (Opcional - para deployment)
# ============================================================================

# Permitir override con variables de entorno
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

# ============================================================================
# METADATOS DEL SISTEMA
# ============================================================================

SYSTEM_VERSION = '2.0.0'
SYSTEM_NAME = 'Sistema Inteligente NNA'
INSTITUTION = 'ESIME Zacatenco - IPN'
PROJECT_TYPE = 'Trabajo Terminal 1'