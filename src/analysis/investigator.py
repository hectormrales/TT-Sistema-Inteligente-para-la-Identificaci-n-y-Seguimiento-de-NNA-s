"""
src/analysis/investigator.py
============================
Investigador profundo de casos de NNA en orfandad por feminicidio.

Soporta:
  1. Extracción directa y estructurada en una sola pasada vía `LLMExtractor`
     (Groq / Gemini / OpenRouter / Azure OpenAI + 5 candados).
  2. Búsqueda complementaria en la web (DuckDuckGo / Scrapling / StealthSession)
     cuando se requiere enriquecer un caso con múltiples fuentes periodísticas.
  3. Inicialización perezosa (lazy) de `google-genai` para no fallar al importar
     cuando `GEMINI_API_KEY` no está definida o se usa otro proveedor (ej. Groq).
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
from urllib.parse import quote_plus
from typing import Optional

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from src.collection.scraper import StealthSession, resolve_article_url
except ImportError:
    import requests as _requests
    StealthSession = _requests.Session
    def resolve_article_url(url: str, session=None, timeout: int = 12) -> str:
        return url

from src.analysis.llm_extractor import LLMExtractor

logger = logging.getLogger(__name__)

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Inicialización segura y perezosa del cliente Gemini (mantiene atributo `client`
# a nivel de módulo para compatibilidad total con tests y mocks existentes).
client = None
try:
    from google import genai
    from google.genai import types
    if GEMINI_API_KEY:
        client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    genai = None
    types = None
    logger.debug("google-genai no inicializado al importar: %s", e)


class DeepInvestigator:
    """
    Investigador profundo multi-proveedor para enriquecer expedientes de casos NNA.
    """

    def __init__(self, llm_extractor: Optional[LLMExtractor] = None):
        self.session = StealthSession()
        self.llm_extractor = llm_extractor or LLMExtractor()

    def _extract_keywords(self, title: str, content: str) -> str:
        """Extrae una frase de búsqueda altamente específica para el caso."""
        prompt = f"""
        Actúa como un investigador experto. Necesito buscar más noticias sobre este evento específico en la web.
        Genera UNA SOLA frase de búsqueda (máximo 6 palabras) que sea altamente específica a este evento.
        Debe incluir el nombre de la víctima (si existe) y detalles clave (como "asesinada", "hijos", "empresaria", ubicación).

        Título: {title}
        Contenido: {content[:1500]}

        Solo devuelve la frase de búsqueda, sin comillas ni explicaciones.
        """
        try:
            if client is not None:
                response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
                query = response.text.strip().replace('"', '')
                if query:
                    return query
        except Exception as e:
            logger.warning("Fallo generando query con cliente primario: %s", e)

        # Fallback: primeros términos significativos del título
        words = [w for w in (title or "").split() if len(w) > 2]
        return " ".join(words[:6]) if words else (title or "feminicidio menores")[:50]

    def _duckduckgo_search(self, query: str) -> list[str]:
        """Busca en DuckDuckGo y retorna URLs de noticias relacionadas."""
        urls: list[str] = []

        # HTML y Lite de DuckDuckGo con StealthSession (Scrapling + curl_cffi)
        search_urls = [
            f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl=mx-es",
            f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}&kl=mx-es",
        ]

        for search_url in search_urls:
            try:
                logger.info("Probando búsqueda en: %s", search_url)
                resp = self.session.get(search_url, timeout=15)
                if not resp or resp.status_code != 200:
                    continue

                if BeautifulSoup is not None:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    found_links = soup.select("a.result__a, a.result-link, a.result__url")
                    hrefs = [a.get("href") for a in found_links if a.get("href")]
                else:
                    hrefs = re.findall(r'href=["\'](https?://[^"\']+)["\']', resp.text)

                for href in hrefs:
                    if not href:
                        continue

                    href = resolve_article_url(href, session=None)

                    if href and href.startswith("http") and "duckduckgo.com" not in href:
                        if href not in urls:
                            urls.append(href)

                if urls:
                    break
            except Exception as e:
                logger.error("Error buscando en %s: %s", search_url, e)

        return urls[:8]

    def _scrape_content(self, url: str) -> str:
        """Extrae el texto limpio de una URL periodística (resolviendo redirecciones de Google/Bing)."""
        try:
            target_url = resolve_article_url(url, session=self.session)
            resp = self.session.get(target_url, timeout=15)
            if not resp or resp.status_code != 200:
                logger.warning(
                    "No se pudo acceder a %s: %s",
                    url,
                    resp.status_code if resp else "Sin respuesta",
                )
                return ""

            # Usar trafilatura si está instalada y devuelve buen cuerpo
            try:
                import trafilatura
                extracted = trafilatura.extract(
                    resp.text,
                    include_comments=False,
                    include_tables=False,
                )
                if extracted and len(extracted.strip()) > 200:
                    return " ".join(extracted.split())[:4000]
            except Exception:
                pass

            if BeautifulSoup is not None:
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(
                    ["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "button", "noscript"]
                ):
                    tag.decompose()

                article = soup.find("article") or soup.find("main") or soup
                text = article.get_text(separator=" ", strip=True)
            else:
                cleaned = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", resp.text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<[^>]+>", " ", cleaned)

            text = " ".join(text.split())
            return text[:4000]
        except Exception as e:
            logger.error("Error scrapeando %s: %s", url, e)
            return ""

    def _generate_summary(self, title: str, combined_text: str) -> dict:
        """Extrae el informe JSON estructurado del caso."""
        prompt = f"""
        Actúa como un analista criminal experto en derechos de los niños.
        A continuación tienes fragmentos de varias noticias sobre un mismo evento: "{title}".
        Analiza el texto y extrae la siguiente información en estricto formato JSON.
        El JSON debe tener EXACTAMENTE las siguientes claves:
        - "ubicacion": (string) Ciudad y Estado donde ocurrió.
        - "victimas": (string) Nombre de la víctima o víctimas directas.
        - "ninos_afectados": (integer o string) Número de niños que quedaron huérfanos o afectados.
        - "edades": (string) Las edades de los niños, si se mencionan.
        - "situacion_actual": (string) Situación actual de los niños (ej. "se encuentra en el DIF", "con sus abuelos"). Si no se menciona, pon "No especificada".
        - "medios_contacto": (string) Institución, dependencia gubernamental (ej. DIF municipal, Fiscalía), colectivo, o números de contacto con quien comunicarse para dar seguimiento al caso o ubicar a las víctimas de acuerdo a la ubicación o el texto. Si no se menciona, sugiérelo según la ubicación.
        - "resumen": (string) Un párrafo (máx 150 palabras) resumiendo cómo ocurrió el evento y la situación de los niños.

        TEXTOS RECOPILADOS:
        {combined_text[:15000]}

        Devuelve SOLO el JSON válido, sin bloques de código markdown ni texto adicional.
        """
        if client is not None:
            try:
                response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
                text = response.text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                return json.loads(text.strip())
            except Exception as e:
                logger.error("Error generando resumen con cliente Gemini: %s", e)

        # Fallback: usar LLMExtractor (soporta Groq, OpenRouter, Azure o extracción determinista)
        try:
            analysis = self.llm_extractor.analyze_article(
                title=title,
                content=combined_text[:10000],
            )
            inv = analysis.get("investigacion_json")
            if isinstance(inv, dict) and "ubicacion" in inv:
                return inv
        except Exception as e:
            logger.error("Error en fallback LLMExtractor para resumen: %s", e)

        return {
            "ubicacion": "No especificada",
            "victimas": "No especificada",
            "ninos_afectados": "No especificado",
            "edades": "No especificadas",
            "situacion_actual": "No especificada",
            "medios_contacto": "DIF / Fiscalía Estatal",
            "resumen": f"Resumen preliminar basado en: {title}",
        }

    def investigate(self, title: str, content: str) -> dict:
        """Ejecuta el pipeline de investigación profunda para una noticia."""
        logger.info("Iniciando investigación para: %s...", (title or "")[:50])

        # 1. Generar Query
        query = self._extract_keywords(title, content)
        logger.info("Query generada: %s", query)

        # 2. Buscar URLs
        urls = self._duckduckgo_search(query)
        if not urls:
            urls = self._duckduckgo_search((title or "")[:50])

        logger.info("URLs encontradas: %d", len(urls))

        # 3. Extraer contenido de las URLs encontradas
        combined_text = ""
        fuentes_exitosas: list[str] = []
        for u in urls:
            text = self._scrape_content(u)
            if len(text) > 200:
                combined_text += f"\n--- FUENTE: {u} ---\n{text}\n"
                fuentes_exitosas.append(u)

        if not combined_text:
            logger.warning(
                "No se pudieron obtener URLs mediante scraping manual para: %s. "
                "Intentando con búsqueda nativa o análisis del contenido local...",
                query,
            )
            try:
                res = self._investigate_with_gemini_search(title, query)
                if not res.get("error"):
                    return res
            except Exception as e:
                logger.error("Fallo en _investigate_with_gemini_search: %s", e)

            # Si tenemos contenido local suficiente, extraer expediente directamente con LLMExtractor
            if content and len(content.strip()) >= 80:
                resultado = self._generate_summary(title, f"{title}. {content}")
                resultado["fuentes"] = []
                resultado["query_usada"] = query
                return resultado

            return {
                "error": True,
                "mensaje": "No se pudo extraer contenido adicional de la web.",
            }

        # 4. Generar resumen estructurado combinando el artículo original + fuentes web
        full_context = f"--- NOTICIA BASE: {title} ---\n{content}\n{combined_text}"
        resultado = self._generate_summary(title, full_context)
        resultado["fuentes"] = fuentes_exitosas
        resultado["query_usada"] = query
        return resultado

    def investigate_url(self, url: str) -> dict:
        """Extrae el contenido de una URL externa e investiga el caso."""
        logger.info("Investigando caso desde URL: %s", url)
        content = self._scrape_content(url)
        if not content or len(content) < 200:
            return {
                "error": True,
                "mensaje": (
                    "No se pudo extraer suficiente contenido de la URL proporcionada. "
                    "Verifique que el enlace sea público y contenga texto."
                ),
            }

        prompt = f"""Analiza este fragmento de noticia y genera un título corto (máx 10 palabras).
        Si el texto parece ser un error de acceso, aviso de cookies o no es una noticia, devuelve 'NOTICIA_INVALIDA'.

        TEXTO: {content[:2000]}"""

        title = "Noticia externa"
        if client is not None:
            try:
                response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
                title = response.text.strip().replace('"', '')
                if "NOTICIA_INVALIDA" in title or len(title) < 5:
                    return {
                        "error": True,
                        "mensaje": "El contenido extraído de la URL no parece ser una noticia válida (posible bloqueo de sitio).",
                    }
            except Exception as e:
                logger.error("Error generando título: %s", e)
                title = content[:80].split(".")[0].strip() or "Noticia externa"
        else:
            title = content[:80].split(".")[0].strip() or "Noticia externa"

        res = self.investigate(title, content)
        if isinstance(res, dict) and "error" not in res:
            res.setdefault("titulo", title)
            if url not in res.get("fuentes", []):
                res.setdefault("fuentes", []).insert(0, url)
        return res

    def _investigate_with_gemini_search(self, title: str, query: str) -> dict:
        """Usa el buscador nativo de Gemini como respaldo si está disponible."""
        if client is None or types is None:
            return {
                "error": True,
                "mensaje": "Cliente Gemini nativo no configurado.",
            }

        prompt = f"""
        Realiza una investigación profunda en la web sobre este evento: "{title}".
        Usa la siguiente frase de búsqueda para encontrar detalles: "{query}".

        Necesito un informe estructurado en JSON con:
        - "ubicacion": Ciudad y Estado.
        - "victimas": Nombres de víctimas directas.
        - "ninos_afectados": Número de niños huérfanos o afectados.
        - "edades": Edades de los niños.
        - "situacion_actual": Situación actual de los niños (ej. "se encuentra en el DIF", "con sus abuelos").
        - "medios_contacto": Institución (DIF, Fiscalía), colectivo, o números de contacto sugeridos para dar seguimiento al caso según la ubicación.
        - "resumen": Un párrafo detallado sobre el evento y la situación de los menores.
        - "fuentes": Una lista de las URLs que consultaste.

        Devuelve SOLO el JSON.
        """
        try:
            search_tool = types.Tool(google_search=types.GoogleSearch())
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(tools=[search_tool]),
            )

            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()

            res = json.loads(text)
            res["metodo"] = "gemini_native_search"
            res["query_usada"] = query
            return res
        except Exception as e:
            logger.error("Error en investigación nativa de Gemini: %s", e)
            return {
                "error": True,
                "mensaje": f"No se pudo extraer contenido de la web ni mediante scraping ni mediante IA. Detalle: {e}",
            }
