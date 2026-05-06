import os
import json
import logging
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from urllib.parse import quote_plus

from src.collection.scraper import StealthSession

logger = logging.getLogger(__name__)

# Configurar Gemini
GEMINI_API_KEY = "AIzaSyC8Sff-dubqwO2bj-PCohSdVqRvEVFqq4g"
# Usando la nueva librería google-genai con el modelo recomendado actual
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = 'gemini-2.5-flash'

class DeepInvestigator:
    def __init__(self):
        self.session = StealthSession()
        
    def _extract_keywords(self, title: str, content: str) -> str:
        """Usa Gemini para extraer la mejor query de búsqueda para este caso."""
        prompt = f"""
        Actúa como un investigador experto. Necesito buscar más noticias sobre este evento específico en la web.
        Genera UNA SOLA frase de búsqueda (máximo 6 palabras) que sea altamente específica a este evento.
        Debe incluir el nombre de la víctima (si existe) y detalles clave (como "asesinada", "hijos", "empresaria", ubicación).
        
        Título: {title}
        Contenido: {content}
        
        Solo devuelve la frase de búsqueda, sin comillas ni explicaciones.
        """
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            query = response.text.strip().replace('"', '')
            return query
        except Exception as e:
            logger.error(f"Error generando query: {e}")
            # Fallback simple
            words = title.split()
            return " ".join(words[:6])

    def _duckduckgo_search(self, query: str) -> list[str]:
        """Busca en DuckDuckGo y retorna URLs."""
        # v5.2: Intenta con el sitio HTML y Lite de DDG para mayor robustez
        urls = []
        search_urls = [
            f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
            f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
        ]
        
        for search_url in search_urls:
            try:
                logger.info(f"Probando búsqueda en: {search_url}")
                resp = self.session.get(search_url, timeout=15)
                if not resp or resp.status_code != 200: 
                    logger.warning(f"Respuesta fallida de DDG ({search_url}): {resp.status_code if resp else 'No resp'}")
                    continue
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Probar múltiples selectores conocidos de DDG (HTML y Lite)
                # .result__a (Link principal en HTML)
                # .result-link (Link en Lite)
                # .result__url (Link verde en HTML)
                found_links = soup.select('a.result__a, a.result-link, a.result__url')
                
                for a in found_links:
                    href = a.get('href')
                    if not href: continue
                    
                    # Limpiar redirecciones de DDG
                    if 'duckduckgo.com/l/?' in href or 'uddg=' in href:
                        import urllib.parse
                        parsed = urllib.parse.urlparse(href)
                        qs = urllib.parse.parse_qs(parsed.query)
                        if 'uddg' in qs:
                            href = qs['uddg'][0]
                    
                    if href and href.startswith('http') and 'duckduckgo.com' not in href:
                        if href not in urls:
                            urls.append(href)
                
                if urls:
                    logger.info(f"Éxito en {search_url}: {len(urls)} URLs encontradas")
                    break # Si ya encontramos URLs en el primer método, no seguimos
            except Exception as e:
                logger.error(f"Error buscando en {search_url}: {e}")
                
        return urls[:8]  # Retornar un poco más para filtrar después

    def _scrape_content(self, url: str) -> str:
        """Extrae el texto de una URL de forma más limpia."""
        try:
            resp = self.session.get(url, timeout=15)
            if not resp or resp.status_code != 200: 
                logger.warning(f"No se pudo acceder a {url}: {resp.status_code if resp else 'Sin respuesta'}")
                return ""
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Limpieza profunda de ruido HTML
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'iframe', 'button', 'noscript']):
                tag.decompose()
                
            # Intentar extraer solo el cuerpo del artículo si existe
            article = soup.find('article') or soup.find('main') or soup
            text = article.get_text(separator=' ', strip=True)
            
            # Limpiar espacios múltiples
            text = " ".join(text.split())
            
            return text[:4000]  # Aumentamos un poco el contexto
        except Exception as e:
            logger.error(f"Error scrapeando {url}: {e}")
            return ""

    def _generate_summary(self, title: str, combined_text: str) -> dict:
        """Usa Gemini para extraer el JSON final estructurado."""
        prompt = f"""
        Actúa como un analista criminal experto en derechos de los niños.
        A continuación tienes fragmentos de varias noticias sobre un mismo evento: "{title}".
        Analiza el texto y extrae la siguiente información en estricto formato JSON.
        El JSON debe tener EXACTAMENTE las siguientes claves:
        - "ubicacion": (string) Ciudad y Estado donde ocurrió.
        - "victimas": (string) Nombre de la víctima o víctimas directas.
        - "ninos_afectados": (integer o string) Número de niños que quedaron huérfanos o afectados.
        - "edades": (string) Las edades de los niños, si se mencionan.
        - "resumen": (string) Un párrafo (máx 150 palabras) resumiendo cómo ocurrió el evento y la situación de los niños.
        
        Si un dato no se menciona en los textos, pon "No especificado".
        
        TEXTOS RECOPILADOS:
        {combined_text[:15000]}
        
        Devuelve SOLO el JSON válido, sin bloques de código markdown ni texto adicional.
        """
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            # Limpiar posible markdown
            text = response.text.strip()
            if text.startswith('```json'): text = text[7:]
            if text.startswith('```'): text = text[3:]
            if text.endswith('```'): text = text[:-3]
            
            return json.loads(text.strip())
        except Exception as e:
            logger.error(f"Error generando resumen: {e}")
            return {
                "ubicacion": "Error en el análisis",
                "victimas": "Error",
                "ninos_afectados": "Error",
                "edades": "Error",
                "resumen": f"No se pudo generar el resumen estructurado. Error: {e}"
            }

    def investigate(self, title: str, content: str) -> dict:
        """Ejecuta el pipeline de investigación completo."""
        logger.info(f"Iniciando investigación para: {title[:50]}...")
        
        # 1. Generar Query
        query = self._extract_keywords(title, content)
        logger.info(f"Query generada: {query}")
        
        # 2. Buscar URLs
        urls = self._duckduckgo_search(query)
        if not urls:
            urls = self._duckduckgo_search(title[:50]) # Fallback
            
        logger.info(f"URLs encontradas: {len(urls)}")
        
        # 3. Extraer contenido
        combined_text = ""
        fuentes_exitosas = []
        for u in urls:
            text = self._scrape_content(u)
            if len(text) > 200:
                combined_text += f"\n--- FUENTE: {u} ---\n{text}\n"
                fuentes_exitosas.append(u)
                
        if not combined_text:
            logger.warning(f"No se pudieron obtener URLs mediante scraping manual para: {query}. Intentando con búsqueda nativa de Gemini...")
            try:
                res = self._investigate_with_gemini_search(title, query)
                logger.info("Investigación nativa de Gemini completada.")
                return res
            except Exception as e:
                logger.error(f"Fallo crítico en _investigate_with_gemini_search: {e}")
                return {
                    "error": True,
                    "mensaje": f"Error al intentar búsqueda nativa: {e}"
                }
            
        # 4. Generar resumen
        resultado = self._generate_summary(title, combined_text)
        resultado["fuentes"] = fuentes_exitosas
        resultado["query_usada"] = query
        
        return resultado

    def investigate_url(self, url: str) -> dict:
        """Extrae el contenido de una URL e investiga el caso."""
        logger.info(f"Identificando caso desde URL: {url}")
        content = self._scrape_content(url)
        if not content or len(content) < 200:
            return {
                "error": True,
                "mensaje": "No se pudo extraer suficiente contenido de la URL proporcionada. Verifique que el enlace sea público y contenga texto."
            }
            
        # Intentar extraer el título de los primeros caracteres
        prompt = f"""Analiza este fragmento de noticia y genera un título corto (máx 10 palabras).
        Si el texto parece ser un error de acceso, aviso de cookies o no es una noticia, devuelve 'NOTICIA_INVALIDA'.
        
        TEXTO: {content[:2000]}"""
        
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            title = response.text.strip().replace('"', '')
            
            if "NOTICIA_INVALIDA" in title or len(title) < 5:
                return {
                    "error": True,
                    "mensaje": "El contenido extraído de la URL no parece ser una noticia válida (posible bloqueo de sitio)."
                }
        except Exception as e:
            logger.error(f"Error generando título: {e}")
            title = "Noticia externa"
            
        return self.investigate(title, content)

    def _investigate_with_gemini_search(self, title: str, query: str) -> dict:
        """Usa el buscador nativo de Gemini como último recurso si el scraper falla."""
        
        prompt = f"""
        Realiza una investigación profunda en la web sobre este evento: "{title}".
        Usa la siguiente frase de búsqueda para encontrar detalles: "{query}".
        
        Necesito un informe estructurado en JSON con:
        - "ubicacion": Ciudad y Estado.
        - "victimas": Nombres de víctimas directas.
        - "ninos_afectados": Número de niños huérfanos o afectados.
        - "edades": Edades de los niños.
        - "resumen": Un párrafo detallado sobre el evento y la situación de los menores.
        - "fuentes": Una lista de las URLs que consultaste.
        
        Devuelve SOLO el JSON.
        """
        
        try:
            # v5.3: Corregido según la última especificación de google-genai
            # Usar GoogleSearch() en lugar de GoogleSearchRetrieval()
            search_tool = types.Tool(google_search=types.GoogleSearch())
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(tools=[search_tool])
            )
            
            text = response.text.strip()
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            
            res = json.loads(text)
            res["metodo"] = "gemini_native_search"
            res["query_usada"] = query
            return res
        except Exception as e:
            logger.error(f"Error en investigación nativa de Gemini: {e}")
            return {
                "error": True,
                "mensaje": f"No se pudo extraer contenido de la web ni mediante scraping ni mediante IA. Detalle: {e}"
            }
