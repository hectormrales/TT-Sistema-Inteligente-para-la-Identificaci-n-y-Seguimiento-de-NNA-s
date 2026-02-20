# src/collection/collector.py — Recolector de noticias con scoring de relevancia
"""
Recolecta noticias desde feeds RSS, fuentes dinámicas (DB) y web scraping:
  • Eje 1 – Feminicidio: ¿la noticia habla de feminicidio / violencia feminicida?
  • Eje 2 – NNA: ¿menciona víctimas indirectas (niños, niñas, adolescentes)?

Incluye deduplicación avanzada cross-site (v4.0).
Solo se conservan noticias que superan el umbral de relevancia compuesto.
"""

import re
import logging
from datetime import datetime, timezone
from unicodedata import normalize
from typing import Tuple

import requests
import pandas as pd
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime

import config
from src.collection.scraper import DynamicScraper
from src.analysis.dedup import NewsDeduplicator

logger = logging.getLogger(__name__)

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
    # Estados
    r'\baguascalientes\b', r'\bbaja\s+california\b', r'\bcampeche\b',
    r'\bchiapas\b', r'\bchihuahua\b', r'\bcoahuila\b', r'\bcolima\b',
    r'\bdurango\b', r'\bguanajuato\b', r'\bguerrero\b', r'\bhidalgo\b',
    r'\bjalisco\b', r'\bmichoacán\b', r'\bmorelos\b', r'\bnayarit\b',
    r'\bnuevo\s+le[oó]n\b', r'\boaxaca\b', r'\bpuebla\b', r'\bquer[eé]taro\b',
    r'\bquintana\s+roo\b', r'\bsan\s+luis\s+potos[ií]\b', r'\bsinaloa\b',
    r'\bsonora\b', r'\btabasco\b', r'\btamaulipas\b', r'\btlaxcala\b',
    r'\bveracruz\b', r'\byucat[aá]n\b', r'\bzacatecas\b',
    r'\bestado\s+de\s+m[eé]xico\b', r'\bcdmx\b', r'\bciudad\s+de\s+m[eé]xico\b',
    # Ciudades principales
    r'\bguadalajara\b', r'\bmonterrey\b', r'\btijuana\b', r'\bjuárez\b',
    r'\bju[aá]rez\b', r'\ble[oó]n\b', r'\becatepec\b', r'\bneza\b',
    r'\btoluca\b', r'\bculiac[aá]n\b', r'\bcancún\b', r'\bacapulco\b',
    r'\bmerida\b', r'\bm[eé]rida\b', r'\bvillahermosa\b', r'\bhermosillo\b',
    r'\bsaltillo\b', r'\btuxtla\b', r'\bxalapa\b', r'\btorreón\b',
    r'\bmatamoros\b', r'\breynosa\b', r'\bplaya\s+del\s+carmen\b',
    r'\biztapalapa\b', r'\bnaucalpan\b', r'\btlalnepantla\b',
    # Instituciones mexicanas
    r'\bfisca[il]ía\b', r'\bfgr\b', r'\bfgj\b', r'\bsemefo\b',
    r'\bDIF\b', r'\bSEP\b', r'\bIMSS\b', r'\bcndh\b',
    r'\bconavim\b', r'\binmujeres\b', r'\bsspc\b',
    r'\bguardia\s+nacional\b', r'\bprocuradur[ií]a\b',
    r'\balerta\s+de\s+(?:violencia\s+de\s+)?g[eé]nero\b',
    r'\bcódigo?\s+rojo\b', r'\bministerio\s+p[uú]blico\b',
]

# Indicadores de que la noticia NO es de México
NON_MEXICO_INDICATORS = [
    r'\bargentina\b', r'\bbuenos\s+aires\b', r'\bcolombia\b', r'\bbogot[aá]\b',
    r'\bper[uú]\b', r'\blima\b', r'\bchile\b', r'\bsantiago\b',
    r'\bvenezuela\b', r'\bcaracas\b', r'\becuador\b', r'\bquito\b',
    r'\bbolivia\b', r'\bla\s+paz\b', r'\bparaguay\b', r'\basunci[oó]n\b',
    r'\buruguay\b', r'\bmontevideo\b', r'\bbrasil\b', r'\bsão\s+paulo\b',
    r'\bespaña\b', r'\bmadrid\b', r'\bbarcelona\b',
    r'\bestados\s+unidos\b', r'\bnew\s+york\b', r'\bwashington\b',
    r'\bel\s+salvador\b', r'\bguatemala\b', r'\bhonduras\b',
    r'\bnicaragua\b', r'\bcosta\s+rica\b', r'\bpanam[aá]\b',
    r'\brepública\s+dominicana\b', r'\bcuba\b', r'\bhaití\b',
    r'\bpuerto\s+rico\b',
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
    'news.google.com',  # Los queries de Google News ya son de México
}


def _is_mexico_news(title: str, content: str, source_url: str = '') -> bool:
    """
    Determina si una noticia es de México.
    
    Lógica:
      1. Si la fuente es un dominio mexicano conocido → True
      2. Si el texto tiene indicadores de otro país → False
      3. Si el texto tiene indicadores de México → True
      4. Si la fuente tiene dominio .mx → True
      5. Sin indicadores claros → True (beneficio de la duda para fuentes configuradas)
    """
    # 1. Dominio mexicano conocido
    if source_url:
        from urllib.parse import urlparse
        domain = urlparse(source_url).netloc.replace('www.', '')
        if domain in MEXICAN_DOMAINS or domain.endswith('.mx'):
            return True
    
    text_combined = f"{title} {content}".lower()
    
    # 2. Indicadores de otro país (descartar)
    non_mexico_count = 0
    for pattern in NON_MEXICO_INDICATORS:
        if re.search(pattern, text_combined, re.IGNORECASE):
            non_mexico_count += 1
    
    # 3. Indicadores de México
    mexico_count = 0
    for pattern in MEXICO_INDICATORS:
        if re.search(pattern, text_combined, re.IGNORECASE):
            mexico_count += 1
    
    # Si hay más indicadores de otro país que de México, descartar
    if non_mexico_count > 0 and mexico_count == 0:
        return False
    
    if non_mexico_count > mexico_count:
        return False
    
    # Si hay al menos un indicador de México, aceptar
    if mexico_count > 0:
        return True
    
    # Sin indicadores claros: aceptar si es de dominio .mx
    if source_url:
        domain = urlparse(source_url).netloc
        if '.mx' in domain:
            return True
    
    # Beneficio de la duda para fuentes configuradas manualmente
    return True


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

    # Clasificación — v4.1: Umbrales ajustados para capturar más noticias relevantes
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

def collect_news_from_rss(rss_url: str) -> list[dict]:
    """Recolecta artículos desde un feed RSS individual."""
    try:
        headers = getattr(config, 'HTTP_HEADERS', {})
        response = requests.get(rss_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'xml')

        articles = []
        for item in soup.find_all('item'):
            title_tag = item.find('title')
            description = item.find('description')
            link = item.find('link')
            pub_date = item.find('pubDate')
            content_encoded = item.find('content:encoded')

            title_text = title_tag.text.strip() if title_tag else ''
            if not title_text:
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

            # ── Scoring de relevancia ───────────────────────
            rel = score_relevance(title_text, desc_text)
            # ── Filtro geográfico: solo México ─────────────
            enlace_text = link.text.strip() if link else rss_url
            if not _is_mexico_news(title_text, desc_text, enlace_text):
                continue
            articles.append({
                'titulo': title_text,
                'contenido': desc_text,
                'enlace': link.text.strip() if link else '',
                'fuente': rss_url,
                'fecha': dt.isoformat(),
                'score_feminicidio': rel['score_feminicidio'],
                'score_nna': rel['score_nna'],
                'score_compuesto': rel['score_compuesto'],
                'clasificacion': rel['clasificacion'],
                'menores_identificados': rel['menores_identificados'],
                'cluster': 0,
            })

        return articles

    except Exception as e:
        print(f"  [WARN] Error RSS ({rss_url[:60]}…): {e}")
        return []


def collect_all_news(keep_all: bool = False) -> pd.DataFrame:
    """
    Recolecta noticias de todas las fuentes activas.

    Prioridad:
      1. Si hay contexto Flask → lee fuentes desde la DB (incluye predeterminadas).
      2. Si no hay contexto   → fallback a config.RSS_FEEDS.

    Args:
        keep_all: Si True, conserva TODOS los artículos (para depuración).
                  Si False (default), descarta los "No relevante".
    Returns:
        DataFrame con noticias filtradas, scored y deduplicadas.
    """
    threshold = getattr(config, 'RELEVANCE_THRESHOLD', 0.25)
    all_articles = []

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
                    # Usar el recolector RSS nativo (más rápido)
                    articles = collect_news_from_rss(source['url'])
                    # Sobreescribir fuente con nombre legible
                    for art in articles:
                        art['fuente'] = source['name']
                    all_articles.extend(articles)
                    _update_db_source_status(
                        source['id'], 'ok', len(articles)
                    )
                    print(f"    → {len(articles)} artículos")
                else:
                    # Usar scraper dinámico para HTML/sitemap/auto
                    raw_articles = scraper.scrape_source(
                        source['url'],
                        method=source['source_type'],
                        max_articles=30,
                    )
                    for art in raw_articles:
                        # Filtro geográfico: solo México
                        if not _is_mexico_news(
                            art.get('titulo', ''),
                            art.get('contenido', ''),
                            art.get('enlace', source['url']),
                        ):
                            continue
                        rel = score_relevance(art['titulo'], art['contenido'])
                        art.update(rel)
                        art['fuente'] = source['name']
                        art.setdefault('cluster', 0)
                        all_articles.append(art)
                    _update_db_source_status(
                        source['id'], 'ok', len(raw_articles)
                    )
                    print(f"    → {len(raw_articles)} artículos")

            except Exception as e:
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
            all_articles.extend(collect_news_from_rss(feed))

    if not all_articles:
        print("  [!] No se recolectaron artículos de ninguna fuente.")
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
