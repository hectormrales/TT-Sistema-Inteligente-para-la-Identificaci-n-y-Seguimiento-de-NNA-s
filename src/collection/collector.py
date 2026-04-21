# src/collection/collector.py — Recolector de noticias con scoring de relevancia
"""
Recolecta noticias desde feeds RSS, fuentes dinámicas (DB) y web scraping:
  • Eje 1 – Feminicidio: ¿la noticia habla de feminicidio / violencia feminicida?
  • Eje 2 – NNA: ¿menciona víctimas indirectas (niños, niñas, adolescentes)?

Incluye deduplicación avanzada cross-site (v4.0).
Solo se conservan noticias que superan el umbral de relevancia compuesto.

v6.0 TT2 Mejoras:
  - Filtro geográfico México reforzado con scoring ponderado (título 3x)
  - 100+ indicadores de ciudades/estados/instituciones mexicanas
  - Tracking de URLs previamente procesadas (evita re-scrapping)
  - Logging mejorado para diagnóstico de fuentes fallidas
  - Filtro de antigüedad (máx. 30 días para feeds RSS)

v7.0 Mejoras (Fase 1 — Pipeline unificado):
  - TODAS las peticiones HTTP ahora pasan por StealthSession, incluyendo
    las de feeds RSS que antes usaban requests.get() directo.
  - Esto garantiza que cada request tiene:
    • Fingerprint TLS (JA3) de Chrome real via cloudscraper
    • Delays con distribución lognormal (anti-fingerprinting)
    • Circuit breaker por dominio (evita golpear sitios caídos)
    • Rotación de User-Agent consistente por dominio
  - Se eliminó la dependencia directa de 'requests' para peticiones HTTP.
"""

import json
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from unicodedata import normalize
from typing import Tuple, Optional

import requests  # Solo para type hints de Response
import pandas as pd
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime

import config
from src.collection.scraper import DynamicScraper, StealthSession
from src.analysis.dedup import NewsDeduplicator

logger = logging.getLogger(__name__)

# Archivo de URLs ya procesadas (evita re-scraping cada ciclo)
_SEEN_URLS_FILE = os.path.join(
    os.environ.get('DATA_DIR', 'data'), 'seen_urls.json'
)
_MAX_AGE_DAYS = 30  # Máxima antigüedad de noticias a recolectar


def _load_seen_urls() -> set:
    """Carga el set de URLs ya procesadas desde disco."""
    try:
        if os.path.exists(_SEEN_URLS_FILE):
            with open(_SEEN_URLS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Limpieza: solo mantener URLs de los últimos 60 días
                cutoff = (datetime.now() - timedelta(days=60)).isoformat()
                if isinstance(data, dict):
                    return {url for url, ts in data.items() if ts > cutoff}
                return set(data)
    except Exception as e:
        logger.warning(f"Error cargando seen_urls: {e}")
    return set()


def _save_seen_urls(urls: set):
    """Guarda el set de URLs procesadas a disco con timestamp."""
    try:
        os.makedirs(os.path.dirname(_SEEN_URLS_FILE) or '.', exist_ok=True)
        now = datetime.now().isoformat()
        data = {url: now for url in urls}
        with open(_SEEN_URLS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Error guardando seen_urls: {e}")


def _is_recent(date_str: str, max_days: int = _MAX_AGE_DAYS) -> bool:
    """Verifica que una noticia no sea más antigua que max_days."""
    try:
        from dateutil import parser as dateutil_parser
        dt = dateutil_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
        return dt >= cutoff
    except Exception:
        return True  # Si no se puede parsear la fecha, incluir por defecto


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Diccionarios de keywords ponderados por importancia
# Los pesos indican cuán fuerte es la señal de cada término.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── Eje 1: Feminicidio ─────────────────────────────────────
FEMINICIDIO_KEYWORDS: list[Tuple[str, float]] = [
    # Términos directos (peso alto)
    (r'\bfeminicidio\b',               1.0),
    (r'\bfemicidio\b',                 1.0),
    (r'\bviolencia\s+feminicida\b',    1.0),
    (r'\bmuerte\s+violenta\s+de\s+(?:una\s+)?mujer\b', 0.9),
    (r'\basesinato\s+de\s+(?:una\s+)?mujer\b', 0.9),
    (r'\bhomicidio\s+(?:doloso\s+)?de\s+(?:una\s+)?mujer\b', 0.85),
    (r'\bviolencia\s+de\s+g[eé]nero\b', 0.7),
    (r'\bcrimen\s+de\s+g[eé]nero\b',  0.7),
    (r'\bviolencia\s+contra\s+(?:la\s+)?mujer(?:es)?\b', 0.65),
    (r'\bmata(?:ron|r(?:on)?|do|da)?\s+a\s+(?:su\s+)?(?:esposa|pareja|novia|mujer|concubina|ex)\b', 0.85),
    (r'\bpriv[oó]\s+de\s+la\s+vida\b', 0.6),
    # Contextuales (peso medio)
    (r'\balerta\s+de\s+(?:violencia\s+de\s+)?g[eé]nero\b', 0.55),
    (r'\bviolencia\s+(?:dom[eé]stica|intrafamiliar|familiar)\b', 0.5),
    (r'\bagres(?:or|ión)\s+(?:sexual|física)\b', 0.45),
    (r'\bvictimario\b',                0.4),
    (r'\bpareja\s+sentimental\b',      0.35),
    (r'\bex\s*pareja\b',               0.35),
]

# ── Eje 2: NNA (víctimas indirectas) ───────────────────────
NNA_KEYWORDS: list[Tuple[str, float]] = [
    # Términos directos (peso alto)
    (r'\bhu[eé]rfan[oa]s?\b',          1.0),
    (r'\borfandad\b',                  1.0),
    (r'\bv[ií]ctimas?\s+indirectas?\b', 1.0),
    (r'\bv[ií]ctimas?\s+colaterales?\b', 0.95),
    (r'\bhijos?\s+(?:de\s+(?:la\s+)?v[ií]ctima|quedaron)\b', 0.95),
    (r'\bhijas?\s+(?:de\s+(?:la\s+)?v[ií]ctima|quedaron)\b', 0.95),
    (r'\bmenor(?:es)?\s+(?:de\s+edad|desprotegid[oa]s?|desamparad[oa]s?|afectad[oa]s?)\b', 0.9),
    (r'\bNNA\b',                       0.9),
    (r'\bni[ñn][oa]s?\s+(?:quedaron|sobreviv|afectad|desamparad|sin\s+madre)\b', 0.9),
    # Términos de NNA genéricos (peso medio)
    (r'\bhij[oa]s?\b',                 0.6),
    (r'\bmenor(?:es)?(?:\s+de\s+edad)?\b', 0.55),
    (r'\bni[ñn][oa]s?\b',             0.5),
    (r'\badolescentes?\b',             0.5),
    (r'\binfant(?:e|il|es)\b',         0.45),
    (r'\bbeb[eé]s?\b',                 0.45),
    (r'\breci[eé]n\s+nacid[oa]s?\b',   0.4),
    # Contexto institucional
    (r'\bDIF\b',                       0.4),
    (r'\bcustodia\b',                  0.4),
    (r'\btutela\b',                    0.35),
    (r'\bcasa\s+hogar\b',              0.35),
    (r'\balbergue\b',                  0.3),
    # Edades
    (r'\bde\s+\d{1,2}\s+a[ñn]os(?:\s+de\s+edad)?\b', 0.45),
    (r'\b\d{1,2}\s+a[ñn]os\s+de\s+edad\b', 0.45),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Filtro geográfico: Solo noticias de México
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Estados y ciudades de México (para detectar contexto mexicano)
MEXICO_INDICATORS = [
    # País
    r'\bm[eé]xico\b', r'\bmexican[oa]s?\b', r'\brepública\s+mexicana\b',
    # Estados (32 entidades federativas)
    r'\baguascalientes\b', r'\bbaja\s+california\b', r'\bcampeche\b',
    r'\bchiapas\b', r'\bchihuahua\b', r'\bcoahuila\b', r'\bcolima\b',
    r'\bdurango\b', r'\bguanajuato\b', r'\bguerrero\b', r'\bhidalgo\b',
    r'\bjalisco\b', r'\bmichoacán\b', r'\bmorelos\b', r'\bnayarit\b',
    r'\bnuevo\s+le[oó]n\b', r'\boaxaca\b', r'\bpuebla\b', r'\bquer[eé]taro\b',
    r'\bquintana\s+roo\b', r'\bsan\s+luis\s+potos[ií]\b', r'\bsinaloa\b',
    r'\bsonora\b', r'\btabasco\b', r'\btamaulipas\b', r'\btlaxcala\b',
    r'\bveracruz\b', r'\byucat[aá]n\b', r'\bzacatecas\b',
    r'\bestado\s+de\s+m[eé]xico\b', r'\bcdmx\b', r'\bciudad\s+de\s+m[eé]xico\b',
    # Ciudades principales y municipios clave
    r'\bguadalajara\b', r'\bmonterrey\b', r'\btijuana\b', r'\bjuárez\b',
    r'\bju[aá]rez\b', r'\ble[oó]n\b', r'\becatepec\b', r'\bneza\b',
    r'\btoluca\b', r'\bculiac[aá]n\b', r'\bcancún\b', r'\bacapulco\b',
    r'\bmerida\b', r'\bm[eé]rida\b', r'\bvillahermosa\b', r'\bhermosillo\b',
    r'\bsaltillo\b', r'\btuxtla\b', r'\bxalapa\b', r'\btorreón\b',
    r'\bmatamoros\b', r'\breynosa\b', r'\bplaya\s+del\s+carmen\b',
    r'\biztapalapa\b', r'\bnaucalpan\b', r'\btlalnepantla\b',
    # Ciudades adicionales de alta violencia
    r'\bcelaya\b', r'\bchilpancingo\b', r'\birapuato\b', r'\bpachuca\b',
    r'\bcuernavaca\b', r'\btepic\b', r'\bchetumal\b', r'\bmazatl[aá]n\b',
    r'\blos\s+mochis\b', r'\bensenada\b', r'\bmexicali\b', r'\bla\s+paz\s+bcs\b',
    r'\btuxtla\s+guti[eé]rrez\b', r'\bsan\s+crist[oó]bal\b', r'\btapachula\b',
    r'\bcoatzacoalcos\b', r'\borizaba\b', r'\bc[oó]rdoba\b', r'\bpoza\s+rica\b',
    r'\bnuevo\s+laredo\b', r'\bciudad\s+victoria\b', r'\btampico\b',
    r'\bciudad\s+obreg[oó]n\b', r'\bnogales\b', r'\bagua\s*prieta\b',
    r'\bzihuatanejo\b', r'\btaxco\b', r'\biguala\b', r'\btlapa\b',
    r'\bpuerto\s+vallarta\b', r'\bzapopan\b', r'\btlaquepaque\b',
    r'\btonalá\b', r'\bsan\s+pedro\s+garza\b', r'\bapodaca\b',
    r'\bsan\s+nicol[aá]s\b', r'\besc[oó]bedo\b',
    # Municipios del Edomex peligrosos
    r'\bchimalhuac[aá]n\b', r'\bchalco\b', r'\btexcoco\b', r'\blos\s+reyes\b',
    r'\bcuautitl[aá]n\b', r'\batizap[aá]n\b',
    # Alcaldías de CDMX
    r'\btl[aá]huac\b', r'\bxochimilco\b', r'\bgustavo\s+a\.?\s+madero\b',
    r'\bvenustiano\s+carranza\b', r'\b[aá]lvaro\s+obreg[oó]n\b',
    r'\bcoyoac[aá]n\b', r'\bbenito\s+ju[aá]rez\b', r'\bcuauht[eé]moc\b',
    r'\bmiguel\s+hidalgo\b', r'\bazcapotzalco\b',
    # Instituciones mexicanas
    r'\bfisca[il]ía\b', r'\bfgr\b', r'\bfgj\b', r'\bsemefo\b',
    r'\bDIF\b', r'\bSEP\b', r'\bIMSS\b', r'\bcndh\b',
    r'\bconavim\b', r'\binmujeres\b', r'\bsspc\b',
    r'\bguardia\s+nacional\b', r'\bprocuradur[ií]a\b',
    r'\balerta\s+de\s+(?:violencia\s+de\s+)?g[eé]nero\b',
    r'\bcódigo?\s+rojo\b', r'\bministerio\s+p[uú]blico\b',
    # Instituciones/términos exclusivamente mexicanos
    r'\bsedena\b', r'\bsemar\b', r'\bconago\b',
    r'\bmorena\b', r'\bpri\b', r'\bpan\b', r'\bprd\b',
    r'\binegi\b', r'\bconapo\b', r'\bconeval\b',
    r'\bsipinna\b', r'\bceav\b', r'\bfiscal[ií]a\s+general\b',
    r'\bamlo\b', r'\bclaudia\s+sheinbaum\b',
    r'\bsecretar[ií]a\s+de\s+gobernaci[oó]n\b',
    r'\bsegob\b', r'\bbienestar\b',
]

# Indicadores de que la noticia NO es de México (ampliado)
NON_MEXICO_INDICATORS = [
    # Sudamérica
    r'\bargentina\b', r'\bbuenos\s+aires\b', r'\bcolombia\b', r'\bbogot[aá]\b',
    r'\bmedell[ií]n\b', r'\bcali\b(?!\s*fornia)', r'\bper[uú]\b', r'\blima\b',
    r'\bchile\b', r'\bsantiago\b', r'\bvalparaíso\b',
    r'\bvenezuela\b', r'\bcaracas\b', r'\becuador\b', r'\bquito\b',
    r'\bguayaquil\b', r'\bbolivia\b', r'\bparaguay\b', r'\basunci[oó]n\b',
    r'\buruguay\b', r'\bmontevideo\b', r'\bbrasil\b', r'\bsão\s+paulo\b',
    r'\bbrasilia\b', r'\br[ií]o\s+de\s+janeiro\b',
    # Europa
    r'\bespaña\b', r'\bmadrid\b', r'\bbarcelona\b', r'\bfrancia\b',
    r'\balemani[ea]\b', r'\bitalia\b', r'\breino\s+unido\b',
    # Norteamérica (no-México)
    r'\bestados\s+unidos\b', r'\bnew\s+york\b', r'\bwashington\b',
    r'\btexas\b', r'\bcalifornia\b', r'\bflorida\b', r'\bcanad[aá]\b',
    # Centroamérica y Caribe
    r'\bel\s+salvador\b', r'\bguatemala\b', r'\bhonduras\b',
    r'\btegucigalpa\b', r'\bsan\s+salvador\b', r'\bciudad\s+de\s+guatemala\b',
    r'\bnicaragua\b', r'\bmanagua\b', r'\bcosta\s+rica\b', r'\bsan\s+jos[eé]\b',
    r'\bpanam[aá]\b', r'\brepública\s+dominicana\b', r'\bsanto\s+domingo\b',
    r'\bcuba\b', r'\bla\s+habana\b', r'\bhaití\b', r'\bpuerto\s+rico\b',
    r'\bbelice\b',
]

# Dominios de medios mexicanos conocidos (siempre pasan el filtro)
MEXICAN_DOMAINS = {
    'jornada.com.mx', 'proceso.com.mx', 'aristeguinoticias.com',
    'animalpolitico.com', 'sinembargo.mx', 'elsoldemexico.com.mx',
    'elfinanciero.com.mx', 'eluniversal.com.mx', 'milenio.com',
    'excelsior.com.mx', 'reporteindigo.com', 'piedepagina.mx',
    'contralinea.com.mx', 'sdpnoticias.com', 'debate.com.mx',
    'razon.com.mx', 'elheraldodemexico.com', 'informador.mx',
    'zocalo.com.mx', 'lajornadadeoriente.com.mx', 'cimacnoticias.com.mx',
    'luchadoras.mx', 'eleconomista.com.mx', 'unotv.com', 'televisa.com',
    'elsoldetoluca.com.mx', 'elsoldepuebla.com.mx', 'diariodexalapa.com.mx',
    'noroeste.com.mx', 'elsiglodetorreon.com.mx', 'lasillarota.com',
    'expansion.mx', 'forbes.com.mx', 'nmas.com.mx', 'infobae.com',
    # news.google.com: NO se marca como dominio mexicano; el filtro de texto
    # se encarga de verificar el contenido artículo por artículo.
}


def _is_mexico_news(title: str, content: str, source_url: str = '') -> bool:
    """
    Determina si una noticia es de México.

    Lógica estricta v6.0 — Mejorada para ONGs:
      1. Si el dominio es .mx conocido → verificar que NO hable de otro país
         como tema principal (medios mexicanos cubren noticias de Centroamérica)
      2. Si hay indicadores claros de OTRO país sin contrapeso mexicano → False
      3. Si hay indicadores de México superiores a los extranjeros → True
      4. Sin señales, fuente neutral → False (filtro conservador)

    Mejoras v6.0:
      - Verificación estricta para dominios .mx (evita falsos positivos de
        noticias centroamericanas publicadas en medios mexicanos)
      - Score ponderado: indicadores en título pesan 3x más que en contenido
      - Más ciudades/municipios mexicanos para reducir falsos negativos
      - Instituciones exclusivamente mexicanas como señal fuerte
    """
    from urllib.parse import urlparse as _urlparse

    article_domain = ''
    if source_url:
        article_domain = _urlparse(source_url).netloc.replace('www.', '')

    text_title = title.lower() if title else ''
    text_content = content.lower() if content else ''
    text_combined = f"{text_title} {text_content}"

    # Contar indicadores con peso (título vale 3x)
    def _weighted_count(indicators, title_text, content_text):
        count = 0
        for p in indicators:
            in_title = bool(re.search(p, title_text, re.IGNORECASE))
            in_content = bool(re.search(p, content_text, re.IGNORECASE))
            if in_title:
                count += 3  # título pesa más
            elif in_content:
                count += 1
        return count

    mexico_score = _weighted_count(MEXICO_INDICATORS, text_title, text_content)
    non_mexico_score = _weighted_count(NON_MEXICO_INDICATORS, text_title, text_content)

    # 1. Dominio mexicano conocido
    if article_domain in MEXICAN_DOMAINS or article_domain.endswith('.mx'):
        # Aun así, si el TÍTULO menciona otro país y NO menciona México → rechazar
        # (medios mexicanos publican noticias de Centroamérica)
        if non_mexico_score > 0 and mexico_score == 0:
            return False
        # Si hay más indicadores extranjeros que mexicanos en la nota completa
        # y el título no menciona México → es una nota internacional
        if non_mexico_score > mexico_score and mexico_score < 3:
            return False
        return True

    # 2. Descarte duro: menciona país extranjero y NADA de México
    if non_mexico_score > 0 and mexico_score == 0:
        return False

    # 3. Si indicadores extranjeros superan a México → rechazar
    if non_mexico_score >= mexico_score and non_mexico_score > 0:
        return False

    # 4. Al menos un indicador de México → aceptar
    if mexico_score >= 1:
        return True

    # 5. Sin indicadores claros: fuentes .mx → beneficio de la duda
    if article_domain.endswith('.mx') and 'google' not in article_domain:
        return True

    # Filtro conservador: sin señal de México = descartar
    return False


def _normalize_text(text: str) -> str:
    """Normaliza texto: NFKD + minúsculas, conserva ñ/acentos para regex."""
    if not isinstance(text, str):
        return ''
    return normalize('NFKD', text).lower()


def _score_axis(text_norm: str, keywords: list[Tuple[str, float]]) -> float:
    """
    Calcula un score [0, 1] para un eje de relevancia.

    Acumula los pesos de TODOS los keywords encontrados (no solo el primero),
    luego aplica una función sigmoide suave para limitar el resultado a [0,1].

    La fórmula final es:  score = 1 - 1 / (1 + accumulated_weight)
    Con esto, más coincidencias → score más alto, pero nunca > 1.
    
    v4.1: Factor de acumulación aumentado para que múltiples coincidencias
    tengan más impacto y se acerquen más rápido al tope.
    """
    total = 0.0
    matches_count = 0
    for pattern, weight in keywords:
        matches = re.findall(pattern, text_norm, re.IGNORECASE)
        if matches:
            n = min(len(matches), 3)
            total += weight * n
            matches_count += 1
    
    # Bonus por diversidad: si hay muchos keywords distintos, boost
    if matches_count >= 3:
        total *= 1.15
    if matches_count >= 5:
        total *= 1.10
    
    # Sigmoide suave
    return 1.0 - 1.0 / (1.0 + total)


def score_relevance(title: str, content: str) -> dict:
    """
    Calcula la relevancia compuesta de un artículo.

    Returns:
        dict con:
            - score_feminicidio  (0-1): relevancia al eje feminicidio
            - score_nna          (0-1): relevancia al eje NNA
            - score_compuesto    (0-1): score ponderado final
            - clasificacion      (str): Alta / Media / Baja / No relevante
            - menores_identificados (str): Sí / No
    """
    title_boost = getattr(config, 'TITLE_BOOST', 3.0)
    threshold = getattr(config, 'RELEVANCE_THRESHOLD', 0.25)
    w_fem = getattr(config, 'RELEVANCE_WEIGHT_FEMINICIDIO', 0.55)
    w_nna = getattr(config, 'RELEVANCE_WEIGHT_NNA', 0.45)

    title_norm = _normalize_text(title)
    content_norm = _normalize_text(content)

    # Score por eje: título tiene más peso que contenido
    fem_title = _score_axis(title_norm, FEMINICIDIO_KEYWORDS) * title_boost
    fem_content = _score_axis(content_norm, FEMINICIDIO_KEYWORDS)
    score_fem = min(1.0, (fem_title + fem_content) / (1.0 + title_boost))

    nna_title = _score_axis(title_norm, NNA_KEYWORDS) * title_boost
    nna_content = _score_axis(content_norm, NNA_KEYWORDS)
    score_nna = min(1.0, (nna_title + nna_content) / (1.0 + title_boost))

    # Score compuesto ponderado
    score_comp = w_fem * score_fem + w_nna * score_nna

    # Bonus: si AMBOS ejes tienen señal, boost multiplicativo
    # v4.1: Boost más agresivo para capturar noticias realmente relevantes
    if score_fem > 0.10 and score_nna > 0.10:
        # Cuanto más fuertes ambos ejes, mayor el boost
        dual_strength = min(score_fem, score_nna)
        if dual_strength > 0.30:
            score_comp = min(1.0, score_comp * 1.55)
        elif dual_strength > 0.15:
            score_comp = min(1.0, score_comp * 1.45)
        else:
            score_comp = min(1.0, score_comp * 1.35)

    # Bonus adicional: si el título menciona directamente feminicidio/NNA
    direct_fem_title = bool(re.search(
        r'\bfeminicidio|femicidio|violencia\s+feminicida|asesinato\s+de\s+(?:una\s+)?mujer\b',
        title_norm, re.IGNORECASE
    ))
    direct_nna_title = bool(re.search(
        r'\bhu[eé]rfan|orfandad|hijos?|hijas?|menores?|ni[\u00f1n][oa]s?|NNA|v[ií]ctimas?\s+indirectas?\b',
        title_norm, re.IGNORECASE
    ))
    if direct_fem_title and direct_nna_title:
        score_comp = min(1.0, score_comp * 1.20)
    elif direct_fem_title:
        score_comp = min(1.0, score_comp * 1.10)

    # ── Penalización: tentativas / intentos (NO son feminicidios consumados) ──
    # El usuario solo quiere feminicidios reales, no tentativas ni intentos.
    TENTATIVA_PATTERNS = [
        r'\btentativa\s+de\s+feminicidio\b',
        r'\bintento\s+de\s+feminicidio\b',
        r'\bsobre\s*vivi[oó]\b',
        r'\bfeminicidio\s+(?:en\s+)?grado\s+de\s+tentativa\b',
        r'\bintent[oó]\s+(?:asesinar|matar|privar)\b',
    ]
    is_tentativa = any(
        re.search(p, title_norm, re.IGNORECASE) or
        re.search(p, content_norm, re.IGNORECASE)
        for p in TENTATIVA_PATTERNS
    )
    if is_tentativa:
        score_comp *= 0.35  # Reducción fuerte: aparece pero con baja relevancia

    # ── Penalización: noticias de estadísticas / cifras / reportes ──
    # No son casos individuales sino reportajes generales de cifras.
    STATS_PATTERNS = [
        r'\bcifras?\s+de\s+feminicidio\b',
        r'\bestadísticas?\s+de\s+(?:feminicidio|violencia)\b',
        r'\b(?:sube|baja|aumenta|disminuye|incrementa)\s+(?:el\s+)?(?:número|cifra|índice|tasa)\b',
        r'\binforme\s+(?:anual|mensual|trimestral|semestral|de\s+cifras)\b',
        r'\breporte\s+(?:anual|mensual|estadístico|de\s+incidencia)\b',
        r'\b\d+\s+(?:feminicidios|víctimas)\s+(?:en|durante)\s+(?:el\s+)?\d{4}\b',
        r'\btasa\s+de\s+feminicidio\b',
    ]
    is_stats = any(
        re.search(p, title_norm, re.IGNORECASE) or
        re.search(p, content_norm, re.IGNORECASE)
        for p in STATS_PATTERNS
    )
    # Solo penalizar si NO hay también señal de NNA (caso individual con cifras)
    if is_stats and score_nna < 0.15:
        score_comp *= 0.45  # Reducción moderada

    # Reclasificar después de penalizaciones
    if score_comp >= 0.45:
        clasificacion = 'Alta'
    elif score_comp >= 0.30:
        clasificacion = 'Media'
    elif score_comp >= threshold:
        clasificacion = 'Baja'
    else:
        clasificacion = 'No relevante'

    return {
        'score_feminicidio': round(score_fem, 4),
        'score_nna': round(score_nna, 4),
        'score_compuesto': round(score_comp, 4),
        'clasificacion': clasificacion,
        'menores_identificados': 'Si' if score_nna > 0.10 else 'No',
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Recolección RSS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def collect_news_from_rss(
    rss_url: str,
    seen_urls: set | None = None,
    session: Optional[StealthSession] = None,
) -> list[dict]:
    """Recolecta artículos desde un feed RSS individual.

    v7.0: Todas las peticiones HTTP pasan por StealthSession para
    beneficiarse de cloudscraper (bypass Cloudflare), TLS fingerprinting
    realista, delays lognormales y circuit breaker por dominio.

    Args:
        rss_url: URL del feed RSS.
        seen_urls: Set de URLs ya procesadas (para evitar re-scraping).
        session: StealthSession compartida. Si None, crea una temporal.
    """
    if seen_urls is None:
        seen_urls = set()

    # Usar sesión stealth compartida o crear una temporal
    _owns_session = False
    if session is None:
        session = StealthSession(test_mode=True)
        _owns_session = True

    try:
        # v7.0: Usar StealthSession en lugar de requests.get() directo.
        # Esto garantiza: cloudscraper TLS fingerprint, delays lognormales,
        # rotación de UA consistente, y circuit breaker por dominio.
        response = session.get(rss_url, timeout=15)
        if response is None:
            logger.warning(f"Sin respuesta para feed RSS: {rss_url[:60]}")
            return []

        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'xml')

        articles = []
        skipped_seen = 0
        skipped_old = 0
        skipped_geo = 0

        for item in soup.find_all('item'):
            title_tag = item.find('title')
            description = item.find('description')
            link = item.find('link')
            pub_date = item.find('pubDate')
            content_encoded = item.find('content:encoded')

            title_text = title_tag.text.strip() if title_tag else ''
            if not title_text:
                continue

            enlace_text = link.text.strip() if link else ''

            # ── Filtro de URLs ya procesadas ────────────────
            if enlace_text and enlace_text in seen_urls:
                skipped_seen += 1
                continue

            # Extraer contenido: preferir content:encoded > description
            if content_encoded and content_encoded.text:
                desc_html = content_encoded.text
            elif description and description.text:
                desc_html = description.text
            else:
                desc_html = ''

            desc_text = BeautifulSoup(desc_html, 'html.parser').get_text(' ', strip=True)

            # Fecha
            if pub_date and pub_date.text.strip():
                try:
                    dt = parsedate_to_datetime(pub_date.text.strip())
                except Exception:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            # ── Filtro de antigüedad ────────────────────────
            if not _is_recent(dt.isoformat()):
                skipped_old += 1
                continue

            # ── Scoring de relevancia ───────────────────────
            rel = score_relevance(title_text, desc_text)
            # ── Filtro geográfico: solo México ─────────────
            if not _is_mexico_news(title_text, desc_text, enlace_text or rss_url):
                skipped_geo += 1
                continue

            # Registrar URL como procesada
            if enlace_text:
                seen_urls.add(enlace_text)

            articles.append({
                'titulo': title_text,
                'contenido': desc_text,
                'enlace': enlace_text,
                'fuente': rss_url,
                'fecha': dt.isoformat(),
                'score_feminicidio': rel['score_feminicidio'],
                'score_nna': rel['score_nna'],
                'score_compuesto': rel['score_compuesto'],
                'clasificacion': rel['clasificacion'],
                'menores_identificados': rel['menores_identificados'],
                'cluster': 0,
            })

        if skipped_seen or skipped_old or skipped_geo:
            logger.debug(
                f"RSS {rss_url[:50]}: {len(articles)} OK, "
                f"{skipped_seen} ya vistas, {skipped_old} antiguas, "
                f"{skipped_geo} no-México"
            )

        return articles

    except requests.exceptions.Timeout:
        logger.warning(f"Timeout en feed RSS: {rss_url[:60]}")
        return []
    except requests.exceptions.ConnectionError:
        logger.warning(f"Error de conexión al feed RSS: {rss_url[:60]}")
        return []
    except Exception as e:
        logger.warning(f"Error RSS ({rss_url[:60]}): {e}")
        return []
    finally:
        # Solo cerrar si creamos la sesión nosotros (evitar cerrar la compartida)
        if _owns_session:
            session.close_all()


def collect_all_news(keep_all: bool = False) -> pd.DataFrame:
    """
    Recolecta noticias de todas las fuentes activas.

    Prioridad:
      1. Si hay contexto Flask → lee fuentes desde la DB (incluye predeterminadas).
      2. Si no hay contexto   → fallback a config.RSS_FEEDS.

    v6.0 TT2 Mejoras:
      - Tracking de URLs ya procesadas (evita re-scrapping entre ciclos)
      - Logging detallado de fuentes exitosas/fallidas
      - Estadísticas de recolección por fuente

    v7.0 Mejoras (Pipeline unificado):
      - Crea UNA StealthSession compartida para todo el ciclo de recolección.
        Esto garantiza que:
        • Todas las peticiones (RSS y scraping) usan cloudscraper (TLS real)
        • El circuit breaker acumula estado entre fuentes del mismo dominio
        • Los delays lognormales se aplican consistentemente
      - Al finalizar, imprime el estado del circuit breaker para diagnóstico.

    Args:
        keep_all: Si True, conserva TODOS los artículos (para depuración).
                  Si False (default), descarta los "No relevante".
    Returns:
        DataFrame con noticias filtradas, scored y deduplicadas.
    """
    threshold = getattr(config, 'RELEVANCE_THRESHOLD', 0.25)
    all_articles = []
    seen_urls = _load_seen_urls()
    initial_seen = len(seen_urls)
    sources_ok = 0
    sources_error = 0

    # v7.0: Crear UNA sesión stealth compartida para todo el ciclo.
    # Beneficios:
    #   - cloudscraper reutiliza cookies/sesiones por dominio
    #   - Circuit breaker acumula estado entre fuentes del mismo dominio
    #   - Menos overhead de crear/destruir sesiones
    shared_session = StealthSession(test_mode=False)

    try:
        # ── Intentar obtener fuentes desde la DB ────────────────
        db_sources = _get_db_sources()

        if db_sources:
            print(f"  ── {len(db_sources)} fuentes activas desde DB ──")
            scraper = DynamicScraper(respect_robots=True, default_delay=2.0)

            for source in db_sources:
                src_label = f"{source['name']} ({source['source_type']})"
                print(f"  [{source['source_type'].upper()}] {src_label}")

                try:
                    if source['source_type'] == 'rss':
                        # v7.0: Pasar la sesión stealth compartida
                        articles = collect_news_from_rss(
                            source['url'], seen_urls, session=shared_session
                        )
                        for art in articles:
                            art['fuente'] = source['name']
                        all_articles.extend(articles)
                        _update_db_source_status(
                            source['id'], 'ok', len(articles)
                        )
                        sources_ok += 1
                        print(f"    → {len(articles)} artículos")
                    else:
                        raw_articles = scraper.scrape_source(
                            source['url'],
                            method=source['source_type'],
                            max_articles=30,
                        )
                        accepted = 0
                        for art in raw_articles:
                            enlace = art.get('enlace', source['url'])
                            if enlace in seen_urls:
                                continue
                            if not _is_mexico_news(
                                art.get('titulo', ''),
                                art.get('contenido', ''),
                                enlace,
                            ):
                                continue
                            rel = score_relevance(art['titulo'], art['contenido'])
                            art.update(rel)
                            art['fuente'] = source['name']
                            art.setdefault('cluster', 0)
                            all_articles.append(art)
                            if enlace:
                                seen_urls.add(enlace)
                            accepted += 1
                        _update_db_source_status(
                            source['id'], 'ok', accepted
                        )
                        sources_ok += 1
                        print(f"    → {accepted} artículos aceptados")

                except Exception as e:
                    sources_error += 1
                    logger.warning(f"Error scraping {source['name']}: {e}")
                    _update_db_source_status(
                        source['id'], 'error', 0, str(e)[:200]
                    )
        else:
            # ── Fallback: sin DB, usar config.RSS_FEEDS ─────────
            print("  ── Fuentes RSS desde config (sin contexto DB) ──")
            for feed in config.RSS_FEEDS:
                feed_label = feed[:70] + '…' if len(feed) > 70 else feed
                print(f"  RSS: {feed_label}")
                # v7.0: Pasar la sesión stealth compartida
                articles = collect_news_from_rss(
                    feed, seen_urls, session=shared_session
                )
                if articles:
                    sources_ok += 1
                all_articles.extend(articles)

        # v7.0: Diagnóstico del circuit breaker al final del ciclo
        cb_status = shared_session.get_circuit_breaker_status()
        if cb_status:
            open_circuits = {
                d: info for d, info in cb_status.items()
                if info['state'] != 'closed'
            }
            if open_circuits:
                print(f"  ⚠ Circuit breaker — dominios en cooldown: {list(open_circuits.keys())}")
                for domain, info in open_circuits.items():
                    logger.warning(
                        f"Circuit breaker {info['state'].upper()} para {domain}: "
                        f"{info['failures']} fallos consecutivos"
                    )

    finally:
        # Siempre cerrar la sesión compartida al terminar
        shared_session.close_all()

    # Guardar URLs procesadas a disco
    _save_seen_urls(seen_urls)
    new_urls = len(seen_urls) - initial_seen
    print(f"  URLs: {initial_seen} previas + {new_urls} nuevas = {len(seen_urls)} total")

    if not all_articles:
        print("  [!] No se recolectaron artículos de ninguna fuente.")
        print(f"  Fuentes OK: {sources_ok}, con error: {sources_error}")
        return pd.DataFrame()

    df = pd.DataFrame(all_articles)

    # ── 3. Deduplicación avanzada (cross-site) ──────────────
    print("  ── Deduplicación avanzada ──")
    pre_dedup = len(df)

    deduplicator = NewsDeduplicator(
        title_threshold=0.70,
        content_threshold=0.80,
        simhash_max_distance=8,
    )
    df = deduplicator.deduplicate(df, keep='best')

    post_dedup = len(df)
    removed = pre_dedup - post_dedup
    print(f"  Duplicados eliminados: {removed} ({pre_dedup} → {post_dedup})")

    total = len(df)
    if not keep_all:
        df = df[df['score_compuesto'] >= threshold].copy()

    relevant = len(df)
    nna = (df['menores_identificados'] == 'Si').sum() if not df.empty else 0

    print(f"  Total recolectadas: {total}")
    print(f"  Relevantes (score >= {threshold}): {relevant}")
    print(f"  Con mención a NNA: {nna}")

    # Ordenar por fecha descendente (más reciente primero)
    if not df.empty:
        try:
            df['_fecha_sort'] = pd.to_datetime(df['fecha'], errors='coerce')
            df = df.sort_values(
                '_fecha_sort', ascending=False, na_position='last'
            ).reset_index(drop=True)
            df = df.drop(columns=['_fecha_sort'])
        except Exception:
            df = df.sort_values('score_compuesto', ascending=False).reset_index(drop=True)

    return df


def _get_db_sources() -> list[dict]:
    """
    Obtiene fuentes activas de la base de datos.
    Retorna lista vacía si la DB no está disponible.
    """
    try:
        from app.models import NewsSource
        from flask import current_app
        # Solo funciona si hay un app context activo
        if current_app:
            sources = NewsSource.query.filter_by(is_active=True).all()
            return [
                {
                    'id': s.id,
                    'name': s.name,
                    'url': s.url,
                    'source_type': s.source_type,
                }
                for s in sources
            ]
    except Exception:
        # Si no hay Flask context (ejecución standalone), ignorar
        pass
    return []


def _update_db_source_status(
    source_id: int,
    status: str,
    articles_found: int,
    error: str | None = None,
):
    """Actualiza el estado de una fuente en la DB después del scraping."""
    try:
        from app.models import db, NewsSource
        source = db.session.get(NewsSource, source_id)
        if source:
            source.last_status = status
            source.last_scraped = datetime.now(timezone.utc)
            source.articles_found = articles_found
            source.last_error = error
            db.session.commit()
    except Exception:
        pass


def detect_children_mentions(text: str) -> str:
    """
    Detecta menciones de NNA en el texto (función legacy).
    Usa el nuevo scoring interno para consistencia.
    """
    if not isinstance(text, str):
        return 'No'
    rel = score_relevance('', text)
    return rel['menores_identificados']
