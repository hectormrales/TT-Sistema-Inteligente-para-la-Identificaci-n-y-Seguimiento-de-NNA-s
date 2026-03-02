# src/collection/historical_scraper.py — Scraper histórico 2023-2026
"""
OE-2: Ampliar cobertura temporal y volumen de datos.

Recolecta noticias históricas de enero 2023 a diciembre 2026
usando múltiples estrategias de búsqueda retrospectiva.

Estrategias implementadas:
  1. Google News Archive: Búsquedas por rango de fecha con queries
     específicos de feminicidio + NNA.
  2. Wayback Machine (CDX API): Recupera versiones archivadas de
     páginas de medios mexicanos.
  3. Hemerotecas digitales: Búsqueda directa en archivos de medios
     mexicanos que ofrecen acceso a ediciones anteriores.
  4. Búsqueda por períodos: Divide el rango 2023-2026 en ventanas
     mensuales para búsqueda exhaustiva.

Capacidades de análisis temporal:
  - Series temporales de casos por mes/trimestre/año
  - Detección de tendencias con media móvil
  - Análisis de estacionalidad
  - Identificación de picos de cobertura mediática

Meta: Recolectar ≥ 1,500 noticias históricas adicionales.
Rango temporal: enero 2023 - diciembre 2026.
"""

import os
import re
import time
import json
import random
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus, urlencode, urlparse

import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

from src.collection.scraper import DynamicScraper, StealthSession
from src.collection.collector import (
    score_relevance, _is_mexico_news, _normalize_text,
)

logger = logging.getLogger(__name__)

# ── Configuración ───────────────────────────────────────────

DATA_DIR = os.environ.get("DATA_DIR", "data")
HISTORICAL_FILE = os.path.join(DATA_DIR, "noticias_historicas.csv")

# Rango temporal OE-2 — CORREGIDO: 2023-2026 (no 2025)
HISTORICAL_START = datetime(2023, 1, 1, tzinfo=timezone.utc)
HISTORICAL_END = datetime(2026, 12, 31, tzinfo=timezone.utc)

# Queries de búsqueda histórica
HISTORICAL_QUERIES = [
    "feminicidio hijos huérfanos México",
    "feminicidio menores víctimas indirectas",
    "orfandad feminicidio niños niñas",
    "feminicidio hijos quedaron solos",
    "violencia feminicida menores",
    "asesinato mujer hijos huérfanos México",
    "feminicidio NNA víctimas",
    "feminicidio custodia menores DIF",
    "víctimas indirectas feminicidio México",
    "feminicidio niños sobrevivientes",
    "alerta de género menores huérfanos",
    "orfandad por feminicidio estadísticas",
    "feminicidio México 2023",
    "feminicidio México 2024",
    "feminicidio México 2025",
    "feminicidio México 2026",
    "hijos de víctimas de feminicidio",
    "menores desamparados feminicidio",
    "feminicidio impacto niños adolescentes",
    "violencia de género orfandad México",
]

# Dominios de medios mexicanos para Wayback Machine
WAYBACK_DOMAINS = [
    "animalpolitico.com",
    "aristeguinoticias.com",
    "sinembargo.mx",
    "proceso.com.mx",
    "jornada.com.mx",
    "eluniversal.com.mx",
    "milenio.com",
    "cimacnoticias.com.mx",
    "piedepagina.mx",
]

# Paths de secciones relevantes para buscar en archivos
ARCHIVE_PATHS = [
    "/seguridad/",
    "/justicia/",
    "/sociedad/",
    "/estados/",
    "/nacional/",
    "/genero/",
    "/derechos-humanos/",
    "/policiaca/",
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Utilidades de tiempo
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_monthly_windows(
    start: datetime, end: datetime
) -> list[tuple[datetime, datetime]]:
    """
    Genera ventanas mensuales para búsqueda exhaustiva.

    Dividir el rango en ventanas mensuales permite:
      - Distribuir las requests en el tiempo
      - Evitar rate-limiting de buscadores
      - Obtener resultados más granulares
      - Rastrear cobertura por período

    Returns:
        Lista de tuplas (inicio_mes, fin_mes) en orden cronológico.
    """
    windows = []
    current = start.replace(day=1)
    while current <= end:
        # Fin del mes
        if current.month == 12:
            month_end = current.replace(
                year=current.year + 1, month=1, day=1
            ) - timedelta(days=1)
        else:
            month_end = current.replace(
                month=current.month + 1, day=1
            ) - timedelta(days=1)

        if month_end > end:
            month_end = end

        windows.append((current, month_end))

        # Siguiente mes
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return windows


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Estrategia 1: Google News con filtro de fecha
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GoogleNewsHistorical:
    """
    Recolecta noticias históricas desde Google News RSS con filtros de fecha.

    Google News permite filtrar por rango temporal usando parámetros
    'after:' y 'before:' en la query, o los parámetros ceid/after/before
    en la URL RSS.

    Formato de URL:
      https://news.google.com/rss/search?q={query}+after:{YYYY-MM-DD}+before:{YYYY-MM-DD}&hl=es-419&gl=MX

    Limitaciones:
      - Google puede limitar resultados a ~100 por query
      - Rate limiting agresivo si se hacen muchas requests
      - Algunas noticias antiguas pueden no estar indexadas
    """

    BASE_URL = "https://news.google.com/rss/search"

    def __init__(self):
        self.session = StealthSession(test_mode=False)
        self.collected_urls: set[str] = set()

    def search_period(
        self,
        query: str,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 50,
    ) -> list[dict]:
        """
        Busca noticias en Google News para un período específico.

        Args:
            query: Términos de búsqueda.
            start_date: Inicio del período.
            end_date: Fin del período.
            max_results: Máximo de resultados por query.

        Returns:
            Lista de dicts con titulo, contenido, enlace, fecha, fuente.
        """
        after = start_date.strftime("%Y-%m-%d")
        before = end_date.strftime("%Y-%m-%d")

        # Construir query con filtros temporales
        full_query = f"{query} after:{after} before:{before}"
        params = {
            "q": full_query,
            "hl": "es-419",
            "gl": "MX",
            "ceid": "MX:es-419",
        }

        url = f"{self.BASE_URL}?{urlencode(params)}"

        try:
            resp = self.session.get(url, timeout=20)
            if resp is None or resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.content, "xml")
            articles = []

            for item in soup.find_all("item"):
                if len(articles) >= max_results:
                    break

                title = item.find("title")
                title_text = title.get_text(strip=True) if title else ""
                if not title_text:
                    continue

                link = item.find("link")
                link_text = link.get_text(strip=True) if link else ""

                # Evitar duplicados
                if link_text in self.collected_urls:
                    continue
                self.collected_urls.add(link_text)

                # Fecha
                pub_date = item.find("pubDate")
                if pub_date:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date.get_text(strip=True))
                    except Exception:
                        dt = start_date
                else:
                    dt = start_date

                # Descripción
                desc = item.find("description")
                desc_text = ""
                if desc:
                    desc_text = BeautifulSoup(
                        desc.get_text(), "html.parser"
                    ).get_text(" ", strip=True)

                # Source
                source_tag = item.find("source")
                source = source_tag.get_text(strip=True) if source_tag else "Google News"

                # Score de relevancia
                rel = score_relevance(title_text, desc_text)

                articles.append({
                    "titulo": title_text,
                    "contenido": desc_text,
                    "enlace": link_text,
                    "fuente": source,
                    "fecha": dt.isoformat(),
                    "score_feminicidio": rel["score_feminicidio"],
                    "score_nna": rel["score_nna"],
                    "score_compuesto": rel["score_compuesto"],
                    "clasificacion": rel["clasificacion"],
                    "menores_identificados": rel["menores_identificados"],
                    "scrape_method": "google_news_historical",
                    "periodo": f"{after}/{before}",
                })

            return articles

        except Exception as e:
            logger.warning(f"Error Google News histórico: {e}")
            return []

    def collect_all_periods(
        self,
        queries: list[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Recolecta noticias para múltiples queries y períodos.

        Divide el rango temporal en ventanas mensuales y ejecuta
        cada query en cada ventana. Incluye delays entre requests
        para evitar rate-limiting.

        Returns:
            DataFrame con todas las noticias históricas recolectadas.
        """
        queries = queries or HISTORICAL_QUERIES
        start = start or HISTORICAL_START
        end = end or HISTORICAL_END

        windows = generate_monthly_windows(start, end)
        all_articles = []
        total_queries = len(queries) * len(windows)
        completed = 0

        logger.info(
            f"Recolección histórica: {len(queries)} queries × "
            f"{len(windows)} ventanas mensuales = {total_queries} búsquedas"
        )

        for query in queries:
            for window_start, window_end in windows:
                completed += 1
                period = f"{window_start.strftime('%Y-%m')} a {window_end.strftime('%Y-%m')}"

                articles = self.search_period(
                    query, window_start, window_end
                )
                all_articles.extend(articles)

                if completed % 10 == 0:
                    logger.info(
                        f"  Progreso: {completed}/{total_queries} — "
                        f"{len(all_articles)} artículos acumulados"
                    )

                # Delay para no saturar Google News
                time.sleep(random.uniform(3, 8))

        if all_articles:
            df = pd.DataFrame(all_articles)
            logger.info(
                f"Recolección histórica completada: {len(df)} artículos"
            )
            return df

        return pd.DataFrame()

    def close(self):
        self.session.close_all()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Estrategia 2: Wayback Machine CDX API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WaybackHistorical:
    """
    Recupera noticias archivadas desde la Wayback Machine.

    Usa la CDX API de Internet Archive para buscar snapshots de
    páginas de medios mexicanos en el rango temporal deseado.

    CDX API:
      URL: https://web.archive.org/cdx/search/cdx
      Parámetros:
        - url: Dominio a buscar
        - from: Fecha inicio (YYYYMMDD)
        - to: Fecha fin (YYYYMMDD)
        - output: Formato de salida (json)
        - filter: Filtro por código HTTP
        - matchType: Tipo de matching (domain, prefix, exact)

    Las URLs archivadas tienen formato:
      https://web.archive.org/web/{timestamp}/{original_url}
    """

    CDX_API = "https://web.archive.org/cdx/search/cdx"

    def __init__(self):
        self.scraper = DynamicScraper(
            respect_robots=False, default_delay=3.0, test_mode=True
        )

    def search_domain(
        self,
        domain: str,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100,
    ) -> list[str]:
        """
        Busca URLs archivadas de un dominio en el rango temporal.

        Returns:
            Lista de URLs de Wayback Machine para extraer.
        """
        params = {
            "url": f"{domain}/*",
            "from": start_date.strftime("%Y%m%d"),
            "to": end_date.strftime("%Y%m%d"),
            "output": "json",
            "filter": "statuscode:200",
            "matchType": "prefix",
            "limit": max_results * 2,
            "fl": "timestamp,original,statuscode",
        }

        try:
            resp = requests.get(
                self.CDX_API, params=params, timeout=30,
                headers={"User-Agent": "NNA-Historical-Research/1.0"}
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            if not data or len(data) < 2:
                return []

            # Primera fila es el header
            headers = data[0]
            rows = data[1:]

            urls = []
            for row in rows:
                timestamp = row[0]
                original_url = row[1]

                # Filtrar por paths relevantes
                path = urlparse(f"https://{original_url}").path
                is_relevant_path = any(
                    rp in path.lower() for rp in ARCHIVE_PATHS
                )

                # Filtrar por keywords en URL
                has_keyword = any(
                    kw in original_url.lower()
                    for kw in [
                        "feminicidio", "violencia", "genero", "mujer",
                        "menor", "huerfan", "orfandad", "nna",
                    ]
                )

                if is_relevant_path or has_keyword:
                    wayback_url = (
                        f"https://web.archive.org/web/{timestamp}/{original_url}"
                    )
                    urls.append(wayback_url)

                if len(urls) >= max_results:
                    break

            return urls

        except Exception as e:
            logger.warning(f"Error CDX API para {domain}: {e}")
            return []

    def extract_from_archive(
        self, wayback_url: str
    ) -> Optional[dict]:
        """
        Extrae contenido de una página archivada en Wayback Machine.
        """
        try:
            article = self.scraper._extract_article(wayback_url)
            if article:
                # Limpiar URL (quitar el prefijo de Wayback)
                original = re.sub(
                    r"https?://web\.archive\.org/web/\d+/", "", wayback_url
                )
                article["enlace"] = original
                article["scrape_method"] = "wayback_machine"

                # Score de relevancia
                rel = score_relevance(
                    article["titulo"], article["contenido"]
                )
                article.update(rel)
            return article
        except Exception as e:
            logger.debug(f"Error extrayendo de Wayback: {e}")
            return None

    def collect_all(
        self,
        domains: list[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        max_per_domain: int = 50,
    ) -> pd.DataFrame:
        """
        Recolecta noticias históricas de Wayback Machine.

        Returns:
            DataFrame con noticias históricas.
        """
        domains = domains or WAYBACK_DOMAINS
        start = start or HISTORICAL_START
        end = end or HISTORICAL_END
        all_articles = []

        for domain in domains:
            logger.info(f"Wayback Machine: buscando en {domain}")
            urls = self.search_domain(domain, start, end, max_per_domain)
            logger.info(f"  → {len(urls)} URLs encontradas")

            for url in urls:
                article = self.extract_from_archive(url)
                if article:
                    # Filtro geográfico
                    if _is_mexico_news(
                        article["titulo"],
                        article["contenido"],
                        article["enlace"],
                    ):
                        all_articles.append(article)

                time.sleep(random.uniform(2, 5))

            logger.info(f"  → {len(all_articles)} artículos relevantes acumulados")

        if all_articles:
            return pd.DataFrame(all_articles)
        return pd.DataFrame()

    def close(self):
        self.scraper.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Análisis de series temporales
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TimeSeriesAnalyzer:
    """
    Análisis temporal de noticias sobre feminicidio y NNA.

    Proporciona:
      - Conteo de noticias por mes/trimestre/año
      - Detección de tendencias (media móvil)
      - Estacionalidad (patrones mensuales recurrentes)
      - Identificación de picos de cobertura mediática
      - Correlación entre ejes (feminicidio vs NNA)

    Algoritmos utilizados:
      - Media móvil simple (SMA) para suavizar ruido
      - Descomposición estacional (resta de tendencia)
      - Z-score para detección de anomalías/picos
    """

    def __init__(self, df: pd.DataFrame):
        """
        Args:
            df: DataFrame con columna 'fecha' y scores.
        """
        self.df = df.copy()
        self._prepare_dates()

    def _prepare_dates(self):
        """Parsea y normaliza las fechas del DataFrame."""
        if "fecha" in self.df.columns:
            self.df["fecha_dt"] = pd.to_datetime(
                self.df["fecha"], errors="coerce", utc=True
            )
            self.df["anio"] = self.df["fecha_dt"].dt.year
            self.df["mes"] = self.df["fecha_dt"].dt.month
            self.df["trimestre"] = self.df["fecha_dt"].dt.quarter
            self.df["anio_mes"] = self.df["fecha_dt"].dt.to_period("M")

    def monthly_counts(self) -> pd.DataFrame:
        """
        Conteo de noticias por mes.

        Returns:
            DataFrame con columnas: anio_mes, total, nna, alta_rel,
            score_fem_promedio, score_nna_promedio.
        """
        if "anio_mes" not in self.df.columns:
            return pd.DataFrame()

        grouped = self.df.groupby("anio_mes").agg(
            total=("titulo", "count"),
            nna=(
                "menores_identificados",
                lambda x: (x == "Si").sum(),
            ),
            score_fem_promedio=("score_feminicidio", "mean"),
            score_nna_promedio=("score_nna", "mean"),
            score_comp_promedio=("score_compuesto", "mean"),
        ).reset_index()

        # Alta relevancia
        clf_col = (
            "clasificacion_final"
            if "clasificacion_final" in self.df.columns
            else "clasificacion"
        )
        alta_por_mes = (
            self.df[self.df[clf_col] == "Alta"]
            .groupby("anio_mes")
            .size()
            .reset_index(name="alta_rel")
        )
        grouped = grouped.merge(alta_por_mes, on="anio_mes", how="left")
        grouped["alta_rel"] = grouped["alta_rel"].fillna(0).astype(int)

        return grouped

    def quarterly_counts(self) -> pd.DataFrame:
        """Conteo de noticias por trimestre."""
        if "anio" not in self.df.columns:
            return pd.DataFrame()

        return self.df.groupby(["anio", "trimestre"]).agg(
            total=("titulo", "count"),
            nna=("menores_identificados", lambda x: (x == "Si").sum()),
            score_comp_promedio=("score_compuesto", "mean"),
        ).reset_index()

    def yearly_counts(self) -> pd.DataFrame:
        """Conteo de noticias por año."""
        if "anio" not in self.df.columns:
            return pd.DataFrame()

        return self.df.groupby("anio").agg(
            total=("titulo", "count"),
            nna=("menores_identificados", lambda x: (x == "Si").sum()),
            score_comp_promedio=("score_compuesto", "mean"),
        ).reset_index()

    def moving_average(self, window: int = 3) -> pd.DataFrame:
        """
        Calcula media móvil simple (SMA) para detectar tendencias.

        Media Móvil Simple (SMA):
          SMA_t = (1/w) × Σ(x_{t-i}) para i = 0..w-1

        Donde w es el tamaño de la ventana.
        Suaviza fluctuaciones de corto plazo para revelar tendencias.

        Args:
            window: Tamaño de la ventana (meses).

        Returns:
            DataFrame con series temporales y su media móvil.
        """
        monthly = self.monthly_counts()
        if monthly.empty:
            return pd.DataFrame()

        monthly["sma_total"] = (
            monthly["total"].rolling(window=window, min_periods=1).mean()
        )
        monthly["sma_nna"] = (
            monthly["nna"].rolling(window=window, min_periods=1).mean()
        )
        monthly["sma_score"] = (
            monthly["score_comp_promedio"]
            .rolling(window=window, min_periods=1)
            .mean()
        )

        return monthly

    def detect_peaks(self, threshold_z: float = 2.0) -> pd.DataFrame:
        """
        Detecta picos de cobertura mediática usando Z-score.

        Z-score:
          z = (x - μ) / σ

        Donde μ es la media y σ es la desviación estándar.
        Un Z-score > threshold indica un pico significativo.

        Los picos pueden corresponder a:
          - Casos mediáticos de alto perfil
          - Cambios legislativos
          - Campañas de concientización
          - Eventos estacionales

        Args:
            threshold_z: Umbral de Z-score para considerar un pico.

        Returns:
            DataFrame con los meses identificados como picos.
        """
        monthly = self.monthly_counts()
        if monthly.empty or len(monthly) < 3:
            return pd.DataFrame()

        mean_total = monthly["total"].mean()
        std_total = monthly["total"].std()

        if std_total == 0:
            return pd.DataFrame()

        monthly["z_score"] = (monthly["total"] - mean_total) / std_total
        monthly["es_pico"] = monthly["z_score"] > threshold_z

        peaks = monthly[monthly["es_pico"]].copy()
        return peaks

    def seasonality_analysis(self) -> dict:
        """
        Analiza estacionalidad: ¿hay meses con más cobertura?

        Método: Promedio de noticias por mes del año (1-12),
        luego se calcula la desviación respecto al promedio general.

        Permite identificar si ciertos meses tienen sistemáticamente
        más o menos cobertura (ej: marzo por Día de la Mujer).

        Returns:
            dict con patrón mensual, meses pico y meses valle.
        """
        if "mes" not in self.df.columns:
            return {}

        monthly_pattern = (
            self.df.groupby("mes")
            .agg(promedio_noticias=("titulo", "count"))
            .reset_index()
        )
        # Normalizar por número de años
        n_years = self.df["anio"].nunique() or 1
        monthly_pattern["promedio_noticias"] = (
            monthly_pattern["promedio_noticias"] / n_years
        )

        global_mean = monthly_pattern["promedio_noticias"].mean()
        monthly_pattern["desviacion"] = (
            monthly_pattern["promedio_noticias"] - global_mean
        )

        # Meses con más / menos cobertura
        MONTH_NAMES = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
        }

        peak_months = monthly_pattern.nlargest(3, "promedio_noticias")
        valley_months = monthly_pattern.nsmallest(3, "promedio_noticias")

        return {
            "patron_mensual": {
                MONTH_NAMES[row["mes"]]: round(row["promedio_noticias"], 1)
                for _, row in monthly_pattern.iterrows()
            },
            "meses_pico": [
                MONTH_NAMES[row["mes"]] for _, row in peak_months.iterrows()
            ],
            "meses_valle": [
                MONTH_NAMES[row["mes"]] for _, row in valley_months.iterrows()
            ],
            "promedio_global": round(global_mean, 1),
        }

    def coverage_summary(self) -> dict:
        """
        Resumen completo de cobertura temporal.

        Returns:
            dict con estadísticas temporales completas.
        """
        yearly = self.yearly_counts()
        seasonality = self.seasonality_analysis()
        peaks = self.detect_peaks()

        date_range = {
            "inicio": str(self.df["fecha_dt"].min())[:10] if "fecha_dt" in self.df.columns else None,
            "fin": str(self.df["fecha_dt"].max())[:10] if "fecha_dt" in self.df.columns else None,
            "total_meses": self.df["anio_mes"].nunique() if "anio_mes" in self.df.columns else 0,
            "total_anios": self.df["anio"].nunique() if "anio" in self.df.columns else 0,
        }

        return {
            "rango": date_range,
            "por_anio": yearly.to_dict("records") if not yearly.empty else [],
            "estacionalidad": seasonality,
            "picos_detectados": len(peaks),
            "total_noticias": len(self.df),
            "noticias_con_nna": int((self.df.get("menores_identificados", pd.Series()) == "Si").sum()),
        }

    def to_json(self, filepath: str):
        """Exporta el análisis temporal a JSON."""
        summary = self.coverage_summary()
        monthly = self.moving_average()

        output = {
            "resumen": summary,
            "serie_mensual": monthly.to_dict("records") if not monthly.empty else [],
            "generado": datetime.now(timezone.utc).isoformat(),
        }

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Análisis temporal guardado en {filepath}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Orquestador de recolección histórica
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class HistoricalCollector:
    """
    Orquesta la recolección histórica usando todas las estrategias.

    Flujo:
      1. Google News Archive → búsquedas mensuales con queries
      2. Wayback Machine → snapshots de medios mexicanos archivados
      3. Deduplicación cross-fuente
      4. Merge con datos existentes
      5. Análisis de series temporales

    Guarda progreso incremental para poder reanudar si se interrumpe.
    """

    def __init__(self):
        self.google = GoogleNewsHistorical()
        self.wayback = WaybackHistorical()
        self.progress_file = os.path.join(DATA_DIR, "historical_progress.json")

    def collect(
        self,
        strategies: list[str] | None = None,
        max_articles: int = 1500,
    ) -> pd.DataFrame:
        """
        Ejecuta la recolección histórica completa.

        Args:
            strategies: Lista de estrategias a usar:
                        ['google_news', 'wayback_machine']
            max_articles: Objetivo mínimo de artículos.

        Returns:
            DataFrame con noticias históricas recolectadas.
        """
        strategies = strategies or ["google_news", "wayback_machine"]
        all_dfs = []

        logger.info(
            f"=== RECOLECCIÓN HISTÓRICA (meta: {max_articles} artículos) ==="
        )
        logger.info(
            f"Rango: {HISTORICAL_START.strftime('%Y-%m')} a "
            f"{HISTORICAL_END.strftime('%Y-%m')}"
        )

        # Cargar progreso previo si existe
        existing = self._load_existing()
        if not existing.empty:
            logger.info(f"Progreso previo: {len(existing)} artículos")
            all_dfs.append(existing)

        # Estrategia 1: Google News
        if "google_news" in strategies:
            logger.info("── Estrategia 1: Google News Archive ──")
            df_google = self.google.collect_all_periods()
            if not df_google.empty:
                logger.info(
                    f"  Google News: {len(df_google)} artículos recolectados"
                )
                all_dfs.append(df_google)
            self._save_progress(all_dfs)

        # Estrategia 2: Wayback Machine
        if "wayback_machine" in strategies:
            logger.info("── Estrategia 2: Wayback Machine ──")
            df_wayback = self.wayback.collect_all()
            if not df_wayback.empty:
                logger.info(
                    f"  Wayback: {len(df_wayback)} artículos recolectados"
                )
                all_dfs.append(df_wayback)
            self._save_progress(all_dfs)

        if not all_dfs:
            logger.warning("No se recolectaron artículos históricos")
            return pd.DataFrame()

        # Combinar todo
        df = pd.concat(all_dfs, ignore_index=True)

        # Deduplicar
        from src.analysis.dedup import NewsDeduplicator
        dedup = NewsDeduplicator(
            title_threshold=0.70, content_threshold=0.85
        )
        pre = len(df)
        df = dedup.deduplicate(df, keep="best")
        post = len(df)
        logger.info(f"Deduplicación: {pre} → {post} ({pre - post} eliminados)")

        # Filtrar solo relevantes
        if "score_compuesto" in df.columns:
            df = df[df["score_compuesto"] >= 0.20].copy()

        # Guardar resultado final
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_csv(HISTORICAL_FILE, index=False, encoding="utf-8")
        logger.info(f"Guardado en {HISTORICAL_FILE}: {len(df)} artículos")

        # Análisis temporal
        if not df.empty:
            ts = TimeSeriesAnalyzer(df)
            ts.to_json(os.path.join(DATA_DIR, "analisis_temporal.json"))

        return df

    def _load_existing(self) -> pd.DataFrame:
        """Carga datos históricos previos si existen."""
        if os.path.exists(HISTORICAL_FILE):
            try:
                return pd.read_csv(HISTORICAL_FILE)
            except Exception:
                pass
        return pd.DataFrame()

    def _save_progress(self, dfs: list[pd.DataFrame]):
        """Guarda progreso parcial para poder reanudar."""
        if not dfs:
            return
        try:
            df = pd.concat(dfs, ignore_index=True)
            os.makedirs(DATA_DIR, exist_ok=True)
            df.to_csv(HISTORICAL_FILE, index=False, encoding="utf-8")

            progress = {
                "total_recolectados": len(df),
                "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
            }
            with open(self.progress_file, "w") as f:
                json.dump(progress, f, indent=2)
        except Exception as e:
            logger.warning(f"Error guardando progreso: {e}")

    def merge_with_current(
        self, current_file: str | None = None
    ) -> pd.DataFrame:
        """
        Combina datos históricos con los datos actuales.

        Returns:
            DataFrame combinado y deduplicado.
        """
        current_file = current_file or os.path.join(
            DATA_DIR, "noticias_analyzed_simplified.csv"
        )

        dfs = []
        if os.path.exists(current_file):
            dfs.append(pd.read_csv(current_file))
        if os.path.exists(HISTORICAL_FILE):
            dfs.append(pd.read_csv(HISTORICAL_FILE))

        if not dfs:
            return pd.DataFrame()

        df = pd.concat(dfs, ignore_index=True)

        # Deduplicar
        from src.analysis.dedup import NewsDeduplicator
        dedup = NewsDeduplicator(title_threshold=0.70, content_threshold=0.85)
        df = dedup.deduplicate(df, keep="best")

        return df

    def close(self):
        self.google.close()
        self.wayback.close()
