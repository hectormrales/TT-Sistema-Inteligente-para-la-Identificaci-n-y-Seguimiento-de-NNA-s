# -*- coding: utf-8 -*-
"""
Scraper histórico para buscar noticias de feminicidios específicamente.
Complementa el RSS scraper buscando en archivos y búsquedas de sitios.

MEJORA PARA TITULACIÓN: Recolecta noticias de los últimos 6 meses
para tener dataset robusto (500-1000 noticias) necesario para ML efectivo.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import re
import logging
from typing import List, Dict
from .feminicide_detector import FeminicideDetector

# Importar configuración
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import config

logger = logging.getLogger(__name__)


def collect_historical_news(months_back: int = None, max_total: int = None) -> List[Dict]:
    """
    Función principal para recolección histórica masiva.
    
    Esta función recolecta noticias de los últimos meses usando Google News
    con múltiples queries para maximizar cobertura.
    
    Args:
        months_back: Meses hacia atrás (default: config.HISTORICAL_SCRAPING_CONFIG)
        max_total: Máximo total de noticias (default: config)
        
    Returns:
        Lista de diccionarios con noticias
        
    Ejemplo:
        # Recolectar últimos 6 meses
        noticias = collect_historical_news(months_back=6, max_total=500)
        print(f"Recolectadas: {len(noticias)} noticias históricas")
    """
    hist_config = getattr(config, 'HISTORICAL_SCRAPING_CONFIG', {})
    
    if not hist_config.get('enabled', False):
        logger.info("Scraping histórico deshabilitado en config")
        return []
    
    months_back = months_back or hist_config.get('months_back', 6)
    max_per_query = hist_config.get('max_results_per_query', 50)
    queries = hist_config.get('queries', ['feminicidio hijos méxico'])
    min_delay = hist_config.get('min_delay_seconds', 2)
    max_delay = hist_config.get('max_delay_seconds', 5)
    
    all_articles = []
    detector = FeminicideDetector()
    
    logger.info(f"Recolectando noticias de últimos {months_back} meses")
    logger.info(f"Queries configuradas: {len(queries)}")
    
    # Dividir tiempo en periodos mensuales
    from dateutil.relativedelta import relativedelta
    end_date = datetime.now()
    
    for month_offset in range(months_back):
        period_end = end_date - relativedelta(months=month_offset)
        period_start = period_end - relativedelta(months=1)
        
        logger.info(f"\nPeriodo: {period_start.strftime('%Y-%m')} ({period_start.strftime('%d/%m')} - {period_end.strftime('%d/%m')})")
        
        for query in queries:
            logger.info(f"  Query: {query[:40]}...")
            
            try:
                # Usar Google News RSS con fecha
                articles = _search_google_news_period(
                    query=query,
                    start_date=period_start,
                    end_date=period_end,
                    max_results=max_per_query,
                    detector=detector
                )
                
                logger.info(f"    → {len(articles)} noticias encontradas")
                all_articles.extend(articles)
                
                # Delay para evitar rate limiting
                import random
                time.sleep(random.uniform(min_delay, max_delay))
                
            except Exception as e:
                logger.error(f"    Error: {e}")
                continue
    
    logger.info(f"\nTotal histórico recolectado: {len(all_articles)} noticias")
    return all_articles


def _search_google_news_period(
    query: str,
    start_date: datetime,
    end_date: datetime,
    max_results: int,
    detector: FeminicideDetector
) -> List[Dict]:
    """
    Busca en Google News para un periodo específico.
    
    Args:
        query: Términos de búsqueda
        start_date: Fecha inicio
        end_date: Fecha fin  
        max_results: Máximo resultados
        detector: Instancia del detector
        
    Returns:
        Lista de artículos detectados
    """
    from GoogleNews import GoogleNews
    
    articles = []
    
    try:
        googlenews = GoogleNews(lang='es', region='MX')
        googlenews.set_time_range(
            start_date.strftime('%m/%d/%Y'),
            end_date.strftime('%m/%d/%Y')
        )
        googlenews.search(query)
        
        results = googlenews.results()[:max_results]
        
        for item in results:
            title = item.get('title', '')
            desc = item.get('desc', '')
            link = item.get('link', '')
            date_str = item.get('date', '')
            
            # Parsear fecha
            try:
                pub_date = datetime.strptime(date_str, '%b %d, %Y') if date_str else end_date
            except:
                pub_date = end_date
            
            # Aplicar detector
            full_text = f"{title} {desc}"
            detection = detector.detect(full_text)
            
            # Solo guardar feminicidios
            if detection['is_feminicide']:
                articles.append({
                    'titulo': title,
                    'contenido': desc,
                    'enlace': link,
                    'fuente': 'Google News (Histórico)',
                    'fecha': pub_date.isoformat(),
                    'cluster': 0,
                    'es_feminicidio': detection['is_feminicide'],
                    'tiene_nna': detection['has_children'],
                    'tiene_huerfanos': detection['has_orphans'],
                    'es_objetivo': detection['is_target_news'],
                    'confianza': detection['confidence'],
                    'prioridad': detection['priority'],
                    'menores_identificados': 'Si' if detection['has_children'] else 'No'
                })
        
        googlenews.clear()
        
    except Exception as e:
        logger.error(f"Error en búsqueda histórica: {e}")
    
    return articles

class HistoricalFeminicideScraper:
    """Scraper especializado para buscar noticias de feminicidios en archivos históricos."""
    
    def __init__(self):
        self.detector = FeminicideDetector()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
    def scrape_cimac_archive(self, days_back=7, max_articles=50):
        """
        Busca en el archivo de CIMAC Noticias (especializado en feminicidios).
        
        Args:
            days_back: Días hacia atrás para buscar
            max_articles: Máximo de artículos a recolectar
        """
        print(f"\n[CIMAC] Buscando noticias de los ultimos {days_back} dias...")
        articles = []
        
        # CIMAC tiene categorías específicas de feminicidios
        categories = [
            'https://cimacnoticias.com.mx/category/feminicidio/',
            'https://cimacnoticias.com.mx/category/violencia-de-genero/',
            'https://cimacnoticias.com.mx/category/derechos-humanos/'
        ]
        
        for category_url in categories:
            try:
                print(f"  Explorando: {category_url}")
                response = requests.get(category_url, headers=self.headers, timeout=15)
                
                if response.status_code != 200:
                    print(f"  Error {response.status_code}")
                    continue
                    
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # CIMAC usa <article> tags
                for article in soup.find_all('article', limit=20):
                    # Extraer título
                    title_elem = article.find(['h2', 'h3'], class_=re.compile('entry-title|post-title'))
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # Extraer link
                    link_elem = title_elem.find('a') or article.find('a')
                    link = link_elem['href'] if link_elem and link_elem.get('href') else ''
                    
                    # Extraer excerpt/descripción
                    excerpt_elem = article.find(['div', 'p'], class_=re.compile('excerpt|entry-summary|entry-content'))
                    excerpt = excerpt_elem.get_text(" ", strip=True)[:500] if excerpt_elem else ''
                    
                    # Extraer fecha
                    date_elem = article.find('time')
                    date_str = date_elem['datetime'] if date_elem and date_elem.get('datetime') else None
                    
                    try:
                        pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')) if date_str else datetime.now()
                    except:
                        pub_date = datetime.now()
                    
                    # Filtrar por fecha
                    if (datetime.now() - pub_date).days > days_back:
                        continue
                    
                    # Aplicar detector
                    full_text = f"{title} {excerpt}"
                    detection = self.detector.detect(full_text)
                    
                    # Solo guardar si es objetivo o al menos feminicidio
                    if detection['is_feminicide']:
                        articles.append({
                            'titulo': title,
                            'contenido': excerpt,
                            'enlace': link,
                            'fuente': category_url,
                            'fecha': pub_date.isoformat(),
                            'es_feminicidio': detection['is_feminicide'],
                            'tiene_nna': detection['has_children'],
                            'tiene_huerfanos': detection['has_orphans'],
                            'es_objetivo': detection['is_target_news'],
                            'confianza': detection['confidence'],
                            'prioridad': detection['priority'],
                            'menores_identificados': 'Si' if detection['has_children'] else 'No'
                        })
                        
                        status = "OBJETIVO" if detection['is_target_news'] else "FEMINICIDIO"
                        print(f"    [{status}] {title[:60]}...")
                        
                        if len(articles) >= max_articles:
                            break
                
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                print(f"  Error en {category_url}: {str(e)}")
                continue
        
        print(f"[CIMAC] Recolectadas: {len(articles)} noticias de feminicidios")
        return articles
    
    def scrape_sem_mexico_search(self, query="feminicidio huerfanos", max_articles=30):
        """
        Busca en SEM México usando su buscador interno.
        
        Args:
            query: Términos de búsqueda
            max_articles: Máximo de artículos
        """
        print(f"\n[SEM Mexico] Buscando: '{query}'...")
        articles = []
        
        try:
            # SEM México tiene buscador
            search_url = f"https://www.semmexico.mx/?s={query.replace(' ', '+')}"
            response = requests.get(search_url, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                print(f"  Error {response.status_code}")
                return articles
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar artículos en resultados
            for article in soup.find_all(['article', 'div'], class_=re.compile('post|entry|result'), limit=30):
                # Extraer título
                title_elem = article.find(['h2', 'h3', 'h4'], class_=re.compile('title|heading'))
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                
                # Extraer link
                link_elem = title_elem.find('a') or article.find('a')
                link = link_elem['href'] if link_elem and link_elem.get('href') else ''
                
                # Extraer descripción
                desc_elem = article.find(['p', 'div'], class_=re.compile('excerpt|summary|description'))
                description = desc_elem.get_text(" ", strip=True)[:500] if desc_elem else ''
                
                # Aplicar detector
                full_text = f"{title} {description}"
                detection = self.detector.detect(full_text)
                
                # Solo guardar si es objetivo o feminicidio
                if detection['is_feminicide']:
                    articles.append({
                        'titulo': title,
                        'contenido': description,
                        'enlace': link,
                        'fuente': search_url,
                        'fecha': datetime.now().isoformat(),
                        'es_feminicidio': detection['is_feminicide'],
                        'tiene_nna': detection['has_children'],
                        'tiene_huerfanos': detection['has_orphans'],
                        'es_objetivo': detection['is_target_news'],
                        'confianza': detection['confidence'],
                        'prioridad': detection['priority'],
                        'menores_identificados': 'Si' if detection['has_children'] else 'No'
                    })
                    
                    status = "OBJETIVO" if detection['is_target_news'] else "FEMINICIDIO"
                    print(f"    [{status}] {title[:60]}...")
                    
                    if len(articles) >= max_articles:
                        break
            
        except Exception as e:
            print(f"  Error en SEM México: {str(e)}")
        
        print(f"[SEM Mexico] Recolectadas: {len(articles)} noticias")
        return articles
    
    def scrape_google_news_search(self, query="feminicidio hijos huerfanos mexico", max_articles=20):
        """
        Busca en Google News (como backup).
        
        Args:
            query: Términos de búsqueda
            max_articles: Máximo de artículos
        """
        print(f"\n[Google News] Buscando: '{query}'...")
        articles = []
        
        try:
            # Google News RSS search
            search_url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=es-MX&gl=MX&ceid=MX:es-419"
            
            response = requests.get(search_url, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                print(f"  Error {response.status_code}")
                return articles
            
            soup = BeautifulSoup(response.content, 'xml')
            
            for item in soup.find_all('item', limit=max_articles):
                title_elem = item.find('title')
                link_elem = item.find('link')
                desc_elem = item.find('description')
                pub_date_elem = item.find('pubDate')
                
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = link_elem.get_text(strip=True) if link_elem else ''
                description = BeautifulSoup(desc_elem.get_text(), 'html.parser').get_text(" ", strip=True) if desc_elem else ''
                
                # Fecha
                try:
                    from email.utils import parsedate_to_datetime
                    pub_date = parsedate_to_datetime(pub_date_elem.text.strip()) if pub_date_elem else datetime.now()
                except:
                    pub_date = datetime.now()
                
                # Aplicar detector
                full_text = f"{title} {description}"
                detection = self.detector.detect(full_text)
                
                # Solo guardar si es objetivo o feminicidio
                if detection['is_feminicide']:
                    articles.append({
                        'titulo': title,
                        'contenido': description,
                        'enlace': link,
                        'fuente': 'Google News',
                        'fecha': pub_date.isoformat(),
                        'es_feminicidio': detection['is_feminicide'],
                        'tiene_nna': detection['has_children'],
                        'tiene_huerfanos': detection['has_orphans'],
                        'es_objetivo': detection['is_target_news'],
                        'confianza': detection['confidence'],
                        'prioridad': detection['priority'],
                        'menores_identificados': 'Si' if detection['has_children'] else 'No'
                    })
                    
                    status = "OBJETIVO" if detection['is_target_news'] else "FEMINICIDIO"
                    print(f"    [{status}] {title[:60]}...")
            
        except Exception as e:
            print(f"  Error en Google News: {str(e)}")
        
        print(f"[Google News] Recolectadas: {len(articles)} noticias")
        return articles
    
    def collect_all_sources(self, days_back=7):
        """
        Recolecta de todas las fuentes históricas.
        
        Returns:
            DataFrame con todas las noticias de feminicidios encontradas
        """
        all_articles = []
        
        print("="*80)
        print("RECOLECCION HISTORICA DE FEMINICIDIOS")
        print("="*80)
        
        # 1. CIMAC (fuente más confiable)
        cimac_articles = self.scrape_cimac_archive(days_back=days_back, max_articles=30)
        all_articles.extend(cimac_articles)
        
        # 2. SEM México
        sem_articles = self.scrape_sem_mexico_search(query="feminicidio huerfanos", max_articles=20)
        all_articles.extend(sem_articles)
        
        # 3. Google News (backup)
        google_articles = self.scrape_google_news_search(
            query="feminicidio hijos huerfanos mexico",
            max_articles=15
        )
        all_articles.extend(google_articles)
        
        # Convertir a DataFrame y eliminar duplicados
        if all_articles:
            df = pd.DataFrame(all_articles)
            
            # Eliminar duplicados por título (mantener el de mayor confianza)
            df = df.sort_values('confianza', ascending=False)
            df = df.drop_duplicates(subset='titulo', keep='first')
            
            print("\n" + "="*80)
            print(f"RESUMEN FINAL")
            print("="*80)
            print(f"Total recolectadas: {len(df)}")
            print(f"  Feminicidios: {len(df[df['es_feminicidio']])}")
            print(f"  Con NNA: {len(df[df['tiene_nna']])}")
            print(f"  Con huerfanos: {len(df[df['tiene_huerfanos']])}")
            print(f"  OBJETIVO: {len(df[df['es_objetivo']])}")
            print(f"\nPrioridades:")
            print(f"  ALTA: {len(df[df['prioridad'] == 'ALTA'])}")
            print(f"  MEDIA: {len(df[df['prioridad'] == 'MEDIA'])}")
            print(f"  BAJA: {len(df[df['prioridad'] == 'BAJA'])}")
            print("="*80)
            
            return df
        else:
            print("\nNo se encontraron noticias de feminicidios")
            return pd.DataFrame()


# Función de conveniencia para usar directamente
def collect_feminicide_news_historical(days_back=7):
    """
    Función principal para recolectar noticias históricas de feminicidios.
    
    Args:
        days_back: Días hacia atrás para buscar (default: 7)
    
    Returns:
        DataFrame con noticias de feminicidios
    """
    scraper = HistoricalFeminicideScraper()
    return scraper.collect_all_sources(days_back=days_back)
