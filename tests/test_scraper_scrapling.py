"""
tests/test_scraper_scrapling.py
===============================
Pruebas unitarias para el motor de extracción full-text con Scrapling + Trafilatura
en `src/collection/scraper.py` (Subfase 2.1).
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from src.collection.scraper import (
    HAS_SCRAPLING,
    ScraplingResponseAdapter,
    StealthSession,
    DynamicScraper,
    extract_full_article,
    extract_full_articles_batch,
)


SAMPLE_NEWS_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Asesinan a mujer en Ecatepec; deja dos hijos menores en la orfandad</title>
    <meta property="article:published_time" content="2026-03-15T14:30:00Z">
</head>
<body>
    <header><nav>Menú Principal | Noticias | Seguridad</nav></header>
    <article class="article-body">
        <h1 class="article-title">Asesinan a mujer en Ecatepec; deja dos hijos menores en la orfandad</h1>
        <p>Una mujer de 29 años identificada como Laura "N" fue víctima de feminicidio dentro de su domicilio ubicado en el municipio de Ecatepec, Estado de México.</p>
        <p>Vecinos alertaron a las autoridades municipales tras escuchar gritos de auxilio durante la madrugada del domingo.</p>
        <p>De acuerdo con reportes de la Fiscalía General de Justicia del Estado de México, la víctima era madre de dos niños de 4 y 7 años de edad, quienes quedaron en situación de orfandad y bajo resguardo temporal del DIF municipal.</p>
    </article>
    <footer>Aviso de privacidad y términos de uso</footer>
</body>
</html>
"""

SAMPLE_JSONLD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Nota Periodística con JSON-LD</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Feminicidio en Guadalajara deja tres menores bajo custodia del DIF",
        "datePublished": "2026-04-02T10:00:00Z",
        "articleBody": "Autoridades de Jalisco investigan bajo el protocolo de feminicidio la muerte de una madre de 33 años en Guadalajara. Sus tres hijos menores de 3, 6 y 9 años quedaron bajo custodia del DIF Jalisco mientras se localiza a su red familiar de apoyo."
    }
    </script>
</head>
<body><div id="app">Cargando...</div></body>
</html>
"""


class TestScraplingIntegration:
    """Verifica el adaptador Scrapling y su selector DOM adaptativo."""

    def test_scrapling_is_available(self):
        assert HAS_SCRAPLING is True

    def test_scrapling_response_adapter_exposes_requests_interface_and_selector(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.url = "https://www.ejemplo.mx/seguridad/caso-ecatepec"
        fake_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        fake_resp.content = SAMPLE_NEWS_HTML.encode("utf-8")
        fake_resp.text = SAMPLE_NEWS_HTML

        adapted = ScraplingResponseAdapter(fake_resp, fake_resp.url)
        assert adapted.status_code == 200
        assert adapted.url == "https://www.ejemplo.mx/seguridad/caso-ecatepec"
        assert "Ecatepec" in adapted.text
        assert adapted.scrapling_page is not None

        # Verificar que el selector CSS de Scrapling extrae el h1 y los párrafos
        h1_nodes = adapted.scrapling_page.css("h1.article-title")
        assert len(h1_nodes) == 1
        assert "Ecatepec" in str(h1_nodes[0].get_all_text(strip=True))

        p_nodes = adapted.scrapling_page.css("article.article-body p")
        assert len(p_nodes) == 3


class TestFullArticleExtraction:
    """Verifica la extracción de cuerpo completo con Scrapling + Trafilatura + JSON-LD."""

    def test_extract_full_article_from_html_body(self):
        mock_session = MagicMock(spec=StealthSession)
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.url = "https://www.jornada.com.mx/notas/2026/03/15/ecatepec"
        fake_resp.headers = {"Content-Type": "text/html"}
        fake_resp.content = SAMPLE_NEWS_HTML.encode("utf-8")
        fake_resp.text = SAMPLE_NEWS_HTML

        mock_session.get.return_value = ScraplingResponseAdapter(fake_resp, fake_resp.url)

        article = extract_full_article(fake_resp.url, session=mock_session)
        assert article is not None
        assert "Ecatepec" in article["titulo"]
        assert "dos niños de 4 y 7 años" in article["contenido"]
        assert "DIF municipal" in article["contenido"]
        assert article["fuente"] == "www.jornada.com.mx"

    def test_extract_full_article_from_jsonld_on_spa_page(self):
        mock_session = MagicMock(spec=StealthSession)
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.url = "https://www.informador.mx/jalisco/feminicidio-guadalajara"
        fake_resp.headers = {"Content-Type": "text/html"}
        fake_resp.content = SAMPLE_JSONLD_HTML.encode("utf-8")
        fake_resp.text = SAMPLE_JSONLD_HTML

        mock_session.get.return_value = ScraplingResponseAdapter(fake_resp, fake_resp.url)

        article = extract_full_article(fake_resp.url, session=mock_session)
        assert article is not None
        assert "Guadalajara" in article["titulo"]
        assert "custodia del DIF Jalisco" in article["contenido"]

    def test_extract_full_articles_batch_concurrent(self):
        urls = [
            "https://medio1.mx/nota/caso-1",
            "https://medio2.mx/nota/caso-2",
        ]

        def fake_extract(url, session=None, timeout=15):
            return {
                "titulo": f"Título de {url}",
                "contenido": (
                    "Cuerpo completo de la noticia periodística con más de cien caracteres "
                    "relatando cómo dos menores quedaron en situación de orfandad en México."
                ),
                "enlace": url,
                "fuente": "medio.mx",
                "fecha": "2026-03-15T12:00:00Z",
                "scrape_method": "scrapling_html",
            }

        with patch("src.collection.scraper.extract_full_article", side_effect=fake_extract):
            batch_res = extract_full_articles_batch(urls, max_workers=2)

        assert len(batch_res) == 2
        assert "orfandad" in batch_res["https://medio1.mx/nota/caso-1"]["contenido"]
        assert "orfandad" in batch_res["https://medio2.mx/nota/caso-2"]["contenido"]


class TestWindowsTlsAndSharedCircuitBreaker:
    """Verifica el certificado ASCII para Windows y el Circuit Breaker compartido (Paso A)."""

    def test_ascii_ca_bundle_configured_in_env(self):
        import os
        from src.collection.scraper import _ASCII_CA_BUNDLE
        if isinstance(_ASCII_CA_BUNDLE, str):
            # Debe ser 100% ASCII para que libcurl/curl_cffi no falle con rutas con tilde
            _ASCII_CA_BUNDLE.encode("ascii")
            assert os.environ.get("CURL_CA_BUNDLE") == _ASCII_CA_BUNDLE
            assert os.environ.get("SSL_CERT_FILE") == _ASCII_CA_BUNDLE

    def test_shared_circuit_breaker_between_stealth_session_and_dynamic_scraper(self):
        from src.collection.scraper import DomainCircuitBreaker
        cb = DomainCircuitBreaker()
        s1 = StealthSession(test_mode=True, circuit_breaker=cb)
        scraper = DynamicScraper(respect_robots=False, test_mode=True, session=s1)

        domain = "sitio-bloqueado-test.mx"
        assert cb.can_request(domain) is True

        # Simular 3 fallos consecutivos en StealthSession
        cb.record_failure(domain)
        cb.record_failure(domain)
        cb.record_failure(domain)

        # Tanto StealthSession como DynamicScraper deben ver el circuito ABIERTO inmediatamente
        assert cb.can_request(domain) is False
        assert scraper._stealth._circuit_breaker.can_request(domain) is False
        assert s1.get(f"https://{domain}/rss") is None


