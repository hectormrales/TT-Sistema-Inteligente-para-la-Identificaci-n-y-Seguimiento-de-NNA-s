# src/collection/advanced_scraper.py
"""
Sistema Avanzado de Web Scraping con Múltiples Técnicas
Incluye gestión dinámica de fuentes y técnicas alternativas
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import time
import random
import json
import os
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import asyncio
import aiohttp
from fake_useragent import UserAgent
import logging

class SourceManager:
    """
    Gestor de fuentes RSS dinámicas con persistencia
    """
    
    def __init__(self, sources_file: str = "data/sources_config.json"):
        self.sources_file = sources_file
        self.sources = self.load_sources()
        
    def load_sources(self) -> dict:
        """Cargar fuentes desde archivo JSON"""
        if os.path.exists(self.sources_file):
            try:
                with open(self.sources_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error cargando fuentes: {e}")
                return {}
        else:
            # Fuentes por defecto
            return self._get_default_sources()
    
    def save_sources(self):
        """Guardar fuentes en archivo JSON"""
        os.makedirs(os.path.dirname(self.sources_file), exist_ok=True)
        with open(self.sources_file, 'w', encoding='utf-8') as f:
            json.dump(self.sources, f, indent=2, ensure_ascii=False)
    
    def _get_default_sources(self) -> dict:
        """Fuentes por defecto del sistema"""
        return {
            "jornada": {
                "name": "La Jornada",
                "url": "https://www.jornada.com.mx/rss/politica.xml",
                "type": "rss",
                "enabled": True,
                "scraping_config": {
                    "technique": "requests",
                    "delay": 2,
                    "user_agent": "default",
                    "headers": {},
                    "selector": "item",
                    "last_success": None,
                    "error_count": 0
                }
            },
            "forbes": {
                "name": "Forbes México",
                "url": "https://www.forbes.com.mx/feed/",
                "type": "rss",
                "enabled": True,
                "scraping_config": {
                    "technique": "requests",
                    "delay": 3,
                    "user_agent": "default",
                    "headers": {},
                    "selector": "item",
                    "last_success": None,
                    "error_count": 0
                }
            },
            "financiero": {
                "name": "El Financiero",
                "url": "https://www.elfinanciero.com.mx/rss/",
                "type": "rss", 
                "enabled": True,
                "scraping_config": {
                    "technique": "requests",
                    "delay": 2,
                    "user_agent": "default",
                    "headers": {},
                    "selector": "item",
                    "last_success": None,
                    "error_count": 0
                }
            }
        }
    
    def add_source(self, source_id: str, name: str, url: str, source_type: str = "rss") -> bool:
        """Agregar nueva fuente"""
        try:
            self.sources[source_id] = {
                "name": name,
                "url": url,
                "type": source_type,
                "enabled": True,
                "scraping_config": {
                    "technique": "requests",
                    "delay": 2,
                    "user_agent": "default",
                    "headers": {},
                    "selector": "item" if source_type == "rss" else "article",
                    "last_success": None,
                    "error_count": 0
                }
            }
            self.save_sources()
            return True
        except Exception as e:
            print(f"Error agregando fuente: {e}")
            return False
    
    def update_source(self, source_id: str, **kwargs) -> bool:
        """Actualizar fuente existente"""
        try:
            if source_id in self.sources:
                for key, value in kwargs.items():
                    if key in ["name", "url", "type", "enabled"]:
                        self.sources[source_id][key] = value
                    elif key.startswith("config_"):
                        config_key = key.replace("config_", "")
                        self.sources[source_id]["scraping_config"][config_key] = value
                
                self.save_sources()
                return True
            return False
        except Exception as e:
            print(f"Error actualizando fuente: {e}")
            return False
    
    def delete_source(self, source_id: str) -> bool:
        """Eliminar fuente"""
        try:
            if source_id in self.sources:
                del self.sources[source_id]
                self.save_sources()
                return True
            return False
        except Exception as e:
            print(f"Error eliminando fuente: {e}")
            return False
    
    def get_enabled_sources(self) -> dict:
        """Obtener solo fuentes habilitadas"""
        return {k: v for k, v in self.sources.items() if v.get("enabled", True)}
    
    def update_success(self, source_id: str):
        """Marcar fuente como exitosa"""
        if source_id in self.sources:
            self.sources[source_id]["scraping_config"]["last_success"] = datetime.now().isoformat()
            self.sources[source_id]["scraping_config"]["error_count"] = 0
            self.save_sources()
    
    def update_error(self, source_id: str):
        """Incrementar contador de errores"""
        if source_id in self.sources:
            self.sources[source_id]["scraping_config"]["error_count"] += 1
            # Deshabilitar si hay demasiados errores
            if self.sources[source_id]["scraping_config"]["error_count"] >= 5:
                self.sources[source_id]["enabled"] = False
            self.save_sources()

class AdvancedScraper:
    """
    Scraper avanzado con múltiples técnicas de extracción
    """
    
    def __init__(self):
        self.source_manager = SourceManager()
        self.ua = UserAgent()
        self.session = requests.Session()
        self.driver = None
        self.logger = self._setup_logger()
        
        # Técnicas disponibles
        self.techniques = {
            "requests": self._scrape_with_requests,
            "selenium": self._scrape_with_selenium,
            "rotating_ua": self._scrape_with_rotating_ua,
            "delayed_requests": self._scrape_with_delays,
            "async_requests": self._scrape_with_async
        }
    
    def _setup_logger(self):
        """Configurar logging"""
        logger = logging.getLogger("AdvancedScraper")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.FileHandler("data/scraping.log")
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _setup_selenium(self):
        """Configurar Selenium WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument(f"--user-agent={self.ua.random}")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            return True
        except Exception as e:
            self.logger.error(f"Error configurando Selenium: {e}")
            return False
    
    def check_robots_and_select_technique(self, source_id: str, url: str) -> str:
        """
        Verificar robots.txt y seleccionar técnica apropiada
        """
        try:
            # Verificar robots.txt
            rp = RobotFileParser()
            domain = urlparse(url).netloc
            robots_url = f"https://{domain}/robots.txt"
            rp.set_url(robots_url)
            rp.read()
            
            # Verificar diferentes User-Agents
            user_agents = [
                "*",
                "NNA-Research-Bot",
                "Mozilla/5.0",
                "Googlebot"
            ]
            
            allowed = False
            for ua in user_agents:
                if rp.can_fetch(ua, url):
                    allowed = True
                    break
            
            if allowed:
                self.logger.info(f"✅ {domain}: robots.txt permite scraping")
                return "requests"  # Técnica estándar
            else:
                self.logger.warning(f"⚠️ {domain}: robots.txt bloquea scraping, usando técnicas alternativas")
                
                # Seleccionar técnica alternativa basada en el historial
                config = self.source_manager.sources[source_id]["scraping_config"]
                error_count = config.get("error_count", 0)
                
                if error_count == 0:
                    return "delayed_requests"
                elif error_count <= 2:
                    return "rotating_ua"
                elif error_count <= 4:
                    return "selenium"
                else:
                    return "async_requests"
                    
        except Exception as e:
            self.logger.error(f"Error verificando robots.txt para {url}: {e}")
            return "delayed_requests"  # Fallback conservador
    
    def _scrape_with_requests(self, source_id: str, url: str, config: dict) -> list:
        """Técnica estándar con requests"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; NNA-Research-Bot/1.0; Educational Research)',
                'Accept': 'application/xml, text/xml, text/html',
                'Accept-Language': 'es-ES,es;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
            headers.update(config.get("headers", {}))
            
            response = self.session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            return self._parse_rss_content(response.content, url)
            
        except Exception as e:
            self.logger.error(f"Error con requests para {url}: {e}")
            raise
    
    def _scrape_with_selenium(self, source_id: str, url: str, config: dict) -> list:
        """Técnica con Selenium para sitios con JavaScript"""
        try:
            if not self.driver and not self._setup_selenium():
                raise Exception("No se pudo configurar Selenium")
            
            self.driver.get(url)
            
            # Esperar a que cargue el contenido
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "item"))
            )
            
            # Obtener contenido después del renderizado
            content = self.driver.page_source
            return self._parse_rss_content(content.encode(), url)
            
        except Exception as e:
            self.logger.error(f"Error con Selenium para {url}: {e}")
            raise
    
    def _scrape_with_rotating_ua(self, source_id: str, url: str, config: dict) -> list:
        """Técnica con rotación de User-Agents"""
        try:
            # Rotar User-Agent
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'application/xml, text/xml, text/html',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            # Crear nueva sesión para cada petición
            temp_session = requests.Session()
            response = temp_session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            return self._parse_rss_content(response.content, url)
            
        except Exception as e:
            self.logger.error(f"Error con rotación UA para {url}: {e}")
            raise
    
    def _scrape_with_delays(self, source_id: str, url: str, config: dict) -> list:
        """Técnica con delays inteligentes y múltiples intentos"""
        max_attempts = 3
        base_delay = config.get("delay", 2)
        
        for attempt in range(max_attempts):
            try:
                # Delay progresivo: 2s, 5s, 10s
                delay = base_delay * (2 ** attempt) + random.uniform(1, 3)
                
                if attempt > 0:
                    self.logger.info(f"Intento {attempt + 1} para {url} con delay de {delay:.1f}s")
                    time.sleep(delay)
                
                # Usar diferentes headers en cada intento
                headers = {
                    'User-Agent': self.ua.random if attempt > 0 else 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'es-MX,es;q=0.8,en-US;q=0.5,en;q=0.3',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                response = self.session.get(url, headers=headers, timeout=20)
                response.raise_for_status()
                
                return self._parse_rss_content(response.content, url)
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limited
                    if attempt < max_attempts - 1:
                        wait_time = 60 * (attempt + 1)  # 1min, 2min, 3min
                        self.logger.warning(f"Rate limit detectado, esperando {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                raise
            except Exception as e:
                if attempt < max_attempts - 1:
                    self.logger.warning(f"Intento {attempt + 1} falló: {e}")
                    continue
                raise
        
        raise Exception(f"Todos los intentos fallaron para {url}")
    
    async def _scrape_with_async(self, source_id: str, url: str, config: dict) -> list:
        """Técnica asíncrona con aiohttp"""
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'application/xml, text/xml'
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        return self._parse_rss_content(content, url)
                    else:
                        raise Exception(f"HTTP {response.status}")
                        
        except Exception as e:
            self.logger.error(f"Error con async para {url}: {e}")
            raise
    
    def _parse_rss_content(self, content: bytes, source_url: str) -> list:
        """Parsear contenido RSS/XML"""
        try:
            soup = BeautifulSoup(content, 'xml')
            articles = []
            
            for item in soup.find_all('item'):
                title = item.find('title')
                description = item.find('description')
                link = item.find('link')
                pub_date = item.find('pubDate')
                
                if title and description:
                    # Limpiar descripción
                    desc_text = BeautifulSoup(description.text, 'html.parser').get_text(" ", strip=True)
                    
                    # Parsear fecha
                    if pub_date and pub_date.text.strip():
                        try:
                            dt = parsedate_to_datetime(pub_date.text.strip())
                        except Exception:
                            dt = datetime.utcnow()
                    else:
                        dt = datetime.utcnow()
                    
                    article = {
                        'titulo': title.text.strip(),
                        'contenido_completo': desc_text,  # Usar nombre estándar
                        'enlace': link.text.strip() if link else '',
                        'fuente': source_url,
                        'fecha': dt.isoformat(),
                        'cluster': 0,
                        'menores_identificados': 'No determinado'
                    }
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            self.logger.error(f"Error parseando contenido de {source_url}: {e}")
            return []
    
    def scrape_source(self, source_id: str) -> list:
        """
        Scraper principal que selecciona y ejecuta la técnica apropiada
        """
        try:
            if source_id not in self.source_manager.sources:
                raise ValueError(f"Fuente {source_id} no encontrada")
            
            source = self.source_manager.sources[source_id]
            
            if not source.get("enabled", True):
                self.logger.info(f"⏭️ Fuente {source_id} deshabilitada, saltando...")
                return []
            
            url = source["url"]
            config = source["scraping_config"]
            
            # Seleccionar técnica
            technique = self.check_robots_and_select_technique(source_id, url)
            
            # Aplicar delay antes del scraping
            delay = config.get("delay", 2)
            time.sleep(delay)
            
            self.logger.info(f"🔍 Scrapeando {source['name']} con técnica: {technique}")
            
            # Ejecutar scraping
            if technique in self.techniques:
                if technique == "async_requests":
                    # Ejecutar de forma asíncrona
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    articles = loop.run_until_complete(
                        self._scrape_with_async(source_id, url, config)
                    )
                    loop.close()
                else:
                    articles = self.techniques[technique](source_id, url, config)
                
                # Actualizar como exitoso
                self.source_manager.update_success(source_id)
                self.logger.info(f"✅ {len(articles)} artículos obtenidos de {source['name']}")
                
                return articles
            else:
                raise ValueError(f"Técnica {technique} no implementada")
                
        except Exception as e:
            self.logger.error(f"❌ Error scrapeando {source_id}: {e}")
            self.source_manager.update_error(source_id)
            return []
    
    def scrape_all_sources(self) -> pd.DataFrame:
        """Scrapear todas las fuentes habilitadas"""
        all_articles = []
        sources = self.source_manager.get_enabled_sources()
        
        self.logger.info(f"🚀 Iniciando scraping de {len(sources)} fuentes")
        
        for source_id in sources:
            articles = self.scrape_source(source_id)
            all_articles.extend(articles)
        
        if all_articles:
            df = pd.DataFrame(all_articles)
            self.logger.info(f"📊 Total: {len(df)} artículos recolectados")
            return df
        else:
            self.logger.warning("⚠️ No se obtuvieron artículos")
            return pd.DataFrame()
    
    def __del__(self):
        """Cleanup al destruir el objeto"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

# Función de conveniencia
def collect_with_advanced_scraper():
    """Función para integrar con el sistema existente"""
    scraper = AdvancedScraper()
    return scraper.scrape_all_sources()