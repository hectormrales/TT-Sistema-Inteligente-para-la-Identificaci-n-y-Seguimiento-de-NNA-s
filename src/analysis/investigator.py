import os
import json
import logging
from bs4 import BeautifulSoup
import google.generativeai as genai
from urllib.parse import quote_plus

from src.collection.scraper import StealthSession

logger = logging.getLogger(__name__)

# Configurar Gemini
GEMINI_API_KEY = "AIzaSyC8Sff-dubqwO2bj-PCohSdVqRvEVFqq4g"
genai.configure(api_key=GEMINI_API_KEY)
# Usando gemini-1.5-flash ya que es el modelo estándar rápido (gemini-2.5-flash podría no existir según la versión de la librería)
model = genai.GenerativeModel('gemini-1.5-flash')

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
            response = model.generate_content(prompt)
            query = response.text.strip().replace('"', '')
            return query
        except Exception as e:
            logger.error(f"Error generando query: {e}")
            # Fallback simple
            words = title.split()
            return " ".join(words[:6])

    def _duckduckgo_search(self, query: str) -> list[str]:
        """Busca en DuckDuckGo y retorna URLs."""
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        urls = []
        try:
            resp = self.session.get(url, timeout=15)
            if not resp: return []
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.find_all('a', class_='result__url'):
                href = a.get('href')
                if href and href.startswith('//duckduckgo.com/l/?'):
                    import urllib.parse
                    parsed = urllib.parse.urlparse(href)
                    qs = urllib.parse.parse_qs(parsed.query)
                    if 'uddg' in qs:
                        href = qs['uddg'][0]
                if href and href.startswith('http'):
                    urls.append(href)
        except Exception as e:
            logger.error(f"Error buscando en DDG: {e}")
        return urls[:5]  # Solo las primeras 5 para no exceder tokens

    def _scrape_content(self, url: str) -> str:
        """Extrae el texto de una URL."""
        try:
            resp = self.session.get(url, timeout=10)
            if not resp: return ""
            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()
            text = soup.get_text(separator=' ', strip=True)
            return text[:3000]  # Limitar tamaño
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
            response = model.generate_content(prompt)
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
            return {
                "error": True,
                "mensaje": "No se pudo extraer contenido adicional de la web."
            }
            
        # 4. Generar resumen
        resultado = self._generate_summary(title, combined_text)
        resultado["fuentes"] = fuentes_exitosas
        resultado["query_usada"] = query
        
        return resultado
