# config.py
# -*- coding: utf-8 -*-
"""
Configuración centralizada del Sistema NNA
Trabajo Terminal 1 - ESCOM IPN
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
    
    # === LA JORNADA (múltiples secciones para más cobertura) ===
    'https://www.jornada.com.mx/rss/estados.xml',      # La Jornada - Estados (casos locales)
    'https://www.jornada.com.mx/rss/politica.xml',     # La Jornada - Política
    'https://www.jornada.com.mx/rss/edicion.xml',      # La Jornada - Edición completa
    'https://www.jornada.com.mx/rss/sociedad.xml',     # La Jornada - Sociedad
    
    # === MEDIOS GENERALISTAS CON COBERTURA DE FEMINICIDIOS ===
    'https://aristeguinoticias.com/feed/',  # Aristegui Noticias (buena cobertura)
    'https://www.sinembargo.mx/feed/',      # Sin Embargo (cobertura social)
    
    # === MEDIOS NACIONALES ADICIONALES ===
    'https://www.excelsior.com.mx/rss.xml',            # Excélsior - General
    
    # === MEDIOS REGIONALES (más cobertura local) ===
    'https://www.reforma.com/rss/portada.xml',         # Reforma - Portada
    
    # ELIMINADOS (dan error 404):
    # 'https://www.animalpolitico.com/category/seguridad/feed/',  # 404
    # 'https://www.proceso.com.mx/seccion/nacional/feed',  # 404
    # 'https://www.milenio.com/rss/policia',  # 404
    # 'https://www.eluniversal.com.mx/rss/metropoli.xml',  # 404
    # 'https://www.milenio.com/rss/edo-de-mexico',  # 404
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

# TF-IDF Vectorization - Optimizado para dataset grande (500-1000 noticias)
# Stopwords personalizadas para español mexicano
CUSTOM_STOPWORDS = [
    'del', 'los', 'las', 'una', 'sus', 'al', 'el', 'la', 'de', 'en', 
    'que', 'por', 'con', 'para', 'un', 'lo', 'como', 'se', 'su',
    'más', 'pero', 'si', 'no', 'o', 'este', 'esta', 'estos', 'estas',
    'ese', 'esa', 'esos', 'esas', 'mi', 'tu', 'fue', 'ser', 'ha',
    'han', 'son', 'está', 'están', 'sobre', 'entre', 'sin', 'muy',
    'ya', 'también', 'hasta', 'desde', 'tras', 'así', 'año', 'años'
]

TFIDF_CONFIG = {
    'max_features': 3000,      # ← AUMENTADO: 3000 features para dataset grande
    'min_df': 2,               # ← Palabra debe aparecer en al menos 2 documentos
    'max_df': 0.85,            # Frecuencia máxima (85% de documentos)
    'ngram_range': (1, 2),     # Unigramas y bigramas (captura contexto)
    'lowercase': True,
    'strip_accents': None,     # Preservar acentos para español
    'stop_words': None         # ← Se aplicarán stopwords personalizadas en el código
}

# LDA Topic Modeling - Optimizado para dataset grande
LDA_CONFIG = {
    'n_components': 8,         # ← AUMENTADO de 4 a 8 (más tópicos para +500 docs)
    'random_state': 42,
    'max_iter': 50,            # ← AUMENTADO: más iteraciones para convergencia
    'learning_method': 'online',
    'learning_offset': 50.0,
    'n_jobs': -1               # Usar todos los cores disponibles
}

# DBSCAN Clustering - Optimizado para dataset mediano/pequeño
DBSCAN_CONFIG = {
    'eps': 0.80,               # ← MUY PERMISIVO: 0.80 = similitud ~20% (agrupa casos relacionados)
    'min_samples': 2,          # ← Mínimo 2 (permite clusters pequeños, detecta duplicados)
    'metric': 'cosine',        # Métrica de similitud para texto
    'n_jobs': -1               # Usar todos los cores
}

# Pipeline simplificado vs completo
PIPELINE_SIMPLE = False  # ← CAMBIADO: False = Pipeline ML completo (TF-IDF + LDA + DBSCAN)
                         # True = Solo Recolección + Detector (rápido pero sin ML)

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
    # Query mejorado con operadores booleanos para mayor cobertura
    'query': '(feminicidio OR "violencia de género" OR "asesinato mujer" OR "matan mujer") AND (hijos OR huérfanos OR menores OR niños OR "quedan solos") AND méxico',
    'max_results': 150,        # ← AUMENTADO: 150 resultados para más cobertura
    'language': 'es-MX',
    'country': 'MX',
    'period': '7d'             # últimos 7 días
}

# ============================================================================
# CONFIGURACIÓN DE SCRAPING HISTÓRICO (Para ML robusto)
# ============================================================================

HISTORICAL_SCRAPING_CONFIG = {
    # Recolectar noticias de los últimos meses para tener dataset grande (400+ noticias)
    'enabled': True,                    # Habilitar scraping histórico
    'months_back': 6,                   # ← AUMENTADO: 6 meses (más noticias históricas)
    'queries': [
        'feminicidio hijos méxico',
        'feminicidio huérfanos méxico',
        'asesinato mujer niños méxico',
        'madre asesinada hijos méxico',
        'violencia género menores méxico',  # ← AGREGADO: query adicional
    ],                                  # ← AUMENTADO: 5 queries
    'max_results_per_query': 50,        # ← AUMENTADO: 50 resultados por query (5×50=250)
    'min_delay_seconds': 10,            # ← AUMENTADO: 10 segundos (evitar 429)
    'max_delay_seconds': 20,            # ← AUMENTADO: 20 segundos (más conservador)
}

# Objetivo mejorado: Recolectar 400-600 noticias para ML robusto
# RSS (~100-150) + Google News reciente (~150) + Histórico (~250-300) = 500-600 noticias
# Tiempo estimado: 15-25 minutos (delays largos para evitar bloqueo HTTP 429)

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