"""
tests/test_collector_v2.py
==========================
Suite de pruebas unitarias para la Subfase 2.2:
  1. Resolución de URLs de agregadores (`resolve_article_url`: Bing News, DuckDuckGo, Google Search, Google News).
  2. Operadores de fecha en feeds (`_inject_date_operators`) y búsqueda dirigida en DuckDuckGo (`df=start..end`, `kl=mx-es`).
  3. Recolección RSS inteligente (`collect_news_from_rss`) con preservación de candidatas `_needs_fulltext_verify` en búsquedas dirigidas.
  4. Enriquecimiento de cuerpo completo (`enrich_candidates_with_full_text`) con re-evaluación de `score_relevance` tras extraer el texto con Scrapling + Trafilatura.
  5. Fix de `_is_block_page` contra falsos positivos por `<meta name="robots">` o botones de login en cabeceras.
"""

from unittest.mock import MagicMock, patch
import pytest

from src.collection.scraper import (
    ScraplingResponseAdapter,
    _is_block_page,
    resolve_article_url,
)
from src.collection.collector import (
    _inject_date_operators,
    collect_news_from_duckduckgo,
    collect_news_from_rss,
    enrich_candidates_with_full_text,
)


class TestUrlResolutionAndBlockPageFix:
    """Verifica el desenvolvimiento de URLs de agregadores y el filtro _is_block_page."""

    def test_unwraps_bing_news_apiclick_url(self):
        bing_url = (
            "http://www.bing.com/news/apiclick.aspx?ref=FexRss&aid=&tid=6aef"
            "&url=https%3a%2f%2fwww.milenio.com%2fpolicia%2ffeminicidio-en-ecatepec-deja-huerfanos"
            "&c=12345&mkt=es-mx"
        )
        resolved = resolve_article_url(bing_url)
        assert resolved == "https://www.milenio.com/policia/feminicidio-en-ecatepec-deja-huerfanos"

    def test_unwraps_duckduckgo_redirect_url(self):
        ddg_url = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.infobae.com%2Fmexico%2Fnota-feminicidio%2F&rut=abc"
        resolved = resolve_article_url(ddg_url)
        assert resolved == "https://www.infobae.com/mexico/nota-feminicidio/"

    def test_unwraps_google_search_redirect_url(self):
        g_url = "/url?q=https%3A%2F%2Fwww.jornada.com.mx%2Fnota%2F2026%2F10%2F15%2Festados&sa=U"
        resolved = resolve_article_url(g_url)
        assert resolved == "https://www.jornada.com.mx/nota/2026/10/15/estados"

    def test_is_block_page_does_not_false_positive_on_meta_robots_or_login_nav(self):
        legit_newspaper_html = (
            "<html><head><meta name='robots' content='index, follow, max-image-preview:large'/>"
            "<title>Asesinan a mujer en Cuautitlán - El País</title></head>"
            "<body><header><a href='/login'>Iniciar sesión</a> <a href='/sub'>Suscríbete</a></header>"
            "<article><h1>Asesinan a mujer en Cuautitlán</h1>"
            + ("<p>La Fiscalía del Estado de México informó que los dos hijos menores quedaron bajo resguardo del DIF municipal tras el feminicidio ocurrido ayer.</p>" * 15)
            + "</article></body></html>"
        )
        resp = ScraplingResponseAdapter(
            legit_newspaper_html.encode("utf-8"),
            url="https://elpais.com/mexico/nota.html",
            status_code=200,
        )
        assert _is_block_page(resp) is False


class TestTargetedSearchAndRssDiscovery:
    """Verifica búsqueda por rango de fechas y preservación de candidatas RSS para full-text."""

    def test_inject_date_operators_adds_after_and_before(self):
        feed = "https://news.google.com/rss/search?q=feminicidio+hijos+M%C3%A9xico&hl=es-419&gl=MX&ceid=MX:es-419"
        updated = _inject_date_operators(feed, "2026-01-01", "2026-03-31")
        assert "after%3A2026-01-01" in updated
        assert "before%3A2026-03-31" in updated

    def test_duckduckgo_passes_date_range_and_mx_region(self):
        fake_ddg_html = """
        <html><body>
          <div class="result">
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.milenio.com%2Festados%2ffeminicidio-puebla">
              Asesinan a mujer frente a sus dos hijos en Puebla
            </a>
            <a class="result__snippet">
              Los dos niños de 5 y 8 años quedaron en orfandad bajo resguardo del DIF en Puebla, México.
            </a>
          </div>
        </body></html>
        """
        mock_session = MagicMock()
        mock_session.get.return_value = ScraplingResponseAdapter(
            fake_ddg_html.encode("utf-8"),
            url="https://html.duckduckgo.com/html/",
            status_code=200,
        )
        seen = set()
        results = collect_news_from_duckduckgo(
            'feminicidio "dejó en orfandad" México',
            seen,
            mock_session,
            start_date="2026-01-01",
            end_date="2026-06-30",
        )
        called_url = mock_session.get.call_args[0][0]
        assert "kl=mx-es" in called_url
        assert "df=2026-01-01..2026-06-30" in called_url
        assert len(results) == 1
        assert results[0]["enlace"] == "https://www.milenio.com/estados/feminicidio-puebla"
        assert results[0]["clasificacion"] == "Alta"

    def test_google_news_rss_preserves_femicide_candidate_with_empty_snippet_for_fulltext_verify(self):
        # En Google News RSS, el título solo dice "Vinculan a proceso por feminicidio de joven en Ecatepec"
        # y <description> repite el título (sin mencionar aún a los hijos, que están en el cuerpo de la nota).
        rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
          <item>
            <title>Asesinan a mujer dentro de su domicilio en Ecatepec, Estado de M\xc3\xa9xico - El Universal</title>
            <link>https://news.google.com/rss/articles/CBMi12345</link>
            <description>Asesinan a mujer dentro de su domicilio en Ecatepec, Estado de M\xc3\xa9xico - El Universal</description>
          </item>
        </channel></rss>
        """
        mock_session = MagicMock()
        mock_session.get.return_value = ScraplingResponseAdapter(
            rss_xml,
            url="https://news.google.com/rss/search?q=feminicidio+hijos+hu%C3%A9rfanos+M%C3%A9xico",
            status_code=200,
        )
        articles = collect_news_from_rss(
            "https://news.google.com/rss/search?q=feminicidio+hijos+hu%C3%A9rfanos+M%C3%A9xico",
            seen_urls=set(),
            session=mock_session,
        )
        assert len(articles) == 1
        assert articles[0]["_needs_fulltext_verify"] is True


class TestFullTextEnrichment:
    """Verifica que enrich_candidates_with_full_text descargue el cuerpo completo y re-clasifique."""

    def test_enriches_candidate_and_upgrades_relevance_when_children_in_body(self):
        candidates = [
            {
                "titulo": "Asesinan a mujer dentro de su domicilio en Ecatepec, Estado de México",
                "contenido": "",
                "enlace": "https://news.google.com/rss/articles/CBMi12345",
                "fuente": "Google News Search",
                "fecha": "2026-10-15T12:00:00+00:00",
                "score_feminicidio": 0.85,
                "score_nna": 0.0,
                "score_compuesto": 0.15,
                "clasificacion": "No relevante",
                "menores_identificados": "No",
                "_needs_fulltext_verify": True,
            },
            {
                "titulo": "Asesinan a mujer en robo de auto en Guadalajara, Jalisco",
                "contenido": "",
                "enlace": "https://news.google.com/rss/articles/CBMi99999",
                "fuente": "Google News Search",
                "fecha": "2026-10-15T12:00:00+00:00",
                "score_feminicidio": 0.85,
                "score_nna": 0.0,
                "score_compuesto": 0.15,
                "clasificacion": "No relevante",
                "menores_identificados": "No",
                "_needs_fulltext_verify": True,
            },
        ]

        fake_extracted_map = {
            "https://news.google.com/rss/articles/CBMi12345": {
                "titulo": "Asesinan a mujer dentro de su domicilio en Ecatepec, Estado de México",
                "contenido": (
                    "Una mujer de 29 años fue asesinada en Ecatepec, Estado de México. "
                    "Vecinos informaron que el feminicidio dejó en orfandad a sus dos hijos menores "
                    "de 4 y 7 años de edad, quienes quedaron bajo resguardo del DIF municipal."
                ),
                "enlace": "https://www.eluniversal.com.mx/edomex/asesinan-a-mujer-en-ecatepec",
                "scrape_method": "scrapling_html",
            },
            "https://news.google.com/rss/articles/CBMi99999": {
                "titulo": "Asesinan a mujer en robo de auto en Guadalajara, Jalisco",
                "contenido": (
                    "Una conductora perdió la vida tras un asalto violento en la colonia Americana "
                    "de Guadalajara. La policía estatal acordonó la avenida mientras peritos "
                    "realizaban el levantamiento de indicios."
                ),
                "enlace": "https://www.informador.mx/jalisco/asalto-en-guadalajara",
                "scrape_method": "scrapling_html",
            },
        }

        with patch("src.collection.collector.extract_full_articles_batch", return_value=fake_extracted_map):
            enriched = enrich_candidates_with_full_text(candidates, threshold=0.25)

        # Solo la primera nota (que menciona a los dos hijos en orfandad en su cuerpo) debe sobrevivir!
        assert len(enriched) == 1
        surviving = enriched[0]
        assert surviving["enlace"] == "https://www.eluniversal.com.mx/edomex/asesinan-a-mujer-en-ecatepec"
        assert "dos hijos menores" in surviving["contenido"]
        assert surviving["clasificacion"] == "Alta"
        assert surviving["menores_identificados"] == "Si"

