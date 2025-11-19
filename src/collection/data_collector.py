# src/collection/data_collector.py
# -*- coding: utf-8 -*-
"""
Módulo de recolección de noticias desde RSS feeds y Google News.
Implementa detección especializada de feminicidios con NNA.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from email.utils import parsedate_to_datetime
from unicodedata import normalize
from typing import List, Dict, Optional
import logging

import config
from .feminicide_detector import FeminicideDetector

# Configurar logger
logger = logging.getLogger(__name__)


def collect_news_from_rss(rss_url: str, max_retries: int = 3) -> List[Dict]:
    """
    Recolecta noticias desde un feed RSS y aplica detección de feminicidios.
    
    Args:
        rss_url: URL del feed RSS
        max_retries: Número máximo de reintentos en caso de error
        
    Returns:
        Lista de artículos detectados como diccionarios
    """
    detector = FeminicideDetector()
    headers = getattr(config, 'HTTP_HEADERS', {})
    timeout = getattr(config, 'HTTP_TIMEOUT', 10)
    
    for attempt in range(max_retries):
        try:
            response = requests.get(rss_url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            articles = []
            
            for item in soup.find_all('item'):
                article = _parse_rss_item(item, rss_url, detector)
                if article:
                    articles.append(article)
            
            return articles
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Intento {attempt + 1}/{max_retries} falló para {rss_url}: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Error recolectando de {rss_url} después de {max_retries} intentos")
                return []
    
    return []


def _parse_rss_item(item: BeautifulSoup, source_url: str, detector: FeminicideDetector) -> Optional[Dict]:
    """
    Parsea un elemento <item> del RSS y aplica detección.
    
    Args:
        item: Elemento BeautifulSoup del RSS
        source_url: URL de la fuente RSS
        detector: Instancia del detector de feminicidios
        
    Returns:
        Diccionario con los datos del artículo o None si no es válido
    """
    title = item.find('title')
    description = item.find('description')
    link = item.find('link')
    pub_date = item.find('pubDate')
    content_encoded = item.find('content:encoded')
    
    if not title or not description:
        return None
    
    # Limpiar HTML de la descripción
    desc_html = content_encoded.text if content_encoded else description.text
    desc_text = BeautifulSoup(desc_html, 'html.parser').get_text(" ", strip=True)
    
    # Normalizar fecha
    if pub_date and pub_date.text.strip():
        try:
            dt = parsedate_to_datetime(pub_date.text.strip())
        except Exception:
            dt = datetime.utcnow()
    else:
        dt = datetime.utcnow()
    
    # Aplicar detector de feminicidios
    full_text = f"{title.text.strip()} {desc_text}"
    detection = detector.detect(full_text)
    
    return {
        'titulo': title.text.strip(),
        'contenido': desc_text,
        'enlace': link.text.strip() if link else '',
        'fuente': source_url,
        'fecha': dt.isoformat(),
        'cluster': 0,
        
        # Campos de detección
        'es_feminicidio': detection['is_feminicide'],
        'tiene_nna': detection['has_children'],
        'tiene_huerfanos': detection['has_orphans'],
        'es_objetivo': detection['is_target_news'],
        'confianza': detection['confidence'],
        'prioridad': detection['priority'],
        
        # Compatibilidad con código anterior
        'menores_identificados': 'Si' if detection['has_children'] else 'No'
    }


def collect_from_google_news(query: Optional[str] = None, max_results: int = 30) -> List[Dict]:
    """
    Recolecta noticias desde Google News RSS con búsqueda específica.
    Complementa los RSS feeds para asegurar cobertura de feminicidios.
    
    Args:
        query: Términos de búsqueda (usa config si no se especifica)
        max_results: Máximo de resultados a procesar
    
    Returns:
        Lista de artículos encontrados
    """
    if query is None:
        google_config = getattr(config, 'GOOGLE_NEWS_CONFIG', {})
        query = google_config.get('query', 'feminicidio hijos huerfanos mexico')
        max_results = google_config.get('max_results', max_results)
    
    detector = FeminicideDetector()
    articles = []
    
    try:
        # Google News RSS search
        search_url = (
            f"https://news.google.com/rss/search?q={query.replace(' ', '+')}"
            f"&hl=es-MX&gl=MX&ceid=MX:es-419"
        )
        
        headers = getattr(config, 'HTTP_HEADERS', {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'xml')
        
        for item in soup.find_all('item')[:max_results]:
            article = _parse_google_news_item(item, detector)
            if article:
                articles.append(article)
        
        logger.info(f"Google News: {len(articles)} artículos recolectados")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error recolectando de Google News: {e}")
    except Exception as e:
        logger.error(f"Error inesperado en Google News: {e}")
    
    return articles


def _parse_google_news_item(item: BeautifulSoup, detector: FeminicideDetector) -> Optional[Dict]:
    """
    Parsea un elemento de Google News RSS.
    
    Args:
        item: Elemento BeautifulSoup del RSS
        detector: Instancia del detector
        
    Returns:
        Diccionario con datos del artículo o None
    """
    title_elem = item.find('title')
    link_elem = item.find('link')
    desc_elem = item.find('description')
    pub_date_elem = item.find('pubDate')
    
    if not title_elem:
        return None
    
    title = title_elem.get_text(strip=True)
    link = link_elem.get_text(strip=True) if link_elem else ''
    
    # Limpiar HTML de la descripción
    description = ''
    if desc_elem:
        desc_html = desc_elem.get_text()
        description = BeautifulSoup(desc_html, 'html.parser').get_text(" ", strip=True)
    
    # Fecha
    try:
        pub_date = parsedate_to_datetime(pub_date_elem.text.strip()) if pub_date_elem else datetime.utcnow()
    except:
        pub_date = datetime.utcnow()
    
    # Aplicar detector
    full_text = f"{title} {description}"
    detection = detector.detect(full_text)
    
    # Solo agregar si es feminicidio (filtrar ruido)
    if not detection['is_feminicide']:
        return None
    
    return {
        'titulo': title,
        'contenido': description,
        'enlace': link,
        'fuente': 'Google News',
        'fecha': pub_date.isoformat(),
        'cluster': 0,
        'es_feminicidio': detection['is_feminicide'],
        'tiene_nna': detection['has_children'],
        'tiene_huerfanos': detection['has_orphans'],
        'es_objetivo': detection['is_target_news'],
        'confianza': detection['confidence'],
        'prioridad': detection['priority'],
        'menores_identificados': 'Si' if detection['has_children'] else 'No'
    }

def collect_all_news(use_google_news: bool = True) -> pd.DataFrame:
    """
    Recolecta noticias de todas las fuentes configuradas.
    
    Args:
        use_google_news: Si es True, también busca en Google News (recomendado)
        
    Returns:
        DataFrame con todas las noticias recolectadas
    """
    all_articles = []
    
    logger.info("="*80)
    logger.info("INICIANDO RECOLECCIÓN DE NOTICIAS CON DETECCIÓN ESPECIALIZADA")
    logger.info("="*80)
    
    # 1. Recolectar de RSS feeds configurados
    rss_feeds = getattr(config, 'RSS_FEEDS', [])
    for rss_feed in rss_feeds:
        logger.info(f"Recolectando de: {rss_feed}")
        articles = collect_news_from_rss(rss_feed)
        logger.info(f"  → {len(articles)} noticias recolectadas")
        all_articles.extend(articles)
    
    # 2. Complementar con Google News
    if use_google_news:
        logger.info("Complementando con Google News (búsqueda específica)...")
        google_articles = collect_from_google_news()
        logger.info(f"  → {len(google_articles)} noticias de feminicidios encontradas")
        all_articles.extend(google_articles)
    
    # Convertir a DataFrame
    df = pd.DataFrame(all_articles)
    
    if len(df) > 0:
        # Eliminar duplicados por título
        initial_count = len(df)
        df = df.drop_duplicates(subset='titulo', keep='first')
        duplicates_removed = initial_count - len(df)
        
        # Estadísticas de recolección
        _log_collection_stats(df, duplicates_removed)
    else:
        logger.warning("No se recolectaron noticias")
    
    return df


def _log_collection_stats(df: pd.DataFrame, duplicates_removed: int):
    """
    Registra estadísticas de la recolección.
    
    Args:
        df: DataFrame con noticias
        duplicates_removed: Número de duplicados eliminados
    """
    total = len(df)
    feminicides = df['es_feminicidio'].sum()
    target_news = df['es_objetivo'].sum()
    high_priority = len(df[df['prioridad'] == 'ALTA'])
    
    logger.info("")
    logger.info("="*80)
    logger.info("RESUMEN DE RECOLECCIÓN")
    logger.info("="*80)
    logger.info(f"Total de noticias únicas: {total}")
    if duplicates_removed > 0:
        logger.info(f"Duplicados eliminados: {duplicates_removed}")
    logger.info(f"Noticias de feminicidio: {feminicides} ({feminicides/total*100:.1f}%)")
    logger.info(f"Noticias OBJETIVO (feminicidio+NNA): {target_news} ({target_news/total*100:.1f}%)")
    logger.info(f"Prioridad ALTA: {high_priority} ({high_priority/total*100:.1f}%)")
    
    # Advertencia si no hay suficientes noticias objetivo
    target_percentage = target_news / total if total > 0 else 0
    if target_percentage < 0.30:
        logger.warning(f"Solo {target_percentage*100:.1f}% son noticias objetivo")
        logger.warning("Se esperaba >30% de noticias sobre feminicidios con NNA")
    else:
        logger.info(f"✓ Porcentaje de noticias objetivo aceptable: {target_percentage*100:.1f}%")


def detect_children_mentions(text: str) -> str:
    """
    Detecta menciones de menores de edad en el texto.
    DEPRECADO: Usar FeminicideDetector.detect() en su lugar.
    
    Args:
        text: Texto a analizar
        
    Returns:
        'Si' o 'No'
    """
    import warnings
    warnings.warn(
        "detect_children_mentions() está deprecado. "
        "Use FeminicideDetector.detect() en su lugar.",
        DeprecationWarning,
        stacklevel=2
    )
    
    if not isinstance(text, str):
        return 'No'
    
    # Normalizar minúsculas y eliminar acentos
    t = normalize('NFKD', text.lower()).encode('ASCII', 'ignore').decode('ascii')
    
    # Palabras clave y patrones comunes
    keywords = [
        r'\bhij[oa]s?\b', r'\bmenor(?:es)?(?:\s+de\s+edad)?\b', r'\bni?[oa]s?\b',
        r'\badolescentes?\b', r'\bhu(erf|erf)an[oa]s?\b', r'\binfant(e|il|es)\b',
        r'\bbebes?\b', r'\breci[e|e]n\s+nacid[oa]s?\b', r'\bNNA\b'
    ]
    
    # Edades explícitas
    age_patterns = [
        r'\b\d{1,2}\s*(anos|mes(?:es)?)\b',
        r'\bde\s+\d{1,2}\s*(anos|mes(?:es)?)\b'
    ]

    import re
    for pat in keywords + age_patterns:
        if re.search(pat, t, re.IGNORECASE):
            return 'Si'
    return 'No'
