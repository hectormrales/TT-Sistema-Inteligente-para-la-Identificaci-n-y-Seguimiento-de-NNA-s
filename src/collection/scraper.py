# src/collection/scraper.py — Web Scraper Dinámico con detección de robots.txt
"""
Scraper inteligente que adapta la técnica de extracción según el sitio:

  1. Lee robots.txt para determinar si el scraping está permitido.
  2. Si está bloqueado, aplica técnicas stealth para evadir el bloqueo:
     • Rotación de User-Agents reales (Chrome, Firefox, Edge, Safari)
     • Delays aleatorios entre requests (simula comportamiento humano)
     • Sesiones HTTP con cookies persistentes
     • Headers realistas (Accept, Accept-Language, Referer, etc.)
     • Reintentos con backoff exponencial
  3. Detecta si el sitio ofrece RSS/Atom, sitemap, o solo HTML.
  4. Aplica la técnica apropiada:
     • RSS/Atom  → parse XML (más rápido y respetuoso)
     • Sitemap   → sigue URLs del sitemap.xml
     • HTML      → extrae article/main body
  5. Respeta Crawl-delay y aplica rate-limiting.

v7.0 Mejoras Fase 1:
  - Integración de cloudscraper: bypass de Cloudflare + TLS fingerprint (JA3)
    que coincide con navegadores reales, resolviendo el problema de detección
    donde el User-Agent dice "Chrome" pero el handshake TLS dice "Python".
  - Timing con distribución lognormal: imita el patrón de lectura humana real
    (mayoría de delays medianos + colas largas ocasionales) en lugar de
    distribución uniforme que es trivial de detectar por WAFs.
  - Circuit breaker por dominio: si un dominio falla 3 veces consecutivas,
    se enfría automáticamente por 5 minutos para evitar desperdiciar
    recursos y ser bloqueado más agresivamente.
  - Backoff adaptativo: el intervalo mínimo entre requests se ajusta
    dinámicamente según el historial de éxitos/fallos de cada dominio.

Uso:
    scraper = DynamicScraper()
    result = scraper.probe_url('https://ejemplo.com')
    articles = scraper.scrape_source(url, method='auto')
"""

import re
import time
import math
import random
import hashlib
import logging
import json
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

import config

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cloudscraper: bypass de Cloudflare + TLS fingerprint matching
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# cloudscraper crea sesiones HTTP cuyo handshake TLS (JA3 hash)
# coincide con el de un navegador real, evitando la detección
# que servicios como Cloudflare, Akamai y PerimeterX realizan
# comparando el User-Agent declarado vs el fingerprint TLS real.
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

# Trafilatura: extractor de texto de alta calidad (opcional)
try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

logger = logging.getLogger(__name__)

# ── User-Agents reales para rotación (stealth) ─────────────

BOT_USER_AGENT = 'NNA-Analyzer-Bot/4.0'

# Pool de User-Agents reales de navegadores populares
USER_AGENT_POOL = [
    # Chrome Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    # Chrome macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    # Firefox Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    # Firefox macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0',
    # Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    # Safari macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    # Chrome Linux
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
]


def _random_user_agent() -> str:
    """Selecciona un User-Agent aleatorio del pool."""
    return random.choice(USER_AGENT_POOL)


def _build_stealth_headers(referer: str | None = None) -> dict:
    """
    Construye headers HTTP realistas que imitan un navegador real.
    Incluye Accept, Accept-Language, Accept-Encoding, Referer, etc.
    """
    ua = _random_user_agent()
    headers = {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'DNT': '1',
    }
    if referer:
        headers['Referer'] = referer
        headers['Sec-Fetch-Site'] = 'same-origin'
    return headers


HEADERS = getattr(config, 'HTTP_HEADERS', {
    'User-Agent': _random_user_agent(),
})

# ── Selectores CSS comunes para extraer contenido de artículos ──

ARTICLE_SELECTORS = [
    'article',
    '[role="article"]',
    '.article-body',
    '.article-content',
    '.entry-content',
    '.post-content',
    '.story-body',
    '.nota-body',
    '.content-body',
    '#article-body',
    '.field-name-body',
    '.text-article',
    '.detail-body',
    'main .content',
    '.nota_contenido',
    '.cuerpo-nota',
]

TITLE_SELECTORS = [
    'h1.article-title',
    'h1.entry-title',
    'h1.post-title',
    'h1.nota-title',
    'article h1',
    'main h1',
    '.headline h1',
    'h1',
]

DATE_SELECTORS = [
    'time[datetime]',
    'meta[property="article:published_time"]',
    'meta[name="date"]',
    'meta[name="pubdate"]',
    '.article-date',
    '.entry-date',
    '.post-date',
    '.fecha',
    '.date',
]

# ── Keywords para detectar enlaces a noticias ───────────────

NEWS_PATH_PATTERNS = [
    r'/nota/', r'/noticia/', r'/noticias/',
    r'/articulo/', r'/article/',
    r'/\d{4}/\d{2}/\d{2}/',        # fechas en URL
    r'/\d{4}/\d{2}/',
    r'/seguridad/', r'/justicia/', r'/sociedad/',
    r'/estados/', r'/nacional/',
    r'/policiaca/', r'/sucesos/',
    # Patrones adicionales para más sitios mexicanos
    r'/mexico/', r'/cdmx/', r'/ciudad/',
    r'/crimen/', r'/violencia/', r'/feminicidio/',
    r'/genero/', r'/derechos-humanos/',
    r'/politica/', r'/opinion/', r'/investigacion/',
    r'/reportaje/', r'/especial/',
    r'/local/', r'/regional/', r'/municipios/',
    r'/nota_detalle', r'/contenido/',
    # Patrones genéricos de artículos (slug con guiones)
    r'/[a-z0-9]+-[a-z0-9]+-[a-z0-9]+-',  # URL tipo slug (al-menos-3-palabras)
    r'-\d{8,}',                            # URLs con IDs numéricos largos
    r'/\d{5,}/',                           # URLs con IDs numéricos
]

# ── Paths comunes de feeds RSS para autodescubrimiento ─────

COMMON_RSS_PATHS = [
    '/feed', '/feed/', '/rss', '/rss.xml', '/rss/', '/atom.xml',
    '/feed/rss', '/feed/rss2', '/rss2.xml', '/index.xml',
    '/noticias/feed', '/noticias/rss', '/ultimas-noticias/feed',
    '/feed/atom', '/atom/', '/syndication.axd',
    '/feeds/posts/default', '/feeds/all.atom.xml',
    '/api/rss', '/api/feed',
    '/wp-json/wp/v2/posts?_embed',  # WordPress REST API
]

# ── Firmas de páginas de bloqueo / CAPTCHA ────────────────

BLOCK_SIGNATURES = [
    # Cloudflare
    'cf-browser-verification', 'cloudflare', 'cf_clearance',
    'attention required', 'ddos protection',
    # Generic captcha/block
    'captcha', 'robot', 'are you human', 'access denied',
    'forbidden', '403 forbidden', 'blocked',
    # Paywall
    'suscríbete', 'suscribete', 'subscríbete', 'subscribe to read',
    'inicia sesión para leer', 'contenido exclusivo para suscriptores',
    'iniciar sesi', 'regístrate para',
    # JavaScript challenges
    'enable javascript', 'javascript required', 'habilita javascript',
    'necesitas javascript',
]

# ── Indicadores de sitio JS-heavy (SPA) ──────────────────

JS_HEAVY_INDICATORS = [
    # Frameworks SPA
    'id="root"', 'id="app"', 'ng-app', 'data-reactroot',
    'data-vue-app', '__nuxt', '__next',
    # Contenido vacío → cargado por JS
    '<script>window.__INITIAL_STATE__',
    '<script>window.__NEXT_DATA__',
    'window.APP_STATE', 'window.__state',
]


def _is_block_page(resp: requests.Response) -> bool:
    """
    Detecta si la respuesta es una página de bloqueo, CAPTCHA o paywall.
    Returns True si el contenido parece ser un bloqueo.
    """
    # Código de estado
    if resp.status_code in (403, 429, 503, 401):
        return True

    text_lower = resp.text.lower()[:5000]  # Solo los primeros 5k chars
    for sig in BLOCK_SIGNATURES:
        if sig.lower() in text_lower:
            return True

    # Si el response es extremadamente corto (< 500 chars) → probable bloqueo
    if len(resp.text.strip()) < 300:
        return True

    return False


def _is_js_heavy_page(html: str) -> bool:
    """
    Detecta si una página es una SPA/app JavaScript que no renderiza
    contenido significativo en el HTML inicial.
    """
    # Si el body tiene muy poco texto después de quitar scripts y styles
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup.find_all(['script', 'style', 'noscript']):
            tag.decompose()
        text = soup.get_text(strip=True)
        # Si el texto visible es menor a 200 chars → probablemente JS-heavy
        if len(text) < 200:
            return True
    except Exception:
        pass

    html_lower = html.lower()
    matched = sum(1 for sig in JS_HEAVY_INDICATORS if sig.lower() in html_lower)
    return matched >= 2


def _extract_json_ld(soup: BeautifulSoup) -> dict:
    """
    Extrae metadatos de Schema.org en formato JSON-LD.
    Soporta Article, NewsArticle, BlogPosting.
    Returns dict con: title, content, date (o vacíos).
    """
    result = {'title': '', 'content': '', 'date': ''}

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '{}')
            # Puede ser lista o dict
            if isinstance(data, list):
                items = data
            else:
                items = [data]

            for item in items:
                schema_type = item.get('@type', '')
                if isinstance(schema_type, list):
                    schema_type = schema_type[0] if schema_type else ''

                if schema_type in ('Article', 'NewsArticle', 'BlogPosting',
                                   'ReportageNewsArticle', 'AnalysisNewsArticle'):
                    if not result['title']:
                        result['title'] = item.get('headline', item.get('name', ''))
                    if not result['content']:
                        # articleBody > description
                        result['content'] = item.get(
                            'articleBody', item.get('description', '')
                        )
                    if not result['date']:
                        result['date'] = item.get(
                            'datePublished', item.get('dateModified', '')
                        )
                    if all(result.values()):
                        break
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    return result


def _extract_with_trafilatura(url: str, html: str) -> dict | None:
    """
    Usa trafilatura para extraer texto de artículo de forma robusta.
    Returns dict con title/content/date o None si no está disponible.
    """
    if not HAS_TRAFILATURA:
        return None

    try:
        extracted = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            output_format='json',
        )
        if not extracted:
            return None

        data = json.loads(extracted)
        text = data.get('text', '') or ''
        title = data.get('title', '') or ''
        date = data.get('date', '') or ''

        if len(text) < 80:
            return None

        return {
            'title': title,
            'content': text,
            'date': date,
        }
    except Exception as e:
        logger.debug(f"trafilatura error: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Circuit Breaker por dominio (Fase 1 – v7.0)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Patrón de resiliencia que evita desperdiciar recursos en dominios
# que fallan repetidamente. Después de N fallos consecutivos, el
# circuito se "abre" y rechaza requests por un período de cooldown.
#
# Estados del circuito:
#   CLOSED   → operación normal, se permiten requests.
#   OPEN     → dominio en cooldown, se rechazan requests inmediatamente.
#   HALF-OPEN → después del cooldown, se permite 1 request de prueba.
#               Si tiene éxito → CLOSED; si falla → OPEN de nuevo.
#
# Beneficios:
#   - Evita saturar un dominio que nos está bloqueando (empeora el ban)
#   - Ahorra tiempo de ejecución al no esperar timeouts en dominios muertos
#   - Permite recuperación automática cuando el dominio vuelve a estar disponible


class DomainCircuitBreaker:
    """
    Circuit breaker por dominio para el scraper.

    Implementa el patrón Circuit Breaker (Martin Fowler, 2014) adaptado
    a scraping web. Cada dominio tiene su propio circuito independiente.

    Parámetros configurables:
      - FAILURE_THRESHOLD: fallos consecutivos para abrir el circuito (default: 3)
      - COOLDOWN_SECONDS: tiempo total de cooldown antes de cerrar (default: 300s)
      - HALF_OPEN_AFTER: tiempo antes de permitir un request de prueba (default: 180s)
    """

    FAILURE_THRESHOLD = 3       # Fallos consecutivos para abrir circuito
    COOLDOWN_SECONDS = 300      # 5 minutos de cooldown total
    HALF_OPEN_AFTER = 180       # Intenta 1 request después de 3 minutos

    def __init__(self):
        # Contador de fallos consecutivos por dominio
        self._failures: dict[str, int] = {}
        # Timestamp del último fallo por dominio
        self._last_failure: dict[str, float] = {}
        # Estado del circuito: 'closed', 'open', 'half-open'
        self._state: dict[str, str] = {}

    def can_request(self, domain: str) -> bool:
        """
        Determina si se puede hacer un request a este dominio.

        Returns:
            True si el circuito está 'closed' o 'half-open' (request de prueba).
            False si el circuito está 'open' (en cooldown).
        """
        state = self._state.get(domain, 'closed')

        if state == 'closed':
            return True

        if state == 'open':
            elapsed = time.time() - self._last_failure.get(domain, 0)
            if elapsed >= self.HALF_OPEN_AFTER:
                # Transición: OPEN → HALF-OPEN (permitir 1 request de prueba)
                self._state[domain] = 'half-open'
                logger.info(
                    f"Circuit breaker HALF-OPEN para {domain} "
                    f"(probando con 1 request)"
                )
                return True
            return False

        # half-open: permitir 1 request de prueba
        return True

    def record_success(self, domain: str):
        """
        Registra un request exitoso. Resetea el contador de fallos
        y cierra el circuito si estaba en half-open.
        """
        previous_state = self._state.get(domain, 'closed')
        self._failures[domain] = 0
        self._state[domain] = 'closed'

        if previous_state == 'half-open':
            logger.info(
                f"Circuit breaker CERRADO para {domain} (recuperado)"
            )

    def record_failure(self, domain: str):
        """
        Registra un fallo. Si se alcanza el threshold, abre el circuito.
        Si estaba en half-open, vuelve a abrir.
        """
        self._failures[domain] = self._failures.get(domain, 0) + 1
        self._last_failure[domain] = time.time()

        current_state = self._state.get(domain, 'closed')

        # Si estaba en half-open y falló → volver a abrir
        if current_state == 'half-open':
            self._state[domain] = 'open'
            logger.warning(
                f"Circuit breaker RE-ABIERTO para {domain} "
                f"(request de prueba falló). Cooldown {self.COOLDOWN_SECONDS}s"
            )
            return

        # Si alcanzó el threshold → abrir
        if self._failures[domain] >= self.FAILURE_THRESHOLD:
            self._state[domain] = 'open'
            logger.warning(
                f"Circuit breaker ABIERTO para {domain} — "
                f"{self._failures[domain]} fallos consecutivos. "
                f"Cooldown {self.COOLDOWN_SECONDS}s"
            )

    def get_status(self) -> dict:
        """Retorna el estado de todos los circuitos para diagnóstico."""
        all_domains = set(
            list(self._failures.keys()) + list(self._state.keys())
        )
        return {
            domain: {
                'state': self._state.get(domain, 'closed'),
                'failures': self._failures.get(domain, 0),
                'last_failure': self._last_failure.get(domain),
            }
            for domain in all_domains
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# robots.txt checker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RobotsChecker:
    """Verifica permisos en robots.txt con caché."""

    _cache: dict[str, dict] = {}

    @classmethod
    def check(cls, url: str) -> dict:
        """
        Analiza robots.txt del dominio.

        Returns:
            dict con:
            - allowed (bool): Si se permite scrapear la URL.
            - crawl_delay (float|None): Retardo recomendado.
            - sitemaps (list[str]): URLs de sitemaps encontrados.
            - has_robots (bool): Si el sitio tiene robots.txt.
        """
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        if domain in cls._cache:
            cached = cls._cache[domain]
            # Verificar permiso para esta URL específica
            cached_copy = cached.copy()
            if cached.get('_parser'):
                cached_copy['allowed'] = cached['_parser'].can_fetch(
                    BOT_USER_AGENT, url
                )
            return cached_copy

        robots_url = f"{domain}/robots.txt"
        result = {
            'allowed': True,
            'crawl_delay': None,
            'sitemaps': [],
            'has_robots': False,
            '_parser': None,
        }

        try:
            rp = RobotFileParser()
            rp.set_url(robots_url)

            # Timeout manual con requests
            resp = requests.get(robots_url, timeout=10, headers=HEADERS)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
                result['has_robots'] = True
                result['allowed'] = rp.can_fetch(BOT_USER_AGENT, url)
                result['_parser'] = rp

                # Crawl delay
                try:
                    delay = rp.crawl_delay(BOT_USER_AGENT)
                    if delay:
                        result['crawl_delay'] = float(delay)
                except Exception:
                    pass

                # Sitemaps
                sitemaps = []
                for line in resp.text.splitlines():
                    if line.strip().lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        sitemaps.append(sitemap_url)
                result['sitemaps'] = sitemaps
            else:
                # Sin robots.txt → todo permitido
                result['has_robots'] = False
                result['allowed'] = True

        except Exception as e:
            logger.debug(f"No se pudo leer robots.txt de {domain}: {e}")
            result['allowed'] = True  # Fallback permisivo

        cls._cache[domain] = result
        return result

    @classmethod
    def clear_cache(cls):
        cls._cache.clear()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# StealthSession con cloudscraper + timing lognormal (v7.0)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class StealthSession:
    """
    Sesión HTTP stealth que imita el comportamiento de un navegador real.

    Técnicas anti-bloqueo (v7.0):
    - cloudscraper: emula fingerprint TLS (JA3) de Chrome/Firefox reales,
      resolviendo challenges de Cloudflare automáticamente.
    - Sesiones persistentes con cookies por dominio.
    - Rotación de User-Agent consistente por dominio (como haría un usuario).
    - Delays con distribución lognormal: la mayoría de los delays son medianos
      (8-15s) con "colas largas" ocasionales (25-45s), imitando el patrón
      real de un humano que lee artículos a velocidades variables.
      (Distribución uniforme → detectable; lognormal → natural.)
    - Reintentos con backoff exponencial + full jitter (estilo Amazon/AWS).
    - Circuit breaker integrado para evitar golpear dominios caídos.

    Modos:
    - test_mode=True: delays reducidos (~3-6s) para pruebas rápidas.
    - test_mode=False: delays completos (~8-20s normal, 12-45s blocked).
    """

    # Máximo de reintentos por request
    MAX_RETRIES = 3

    # ── Parámetros de distribución lognormal ────────────────
    # La distribución lognormal se parametriza con (mu, sigma) donde:
    #   mu    = media del logaritmo natural de la variable
    #   sigma = desviación estándar del logaritmo natural
    #
    # Propiedades resultantes (para producción, no bloqueado):
    #   Mediana:   e^mu ≈ 12.2s
    #   Media:     e^(mu + sigma²/2) ≈ 15.3s
    #   Moda:      e^(mu - sigma²) ≈ 7.8s  (delay más frecuente)
    #   P75:       ~18s
    #   P95:       ~32s   (simula "lectura de artículo largo")
    #   P99:       ~45s   (simula "distracción / alt-tab")
    #
    # Esto es MUY diferente de uniform(8, 20) que tiene una moda "plana"
    # y nunca genera delays > 20s, algo que los WAFs pueden detectar.

    # Producción – navegación normal
    LOGNORMAL_MU = 2.5          # mediana ≈ 12.2s
    LOGNORMAL_SIGMA = 0.7       # dispersión moderada
    # Producción – sitio que nos ha bloqueado
    BLOCKED_LOGNORMAL_MU = 3.2  # mediana ≈ 24.5s
    BLOCKED_LOGNORMAL_SIGMA = 0.6
    # Test – navegación normal
    TEST_LOGNORMAL_MU = 1.2     # mediana ≈ 3.3s
    TEST_LOGNORMAL_SIGMA = 0.6
    # Test – sitio bloqueado
    TEST_BLOCKED_LOGNORMAL_MU = 1.8   # mediana ≈ 6s
    TEST_BLOCKED_LOGNORMAL_SIGMA = 0.5
    # Límites absolutos para evitar extremos absurdos
    MIN_DELAY = 2.0
    MAX_DELAY_CAP = 60.0

    def __init__(self, test_mode: bool = False):
        self._sessions: dict[str, requests.Session] = {}
        self._domain_ua: dict[str, str] = {}
        self._last_request: dict[str, float] = {}
        self.test_mode = test_mode
        # Circuit breaker compartido entre todas las sesiones
        self._circuit_breaker = DomainCircuitBreaker()

    def _get_session(self, domain: str) -> requests.Session:
        """
        Obtiene o crea una sesión persistente para un dominio.

        v7.0: Si cloudscraper está disponible, crea una sesión con
        fingerprint TLS de Chrome en Windows (el perfil más común),
        lo que hace que el handshake TLS coincida con el User-Agent.
        Si no está disponible, cae back a requests.Session estándar.
        """
        if domain not in self._sessions:
            if HAS_CLOUDSCRAPER:
                # cloudscraper emula el fingerprint TLS de Chrome + resuelve
                # los JavaScript challenges de Cloudflare automáticamente
                session = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'desktop': True,
                    }
                )
                logger.debug(
                    f"Sesión cloudscraper creada para {domain} "
                    f"(TLS fingerprint: Chrome/Windows)"
                )
            else:
                session = requests.Session()
                logger.debug(
                    f"Sesión requests estándar para {domain} "
                    f"(cloudscraper no disponible — TLS fingerprint expuesto)"
                )
            # Asignar un UA fijo por dominio (como haría un navegador real)
            ua = _random_user_agent()
            self._domain_ua[domain] = ua
            self._sessions[domain] = session
        return self._sessions[domain]

    def _human_delay(self, domain: str, is_blocked_site: bool = False):
        """
        Espera un tiempo aleatorio con distribución lognormal entre requests.

        ¿Por qué lognormal y no uniforme?
        ---------------------------------
        Los humanos reales tienen un patrón de lectura que NO es uniforme:
          - La mayoría de las acciones toman un tiempo "medio" (scroll, click)
          - Ocasionalmente, el usuario lee un artículo completo (delay largo)
          - Muy raramente, hay una pausa muy larga (alt-tab, distracción)

        Esto genera una distribución con "cola derecha larga" = lognormal.
        Una distribución uniforme (U(8,20)) genera delays absolutamente
        equidistribuidos entre 8 y 20s, algo que un WAF puede reconocer
        como patrón robótico en ~50 requests.

        La distribución lognormal genera (en producción):
          - 50% de requests:  8-15s  (navegación normal)
          - 30% de requests: 15-25s  (lectura rápida)
          - 15% de requests: 25-40s  (lectura detenida)
          - 5% de requests:  40-60s  (pausa / distracción)
        """
        now = time.time()
        last = self._last_request.get(domain, 0)
        elapsed = now - last

        # Seleccionar parámetros según modo y estado del sitio
        if self.test_mode:
            if is_blocked_site:
                mu, sigma = self.TEST_BLOCKED_LOGNORMAL_MU, self.TEST_BLOCKED_LOGNORMAL_SIGMA
            else:
                mu, sigma = self.TEST_LOGNORMAL_MU, self.TEST_LOGNORMAL_SIGMA
        else:
            if is_blocked_site:
                mu, sigma = self.BLOCKED_LOGNORMAL_MU, self.BLOCKED_LOGNORMAL_SIGMA
            else:
                mu, sigma = self.LOGNORMAL_MU, self.LOGNORMAL_SIGMA

        # Generar delay con distribución lognormal
        target_delay = random.lognormvariate(mu, sigma)
        # Clamp: evitar delays absurdamente cortos o largos
        target_delay = max(self.MIN_DELAY, min(target_delay, self.MAX_DELAY_CAP))

        remaining = target_delay - elapsed
        if remaining > 0:
            logger.debug(
                f"Stealth delay {remaining:.1f}s para {domain} "
                f"(lognormal μ={mu}, σ={sigma})"
            )
            time.sleep(remaining)

        self._last_request[domain] = time.time()

    def get(
        self,
        url: str,
        is_blocked_site: bool = False,
        referer: str | None = None,
        timeout: int = 25,
    ) -> requests.Response | None:
        """
        GET stealth con reintentos, rotación de headers, delay lognormal
        y circuit breaker integrado.

        Args:
            url: URL a solicitar.
            is_blocked_site: Si True, usa delays más largos.
            referer: URL de referencia (simula navegación desde otra página).
            timeout: Timeout en segundos.

        Returns:
            requests.Response si tuvo éxito, None si todos los reintentos fallaron.
        """
        parsed = urlparse(url)
        domain = parsed.netloc

        # ── Circuit breaker: verificar si el dominio está en cooldown ──
        if not self._circuit_breaker.can_request(domain):
            logger.debug(
                f"Circuit breaker ABIERTO para {domain} — saltando request"
            )
            return None

        session = self._get_session(domain)
        headers = _build_stealth_headers(referer)
        # Usar el UA asignado a este dominio (consistencia por sesión)
        headers['User-Agent'] = self._domain_ua.get(domain, _random_user_agent())

        for attempt in range(1, self.MAX_RETRIES + 1):
            # Delay lognormal ANTES de cada request
            self._human_delay(domain, is_blocked_site)

            try:
                resp = session.get(url, headers=headers, timeout=timeout)

                # Si recibimos 403/429/503 → backoff exponencial + rotar UA
                if resp.status_code in (403, 429, 503):
                    # Backoff exponencial con full jitter (estilo Amazon)
                    # cap = min(300, base * 2^attempt)
                    # delay = random(0, cap)
                    cap = min(300, 2 * (2 ** attempt))
                    backoff = random.uniform(cap * 0.5, cap)
                    logger.info(
                        f"HTTP {resp.status_code} en {url[:60]}… "
                        f"Reintento {attempt}/{self.MAX_RETRIES} en {backoff:.0f}s"
                    )
                    self._circuit_breaker.record_failure(domain)
                    time.sleep(backoff)
                    # Rotar User-Agent para el reintento
                    headers['User-Agent'] = _random_user_agent()
                    self._domain_ua[domain] = headers['User-Agent']
                    continue

                resp.raise_for_status()
                # ── Éxito: registrar en circuit breaker ──
                self._circuit_breaker.record_success(domain)
                return resp

            except requests.Timeout:
                logger.warning(f"Timeout en {url[:60]}… (intento {attempt})")
                self._circuit_breaker.record_failure(domain)
                if attempt < self.MAX_RETRIES:
                    time.sleep(random.uniform(5, 10))
                continue
            except requests.ConnectionError as e:
                logger.warning(f"Error conexión {url[:60]}…: {e}")
                self._circuit_breaker.record_failure(domain)
                if attempt < self.MAX_RETRIES:
                    time.sleep(random.uniform(3, 7))
                continue
            except requests.RequestException as e:
                logger.warning(f"Error HTTP en {url[:60]}…: {e}")
                self._circuit_breaker.record_failure(domain)
                return None

        logger.warning(f"Agotados {self.MAX_RETRIES} reintentos para {url[:60]}…")
        return None

    def get_circuit_breaker_status(self) -> dict:
        """Expone el estado del circuit breaker para diagnóstico."""
        return self._circuit_breaker.get_status()

    def close_all(self):
        """Cierra todas las sesiones."""
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()


class DynamicScraper:
    """
    Scraper que adapta su técnica según el sitio objetivo.

    Flujo:
      1. probe_url() → detecta tipo de fuente (rss, sitemap, html)
      2. Si robots.txt bloquea → activa modo stealth con técnicas anti-bloqueo
      3. scrape_source() → aplica la técnica apropiada

    v7.0 Mejoras:
      • cloudscraper como transport: JA3 fingerprint = Chrome real
      • Timing lognormal: distribución natural de delays
      • Circuit breaker por dominio: cooldown automático ante fallos
      • Cascada de fallback: RSS → Sitemap → HTML → Google Cache
    """

    def __init__(self, respect_robots: bool = True, default_delay: float = 1.5, test_mode: bool = False):
        self.respect_robots = respect_robots
        self.default_delay = default_delay
        self.test_mode = test_mode
        self._last_request_time: dict[str, float] = {}
        self._stealth = StealthSession(test_mode=test_mode)
        # Dominios donde se activó modo stealth (bloqueados por robots.txt)
        self._stealth_domains: set[str] = set()

    # ── Rate limiting ─────────────────────────────────────────

    def _rate_limit(self, domain: str, delay: float | None = None):
        """Espera antes de hacer otra request al mismo dominio."""
        actual_delay = delay or self.default_delay
        now = time.time()
        last = self._last_request_time.get(domain, 0)
        wait = actual_delay - (now - last)
        if wait > 0:
            time.sleep(wait)
        self._last_request_time[domain] = time.time()

    def _get(self, url: str, crawl_delay: float | None = None) -> requests.Response | None:
        """
        GET inteligente: usa modo normal o stealth según el dominio.

        Si el dominio está en la lista de stealth (bloqueado por robots.txt),
        usa la sesión stealth con delays largos y headers realistas.
        En caso contrario, usa el rate-limiting normal.

        v7.0: Todas las peticiones pasan por el circuit breaker integrado
        en StealthSession, incluso en modo normal.
        """
        parsed = urlparse(url)
        domain = parsed.netloc

        # Si este dominio requiere modo stealth
        if domain in self._stealth_domains:
            return self._stealth.get(
                url,
                is_blocked_site=True,
                referer=f"{parsed.scheme}://{domain}/",
            )

        # Modo normal: también usa StealthSession para beneficiarse del
        # circuit breaker y cloudscraper, pero con delays más cortos
        self._rate_limit(domain, crawl_delay)
        return self._stealth.get(
            url,
            is_blocked_site=False,
            referer=None,
        )

    # ── Detección de tipo de fuente ─────────────────────────

    def probe_url(self, url: str) -> dict:
        """
        Analiza una URL para determinar la mejor técnica de scraping.

        Returns:
            dict con:
            - url (str): URL original
            - domain (str): dominio
            - robots (dict): resultado de robots.txt
            - source_type (str): 'rss' | 'sitemap' | 'html' | 'blocked'
            - rss_feeds (list): feeds RSS/Atom detectados
            - sitemaps (list): sitemaps encontrados
            - can_scrape (bool): si se permite el scraping
            - recommended_method (str): método recomendado
            - crawl_delay (float|None): retardo recomendado
        """
        parsed = urlparse(url)
        domain = parsed.netloc

        result = {
            'url': url,
            'domain': domain,
            'robots': {},
            'source_type': 'unknown',
            'rss_feeds': [],
            'sitemaps': [],
            'can_scrape': True,
            'recommended_method': 'html',
            'crawl_delay': None,
        }

        # 1. Verificar robots.txt
        if self.respect_robots:
            robots_info = RobotsChecker.check(url)
            result['robots'] = {
                k: v for k, v in robots_info.items() if k != '_parser'
            }
            result['crawl_delay'] = robots_info.get('crawl_delay')
            result['sitemaps'] = robots_info.get('sitemaps', [])

            if not robots_info['allowed']:
                # ── MODO STEALTH: robots.txt bloquea, activar bypass ──
                logger.info(
                    f"robots.txt bloquea {domain} → activando modo stealth "
                    f"(cloudscraper + delays lognormales + UA rotation)"
                )
                parsed_d = urlparse(url)
                self._stealth_domains.add(parsed_d.netloc)
                # Marcar como scraping permitido via stealth
                result['can_scrape'] = True
                result['stealth_mode'] = True
                # No retornar bloqueado, continuar con detección de tipo
            else:
                result['can_scrape'] = True
                result['stealth_mode'] = False

        # 2. Intentar detectar si la URL ya es un feed RSS/Atom
        if self._is_rss_url(url):
            result['source_type'] = 'rss'
            result['rss_feeds'] = [url]
            result['recommended_method'] = 'rss'
            return result

        # 3. Cargar la página y buscar feeds RSS en <link>
        resp = self._get(url, result.get('crawl_delay'))
        if resp is None:
            result['source_type'] = 'error'
            result['recommended_method'] = 'none'
            return result

        content_type = resp.headers.get('Content-Type', '')

        # Si el content type indica XML/RSS
        if any(ct in content_type for ct in ['xml', 'rss', 'atom']):
            result['source_type'] = 'rss'
            result['rss_feeds'] = [url]
            result['recommended_method'] = 'rss'
            return result

        # 4. Parsear HTML para encontrar feeds alternativos
        soup = BeautifulSoup(resp.text, 'html.parser')
        rss_links = self._find_rss_links(soup, url)

        # 4b. Si no se encontraron feeds en HTML, probar rutas comunes
        if not rss_links:
            rss_links = self._autodiscover_rss(url)

        # 4c. Detectar si el sitio es JS-heavy (SPA)
        if _is_js_heavy_page(resp.text):
            logger.info(
                f"Sitio JS-heavy detectado: {domain} → intentando RSS/sitemap primero"
            )
            result['js_heavy'] = True
        else:
            result['js_heavy'] = False

        # 4d. Detectar página de bloqueo
        if _is_block_page(resp):
            logger.warning(
                f"Página de bloqueo/CAPTCHA detectada en {domain} → activando stealth"
            )
            self._stealth_domains.add(domain)
            result['stealth_mode'] = True

        if rss_links:
            result['rss_feeds'] = rss_links
            result['source_type'] = 'rss'
            result['recommended_method'] = 'rss'
        elif result['sitemaps']:
            result['source_type'] = 'sitemap'
            result['recommended_method'] = 'sitemap'
        else:
            result['source_type'] = 'html'
            result['recommended_method'] = 'html'
            # Si es JS-heavy y no tiene RSS ni sitemap, advertir
            if result.get('js_heavy'):
                logger.warning(
                    f"{domain} es JS-heavy sin RSS ni sitemap: "
                    f"scraping HTML puede estar limitado"
                )

        return result

    def _is_rss_url(self, url: str) -> bool:
        """Heurística para detectar si una URL es un feed RSS."""
        lower = url.lower()
        rss_indicators = [
            '/rss', '/feed', '/atom', '.xml', '/syndication',
            'format=rss', 'output=rss', 'type=rss',
        ]
        return any(indicator in lower for indicator in rss_indicators)

    def _find_rss_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Encuentra feeds RSS/Atom en los <link> de una página HTML."""
        feeds = []
        link_types = [
            'application/rss+xml',
            'application/atom+xml',
            'application/xml',
            'text/xml',
        ]
        for link in soup.find_all('link', rel='alternate'):
            link_type = link.get('type', '')
            if link_type in link_types:
                href = link.get('href', '')
                if href:
                    feeds.append(urljoin(base_url, href))

        # Buscar también links <a> con texto "RSS" o "Feed"
        for a_tag in soup.find_all('a', href=True):
            text = (a_tag.get_text() or '').strip().lower()
            href = a_tag['href'].lower()
            if any(kw in text for kw in ['rss', 'feed', 'xml']):
                feeds.append(urljoin(base_url, a_tag['href']))
            elif any(kw in href for kw in ['/rss', '/feed', '.xml']):
                feeds.append(urljoin(base_url, a_tag['href']))

        # Deduplicar
        seen = set()
        unique = []
        for f in feeds:
            if f not in seen:
                seen.add(f)
                unique.append(f)
        return unique

    def _autodiscover_rss(self, base_url: str) -> list[str]:
        """
        Intenta descubrir feeds RSS probando rutas comunes del sitio.
        Técnica de fallback cuando no se encuentran feeds en el HTML.
        """
        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        found = []

        for path in COMMON_RSS_PATHS:
            candidate = f"{origin}{path}"
            try:
                resp = self._stealth.get(candidate, timeout=8)
                if resp is None or resp.status_code != 200:
                    continue
                ct = resp.headers.get('Content-Type', '')
                # Verificar que sea XML/RSS real
                if any(x in ct for x in ['xml', 'rss', 'atom']):
                    found.append(candidate)
                    logger.info(f"Feed RSS autodescubierto: {candidate}")
                    break
                # Si es HTML, comprobar si contiene items RSS
                if 'html' not in ct:
                    text = resp.text[:500]
                    if any(tag in text for tag in ['<rss', '<feed', '<item>', '<entry>']):
                        found.append(candidate)
                        logger.info(f"Feed RSS autodescubierto (contenido): {candidate}")
                        break
            except Exception:
                continue

        return found

    def _fetch_google_cache(self, url: str) -> requests.Response | None:
        """
        Intenta obtener una página a través de Google Cache como último recurso.
        Solo funciona para páginas públicamente indexadas.
        """
        cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
        try:
            resp = self._stealth.get(
                cache_url,
                referer='https://www.google.com/',
                timeout=15,
            )
            if resp and resp.status_code == 200 and len(resp.text) > 500:
                return resp
        except Exception:
            pass
        return None

    # ── Scraping por tipo ───────────────────────────────────

    def scrape_source(
        self,
        url: str,
        method: str = 'auto',
        max_articles: int = 50,
    ) -> list[dict]:
        """
        Scrapea una fuente usando el método indicado o auto-detectado.

        Si la fuente está bloqueada por robots.txt, activa automáticamente
        el modo stealth con delays largos y técnicas anti-detección.

        Cascada de fallback: si un método no trae artículos,
        intenta el siguiente: RSS → Sitemap → HTML.

        Args:
            url: URL de la fuente.
            method: 'auto', 'rss', 'sitemap', 'html'.
            max_articles: máximo de artículos a extraer.

        Returns:
            Lista de dicts con: titulo, contenido, enlace, fuente, fecha.
        """
        if method == 'auto':
            probe = self.probe_url(url)
            if not probe['can_scrape']:
                logger.warning(f"No se pudo acceder a: {url}")
                return []
            method = probe['recommended_method']
            crawl_delay = probe.get('crawl_delay')
            rss_feeds = probe.get('rss_feeds', [])
            stealth = probe.get('stealth_mode', False)

            if stealth:
                logger.info(
                    f"Modo stealth activo para {url[:60]}… "
                    f"(cloudscraper + delays lognormales + UA rotation)"
                )
        else:
            crawl_delay = None
            rss_feeds = [url] if method == 'rss' else []
            stealth = urlparse(url).netloc in self._stealth_domains

        # ── Cascada de métodos con fallback ──
        articles = []
        methods_tried = []

        if method == 'rss':
            articles = self._scrape_rss(
                rss_feeds or [url], max_articles, crawl_delay
            )
            methods_tried.append('rss')

        if not articles and method in ('sitemap', 'rss'):
            # Si RSS no trajo nada o el método es sitemap, intentar sitemap
            if 'sitemap' not in methods_tried:
                logger.info(f"Método {method} sin resultados, intentando sitemap: {url[:60]}…")
                articles = self._scrape_sitemap(url, max_articles, crawl_delay)
                methods_tried.append('sitemap')

        if not articles and method != 'html':
            # Último recurso: HTML scraping directo
            if 'html' not in methods_tried:
                logger.info(f"Métodos {methods_tried} sin resultados, intentando HTML: {url[:60]}…")
                articles = self._scrape_html_listing(url, max_articles, crawl_delay)
                methods_tried.append('html')

        if not articles and method == 'html':
            articles = self._scrape_html_listing(url, max_articles, crawl_delay)
            methods_tried.append('html')

        if not articles:
            logger.warning(
                f"No se encontraron artículos en {url[:60]}… "
                f"(métodos intentados: {methods_tried})"
            )

        return articles

    def _scrape_rss(
        self, feeds: list[str], max_articles: int, crawl_delay: float | None
    ) -> list[dict]:
        """Extrae artículos desde feeds RSS/Atom."""
        articles = []

        for feed_url in feeds:
            if len(articles) >= max_articles:
                break

            resp = self._get(feed_url, crawl_delay)
            if resp is None:
                continue

            soup = BeautifulSoup(resp.content, 'xml')

            for item in soup.find_all(['item', 'entry']):
                if len(articles) >= max_articles:
                    break

                title = item.find('title')
                title_text = title.get_text(strip=True) if title else ''
                if not title_text:
                    continue

                # Contenido
                content = (
                    item.find('content:encoded')
                    or item.find('content')
                    or item.find('description')
                    or item.find('summary')
                )
                content_html = content.get_text() if content else ''
                content_text = BeautifulSoup(
                    content_html, 'html.parser'
                ).get_text(' ', strip=True)

                # Enlace
                link = item.find('link')
                if link:
                    link_text = link.get('href') or link.get_text(strip=True)
                else:
                    guid = item.find('guid')
                    link_text = guid.get_text(strip=True) if guid else ''

                # Fecha
                date_tag = (
                    item.find('pubDate')
                    or item.find('published')
                    or item.find('updated')
                    or item.find('dc:date')
                )
                if date_tag and date_tag.get_text(strip=True):
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(date_tag.get_text(strip=True))
                    except Exception:
                        try:
                            from dateutil import parser as dateparser
                            dt = dateparser.parse(date_tag.get_text(strip=True))
                        except Exception:
                            dt = datetime.now(timezone.utc)
                else:
                    dt = datetime.now(timezone.utc)

                articles.append({
                    'titulo': title_text,
                    'contenido': content_text,
                    'enlace': link_text,
                    'fuente': feed_url,
                    'fecha': dt.isoformat() if dt else '',
                    'scrape_method': 'rss',
                })

        return articles

    def _scrape_sitemap(
        self, base_url: str, max_articles: int, crawl_delay: float | None
    ) -> list[dict]:
        """Extrae artículos siguiendo enlaces del sitemap."""
        articles = []
        robots_info = RobotsChecker.check(base_url)
        sitemaps = robots_info.get('sitemaps', [])

        if not sitemaps:
            # Intentar sitemaps comunes
            parsed = urlparse(base_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            sitemaps = [
                f"{base}/sitemap.xml",
                f"{base}/sitemap_index.xml",
                f"{base}/sitemap-news.xml",
                f"{base}/news-sitemap.xml",
            ]

        article_urls = []

        for sitemap_url in sitemaps[:5]:  # Máx 5 sitemaps
            resp = self._get(sitemap_url, crawl_delay)
            if resp is None:
                continue

            # Verificar que sea XML real
            content_type = resp.headers.get('Content-Type', '')
            if 'html' in content_type and 'xml' not in content_type:
                continue

            try:
                soup = BeautifulSoup(resp.content, 'xml')
            except Exception:
                continue

            # Sitemap index → sub-sitemaps (priorizar news sitemaps)
            sub_sitemaps = []
            for sm in soup.find_all('sitemap'):
                loc = sm.find('loc')
                if loc:
                    sm_url = loc.get_text(strip=True)
                    # Priorizar sitemaps de noticias
                    if any(kw in sm_url.lower() for kw in ['news', 'noticias', 'nota', 'post']):
                        sub_sitemaps.insert(0, sm_url)
                    else:
                        sub_sitemaps.append(sm_url)

            for sm_url in sub_sitemaps[:5]:
                sub_resp = self._get(sm_url, crawl_delay)
                if sub_resp:
                    try:
                        sub_soup = BeautifulSoup(sub_resp.content, 'xml')
                        for url_tag in sub_soup.find_all('url'):
                            loc2 = url_tag.find('loc')
                            if loc2:
                                u = loc2.get_text(strip=True)
                                if self._looks_like_article(u):
                                    article_urls.append(u)
                            if len(article_urls) >= max_articles * 3:
                                break
                    except Exception:
                        continue
                if len(article_urls) >= max_articles * 3:
                    break

            # URLs directas en el sitemap principal
            for url_tag in soup.find_all('url'):
                loc = url_tag.find('loc')
                if loc:
                    u = loc.get_text(strip=True)
                    if self._looks_like_article(u):
                        article_urls.append(u)
                if len(article_urls) >= max_articles * 3:
                    break

            if article_urls:
                break  # Ya tenemos URLs, no seguir con más sitemaps

        # Deduplicar URLs
        seen = set()
        unique_urls = []
        for u in article_urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        # Scrapear las URLs más recientes (tomar últimas N)
        for article_url in unique_urls[-max_articles:]:
            if len(articles) >= max_articles:
                break
            article = self._extract_article(article_url, crawl_delay)
            if article:
                articles.append(article)

        return articles

    def _scrape_html_listing(
        self, url: str, max_articles: int, crawl_delay: float | None
    ) -> list[dict]:
        """
        Scrapea una página HTML que lista noticias.
        Extrae enlaces a artículos y luego scrapea cada uno.

        En modo stealth NO re-verifica robots.txt por artículo
        (ya se decidió hacer bypass al nivel del dominio).
        """
        articles = []

        resp = self._get(url, crawl_delay)
        if resp is None:
            return articles

        soup = BeautifulSoup(resp.text, 'html.parser')
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc
        is_stealth = base_domain in self._stealth_domains

        # Encontrar enlaces a artículos
        article_urls = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(url, href)
            parsed_href = urlparse(full_url)

            # Solo enlaces del mismo dominio
            if parsed_href.netloc != base_domain:
                continue

            # Ignorar enlaces a home, secciones genéricas, etc.
            path = parsed_href.path.rstrip('/')
            if not path or path == '' or path.count('/') < 2:
                # Aceptar si _looks_like_article o si tiene texto largo de título
                text = a_tag.get_text(strip=True)
                if self._looks_like_article(full_url) and len(text) > 15:
                    article_urls.append((full_url, text))
                continue

            text = a_tag.get_text(strip=True)

            # Método 1: URL coincide con patrones de artículo
            if self._looks_like_article(full_url) and len(text) > 10:
                article_urls.append((full_url, text))
                continue

            # Método 2: URLs con paths profundos y texto largo (probablemente artículos)
            if path.count('/') >= 2 and len(text) > 25:
                # Filtrar enlaces que claramente NO son artículos
                skip_patterns = [
                    r'^/(tag|categoria|category|autor|author|page|buscar|search|login|registro|contacto|about|privacy|terminos|aviso)',
                    r'\.(jpg|png|gif|pdf|mp4|mp3|css|js)$',
                    r'/(wp-content|wp-admin|assets|static)/',
                ]
                is_skip = any(re.search(p, path, re.IGNORECASE) for p in skip_patterns)
                if not is_skip:
                    article_urls.append((full_url, text))

        # Deduplicar preservando orden
        seen = set()
        unique_urls = []
        for u, t in article_urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append((u, t))

        logger.info(f"HTML listing: {len(unique_urls)} enlaces a artículos en {url[:60]}…")

        # Extraer contenido de cada artículo
        for article_url, _ in unique_urls[:max_articles]:
            if len(articles) >= max_articles:
                break

            # En modo stealth: NO re-verificar robots.txt por artículo
            # (ya decidimos hacer bypass al nivel del dominio)
            if not is_stealth and self.respect_robots:
                check = RobotsChecker.check(article_url)
                if not check['allowed']:
                    # Activar stealth para este dominio y continuar
                    self._stealth_domains.add(parsed_base.netloc)
                    is_stealth = True
                    logger.info(f"Activando stealth mid-scrape para {base_domain}")

            article = self._extract_article(article_url, crawl_delay)
            if article:
                articles.append(article)

        return articles

    def _looks_like_article(self, url: str) -> bool:
        """
        Determina si una URL parece ser un artículo de noticias.
        Usa patrones de URL + heurísticas de estructura.
        """
        # Excluir URLs claramente no-artículo
        parsed = urlparse(url)
        path = parsed.path.lower()

        # Excluir páginas genéricas
        excludes = [
            r'^/$', r'^/index', r'^/home', r'^/contacto', r'^/about',
            r'^/login', r'^/registro', r'^/buscar', r'^/search',
            r'^/tag/', r'^/tags/', r'^/categoria/', r'^/category/',
            r'^/autor/', r'^/author/', r'^/page/\d+',
            r'\.(jpg|png|gif|svg|pdf|css|js|mp4|mp3)$',
            r'^/(wp-admin|wp-content|assets|static|media|img)/',
        ]
        for exc in excludes:
            if re.search(exc, path):
                return False

        # Método 1: patrones conocidos de URLs de artículos
        for pattern in NEWS_PATH_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        # Método 2: URL con slug tipo artículo (path con 3+ segmentos o slug largo)
        segments = [s for s in path.split('/') if s]
        if len(segments) >= 2:
            last_segment = segments[-1]
            # Slug con guiones tipo "feminicidio-en-estado-de-mexico"
            if '-' in last_segment and len(last_segment) > 20:
                return True
            # Último segmento es numérico (ID de noticia)
            if last_segment.isdigit() and len(last_segment) >= 4:
                return True

        return False

    def _extract_article(
        self, url: str, crawl_delay: float | None = None
    ) -> dict | None:
        """
        Extrae título, contenido y fecha de una página de artículo.

        Estrategia multi-nivel (cascada):
          1. Petición HTTP normal / stealth
          2. Si la página está bloqueada → Google Cache fallback
          3. JSON-LD / Schema.org (más fiable si está disponible)
          4. trafilatura (extractor ML moderno, si está instalado)
          5. Selectores CSS específicos por sitio
          6. Meta tags og:title, og:description
          7. Descarte si el contenido mínimo no se cumple

        Si la página es JS-heavy, lo registra como warning.
        """
        resp = self._get(url, crawl_delay)
        if resp is None:
            return None

        # ── Detección de bloqueo ────────────────────────────
        if _is_block_page(resp):
            domain = urlparse(url).netloc
            logger.info(
                f"Bloqueo detectado en {url[:60]}… → activando stealth + "
                f"intentando Google Cache"
            )
            self._stealth_domains.add(domain)

            # Primer reintento en stealth
            resp = self._stealth.get(url, is_blocked_site=True)
            if resp is None or _is_block_page(resp):
                # Último recurso: caché de Google
                resp = self._fetch_google_cache(url)
                if resp is None:
                    logger.warning(
                        f"No se pudo extraer {url[:60]}: bloqueado y sin caché"
                    )
                    return None

        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')

        # ── Advertencia: JS-heavy ─────────────────────────
        if _is_js_heavy_page(html):
            logger.debug(f"Página JS-heavy: {url[:60]} — contenido puede ser limitado")

        title = ''
        content = ''
        date_str = ''

        # ── Nivel 1: JSON-LD / Schema.org ─────────────────
        jld = _extract_json_ld(soup)
        if jld['title']:
            title = jld['title']
        if jld['content'] and len(jld['content']) >= 100:
            content = jld['content']
        if jld['date']:
            date_str = jld['date']

        # ── Nivel 2: trafilatura ───────────────────────────
        if not content or len(content) < 100:
            traf = _extract_with_trafilatura(url, html)
            if traf:
                if not title and traf['title']:
                    title = traf['title']
                if traf['content'] and len(traf['content']) >= 100:
                    content = traf['content']
                if not date_str and traf['date']:
                    date_str = traf['date']

        # ── Nivel 3: Selectores CSS específicos ───────────
        if not title:
            for sel in TITLE_SELECTORS:
                tag = soup.select_one(sel)
                if tag:
                    title = tag.get_text(strip=True)
                    break
        if not title:
            og_title = soup.find('meta', property='og:title')
            if og_title:
                title = og_title.get('content', '')
        if not title:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)

        if not content or len(content) < 100:
            for sel in ARTICLE_SELECTORS:
                container = soup.select_one(sel)
                if container:
                    for tag in container.find_all(
                        ['script', 'style', 'nav', 'aside', 'iframe',
                         'noscript', 'footer', 'header', 'figure',
                         'figcaption', 'form', 'button']
                    ):
                        tag.decompose()
                    paragraphs = container.find_all('p')
                    if paragraphs:
                        candidate = ' '.join(
                            p.get_text(' ', strip=True) for p in paragraphs
                            if len(p.get_text(strip=True)) > 30
                        )
                        if len(candidate) >= 100:
                            content = candidate
                            break
                    else:
                        candidate = container.get_text(' ', strip=True)
                        if len(candidate) >= 100:
                            content = candidate
                            break

        # ── Nivel 4: Fallback a meta tags ─────────────────
        if not content or len(content) < 80:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                content = meta_desc.get('content', '')
            if not content:
                og_desc = soup.find('meta', property='og:description')
                if og_desc:
                    content = og_desc.get('content', '')

        # ── Validación mínima ──────────────────────────────
        if not title or len(title) < 10:
            return None
        if not content or len(content) < 50:
            return None

        # ── Fecha ──────────────────────────────────────────
        dt = datetime.now(timezone.utc)

        if not date_str:
            for sel in DATE_SELECTORS:
                if sel.startswith('meta'):
                    tag = soup.select_one(sel)
                    if tag:
                        date_str = tag.get('content', '')
                        break
                else:
                    tag = soup.select_one(sel)
                    if tag:
                        date_str = tag.get('datetime') or tag.get_text(strip=True)
                        break

        if date_str:
            try:
                from dateutil import parser as dateparser
                dt = dateparser.parse(date_str)
            except Exception:
                dt = datetime.now(timezone.utc)

        return {
            'titulo': title,
            'contenido': content[:4000],  # Limitar a 4000 chars
            'enlace': url,
            'fuente': urlparse(url).netloc,
            'fecha': dt.isoformat() if dt else '',
            'scrape_method': 'html',
        }

    # ── Utilidades ──────────────────────────────────────────

    def get_circuit_breaker_status(self) -> dict:
        """Expone el estado del circuit breaker para diagnóstico externo."""
        return self._stealth.get_circuit_breaker_status()

    def close(self):
        """Libera recursos (cierra sesiones stealth)."""
        self._stealth.close_all()

    @staticmethod
    def content_hash(title: str, content: str) -> str:
        """Genera un hash del contenido para detección de duplicados."""
        text = f"{title.strip().lower()}|{content.strip().lower()[:500]}"
        return hashlib.md5(text.encode('utf-8')).hexdigest()
