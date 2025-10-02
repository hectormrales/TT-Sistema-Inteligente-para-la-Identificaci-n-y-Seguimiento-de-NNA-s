# src/collection/smart_data_collector.py
"""
Recolector de datos inteligente que respeta robots.txt y optimiza las peticiones
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from email.utils import parsedate_to_datetime
from unicodedata import normalize
import time
import re
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse
import config

class SmartDataCollector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; NNA-Research-Bot/1.0; Educational Research)',
            'Accept': 'application/xml, text/xml, text/html',
            'Accept-Language': 'es-ES,es;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        })
        self.robots_cache = {}
        self.request_delay = 2  # Segundos entre peticiones
        self.max_retries = 3
        
    def check_robots_txt(self, url: str) -> bool:
        """
        Verifica si el sitio permite el web scraping según robots.txt
        """
        try:
            domain = urlparse(url).netloc
            
            if domain in self.robots_cache:
                return self.robots_cache[domain]
            
            rp = RobotFileParser()
            robots_url = f"https://{domain}/robots.txt"
            rp.set_url(robots_url)
            
            try:
                rp.read()
                # Verificar si nuestro User-Agent puede acceder
                can_fetch = rp.can_fetch('*', url) and rp.can_fetch('NNA-Research-Bot', url)
                self.robots_cache[domain] = can_fetch
                
                print(f"robots.txt para {domain}: {'✓ Permitido' if can_fetch else '✗ Bloqueado'}")
                return can_fetch
                
            except Exception as e:
                print(f"No se pudo leer robots.txt de {domain}: {e}")
                # Si no hay robots.txt, asumimos que está permitido pero con precaución
                self.robots_cache[domain] = True
                return True
                
        except Exception as e:
            print(f"Error verificando robots.txt: {e}")
            return True  # Beneficio de la duda
    
    def get_crawl_delay(self, url: str) -> float:
        """
        Obtiene el delay recomendado para el crawling desde robots.txt
        """
        try:
            domain = urlparse(url).netlext
            rp = RobotFileParser()
            robots_url = f"https://{domain}/robots.txt"
            rp.set_url(robots_url)
            rp.read()
            
            # Buscar Crawl-delay específico
            delay = rp.crawl_delay('NNA-Research-Bot') or rp.crawl_delay('*')
            return float(delay) if delay else self.request_delay
            
        except:
            return self.request_delay
    
    def collect_rss_headers_only(self, rss_url: str) -> list:
        """
        Primera fase: Recolecta solo títulos y descripciones de RSS
        """
        if not self.check_robots_txt(rss_url):
            print(f"⚠️ Acceso bloqueado por robots.txt: {rss_url}")
            return []
        
        try:
            print(f"📰 Recolectando encabezados de: {rss_url}")
            
            # Respetar delay de crawling
            delay = self.get_crawl_delay(rss_url)
            time.sleep(delay)
            
            response = self.session.get(rss_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            
            articles_preview = []
            for item in soup.find_all('item'):
                title = item.find('title')
                description = item.find('description')
                link = item.find('link')
                pub_date = item.find('pubDate')
                
                if title and description:
                    # Limpiar descripción de HTML
                    desc_text = BeautifulSoup(description.text, 'html.parser').get_text(" ", strip=True)
                    
                    # Normalizar fecha
                    if pub_date and pub_date.text.strip():
                        try:
                            dt = parsedate_to_datetime(pub_date.text.strip())
                        except Exception:
                            dt = datetime.utcnow()
                    else:
                        dt = datetime.utcnow()
                    
                    preview = {
                        'titulo': title.text.strip(),
                        'descripcion': desc_text[:300],  # Solo primeros 300 caracteres
                        'enlace': link.text.strip() if link else '',
                        'fuente': rss_url,
                        'fecha': dt.isoformat(),
                        'relevancia_nna': self._calculate_nna_relevance(title.text, desc_text),
                        'contenido_completo': None,  # Se llenará en la segunda fase
                        'procesado_completo': False
                    }
                    articles_preview.append(preview)
            
            print(f"✓ Recolectados {len(articles_preview)} encabezados")
            return articles_preview
            
        except Exception as e:
            print(f"❌ Error recolectando encabezados de {rss_url}: {e}")
            return []
    
    def _calculate_nna_relevance(self, title: str, description: str) -> float:
        """
        Calcula la relevancia potencial para casos NNA basado en título y descripción
        """
        text = f"{title} {description}".lower()
        
        # Normalizar texto
        text = normalize('NFKD', text).encode('ASCII', 'ignore').decode('ascii')
        
        # Palabras clave con pesos diferentes
        keywords_high = [
            r'\bhij[oa]s?\b', r'\bmenor(?:es)?(?:\s+de\s+edad)?\b', r'\bniñ[oa]s?\b',
            r'\bhuerfan[oa]s?\b', r'\binfant(?:e|il|es)\b', r'\bfeminicidio\b'
        ]
        
        keywords_medium = [
            r'\badolescentes?\b', r'\bfamilia\b', r'\bviolencia\b', 
            r'\bmataron?\b', r'\basesinat[oa]\b', r'\bmadre\b'
        ]
        
        keywords_low = [
            r'\bmujer\b', r'\bhogar\b', r'\bcasa\b', r'\bpareja\b'
        ]
        
        # Patrones de edad explícita
        age_patterns = [
            r'\b\d{1,2}\s*(?:anos?|mes(?:es)?)\b',
            r'\bde\s+\d{1,2}\s*(?:anos?|mes(?:es)?)\b'
        ]
        
        score = 0.0
        
        # Contar coincidencias con pesos
        for pattern in keywords_high:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            score += matches * 0.4
        
        for pattern in keywords_medium:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            score += matches * 0.2
        
        for pattern in keywords_low:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            score += matches * 0.1
        
        for pattern in age_patterns:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            score += matches * 0.3
        
        # Normalizar score (máximo 1.0)
        return min(score, 1.0)
    
    def filter_relevant_articles(self, articles_preview: list, threshold: float = 0.3) -> list:
        """
        Filtra artículos relevantes basado en el score de relevancia
        """
        relevant = []
        for article in articles_preview:
            if article['relevancia_nna'] >= threshold:
                relevant.append(article)
        
        print(f"🎯 Filtrados {len(relevant)} artículos relevantes de {len(articles_preview)} totales")
        print(f"   Umbral de relevancia: {threshold}")
        
        # Mostrar algunos ejemplos
        if relevant:
            print("\n📋 Ejemplos de artículos relevantes:")
            for i, art in enumerate(relevant[:3]):
                print(f"   {i+1}. {art['titulo'][:60]}... (score: {art['relevancia_nna']:.2f})")
        
        return relevant
    
    def fetch_full_content(self, article: dict) -> dict:
        """
        Segunda fase: Obtiene el contenido completo de artículos relevantes
        """
        if not article['enlace']:
            return article
        
        if not self.check_robots_txt(article['enlace']):
            print(f"⚠️ Acceso bloqueado para: {article['enlace']}")
            return article
        
        try:
            print(f"📄 Descargando contenido completo: {article['titulo'][:50]}...")
            
            # Respetar delay
            delay = self.get_crawl_delay(article['enlace'])
            time.sleep(delay)
            
            response = self.session.get(article['enlace'], timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Intentar extraer el contenido principal
            content = self._extract_main_content(soup)
            
            article['contenido_completo'] = content
            article['procesado_completo'] = True
            
            return article
            
        except Exception as e:
            print(f"❌ Error descargando {article['enlace']}: {e}")
            # Usar la descripción como contenido si falla la descarga
            article['contenido_completo'] = article['descripcion']
            article['procesado_completo'] = False
            return article
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """
        Extrae el contenido principal del artículo
        """
        # Remover elementos innecesarios
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "advertisement"]):
            tag.decompose()
        
        # Buscar contenido principal con diferentes selectores
        selectors = [
            'article',
            '.entry-content',
            '.post-content', 
            '.article-content',
            '.content',
            'main',
            '.main-content',
            '#content'
        ]
        
        for selector in selectors:
            content_element = soup.select_one(selector)
            if content_element:
                return content_element.get_text(" ", strip=True)
        
        # Fallback: usar todo el body
        body = soup.find('body')
        if body:
            return body.get_text(" ", strip=True)
        
        return soup.get_text(" ", strip=True)
    
    def collect_smart_news(self, rss_feeds: list, relevance_threshold: float = 0.3) -> pd.DataFrame:
        """
        Proceso completo de recolección inteligente de noticias
        """
        print("🤖 Iniciando recolección inteligente de noticias...")
        print(f"📊 Fuentes a procesar: {len(rss_feeds)}")
        print(f"🎯 Umbral de relevancia: {relevance_threshold}")
        print("─" * 60)
        
        all_articles = []
        
        # Fase 1: Recolectar solo encabezados
        print("\n🔍 FASE 1: Recolectando encabezados...")
        for rss_url in rss_feeds:
            articles_preview = self.collect_rss_headers_only(rss_url)
            all_articles.extend(articles_preview)
        
        print(f"\n📈 Total de encabezados recolectados: {len(all_articles)}")
        
        # Filtrar artículos relevantes
        print("\n🔬 FASE 2: Filtrando por relevancia...")
        relevant_articles = self.filter_relevant_articles(all_articles, relevance_threshold)
        
        # Fase 3: Descargar contenido completo solo de artículos relevantes
        print(f"\n📚 FASE 3: Descargando {len(relevant_articles)} artículos completos...")
        for i, article in enumerate(relevant_articles):
            print(f"   Progreso: {i+1}/{len(relevant_articles)}")
            self.fetch_full_content(article)
        
        # Agregar artículos no relevantes sin contenido completo
        non_relevant = [art for art in all_articles if art['relevancia_nna'] < relevance_threshold]
        for article in non_relevant:
            article['contenido_completo'] = article['descripcion']  # Usar descripción
            article['procesado_completo'] = False
        
        # Combinar todos los artículos
        final_articles = relevant_articles + non_relevant
        
        # Convertir a DataFrame y normalizar nombres de columnas
        df_articles = pd.DataFrame(final_articles)
        
        # Normalizar nombres de columnas para compatibilidad
        if not df_articles.empty:
            # Crear columna 'contenido' para compatibilidad con el analizador existente
            df_articles['contenido'] = df_articles['contenido_completo'].fillna(df_articles['descripcion'])
            
            # También mantener cluster inicializado
            df_articles['cluster'] = 0
            
            print("\n🔍 FASE 4: Análisis de menciones NNA...")
            df_articles['menores_identificados'] = df_articles.apply(
                lambda row: self._detect_children_mentions_enhanced(
                    row['titulo'], 
                    row['contenido']
                ), axis=1
            )
        
        print("\n✅ Recolección inteligente completada!")
        print(f"📊 Estadísticas finales:")
        print(f"   - Total artículos: {len(df_articles)}")
        print(f"   - Artículos con contenido completo: {sum(df_articles['procesado_completo'])}")
        print(f"   - Menciones NNA detectadas: {sum(df_articles['menores_identificados'] == 'Si')}")
        print(f"   - Tasa de detección NNA: {sum(df_articles['menores_identificados'] == 'Si')/len(df_articles)*100:.1f}%")
        
        return df_articles
    
    def _detect_children_mentions_enhanced(self, title: str, content: str) -> str:
        """
        Detección mejorada de menciones de menores
        """
        text = f"{title} {content}".lower()
        
        # Normalizar texto
        text = normalize('NFKD', text).encode('ASCII', 'ignore').decode('ascii')
        
        # Patrones mejorados
        keywords = [
            r'\bhij[oa]s?\b', r'\bmenor(?:es)?(?:\s+de\s+edad)?\b', r'\bniñ[oa]s?\b',
            r'\badolescentes?\b', r'\bhuerfan[oa]s?\b', r'\binfant(?:e|il|es)\b',
            r'\bbebes?\b', r'\breci[e|e]n\s+nacid[oa]s?\b', r'\bNNA\b',
            r'\bmenores?\s+abandonad[oa]s?\b', r'\bniñ[oa]s?\s+en\s+peligro\b'
        ]
        
        # Patrones de edad explícita
        age_patterns = [
            r'\b\d{1,2}\s*(?:anos?|mes(?:es)?)\s*de\s+edad\b',
            r'\bde\s+\d{1,2}\s*(?:anos?|mes(?:es)?)\b',
            r'\b(?:menor|niñ[oa])\s+de\s+\d{1,2}\b'
        ]
        
        # Patrones contextuales
        context_patterns = [
            r'\bquedaron?\s+huerfan[oa]s?\b',
            r'\bsin\s+(?:madre|padre|padres)\b',
            r'\bhij[oa]s?\s+de\s+(?:la\s+)?victima\b',
            r'\bmenores?\s+afectad[oa]s?\b'
        ]
        
        all_patterns = keywords + age_patterns + context_patterns
        
        for pattern in all_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return 'Si'
        
        return 'No'

# Función de conveniencia para usar en el pipeline existente
def collect_smart_news_data():
    """
    Función de conveniencia para integrar con el sistema existente
    """
    collector = SmartDataCollector()
    return collector.collect_smart_news(config.RSS_FEEDS)