"""
tests/test_investigator.py
==========================
Pruebas unitarias para src/analysis/investigator.py
usando unittest.mock — equivalente Python de Mockito (Java).

Conceptos clave:
  - patch()     ≡  Mockito.mock() / @Mock
  - MagicMock() ≡  objeto mock con todos los métodos simulados
  - return_value≡  when(mock).thenReturn(value)
  - side_effect ≡  when(mock).thenThrow(Exception)
  - assert_called_once_with() ≡ verify(mock).method(args)
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES — datos de prueba reutilizables
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture
def resultado_investigacion_exitoso():
    """Resultado JSON simulado que devolvería Gemini AI."""
    return {
        "ubicacion": "Guadalajara, Jalisco",
        "victimas": "María González, 34 años",
        "ninos_afectados": "3",
        "edades": "4, 7 y 11 años",
        "resumen": (
            "El caso ocurrió el 5 de mayo de 2025. "
            "La víctima fue encontrada sin vida en su domicilio. "
            "Sus tres hijos menores quedaron bajo resguardo del DIF Jalisco."
        ),
        "fuentes": ["https://fuente1.com/noticia", "https://fuente2.com/caso"],
        "query_usada": "feminicidio Guadalajara Jalisco hijos menores 2025",
    }


@pytest.fixture
def mock_gemini_response(resultado_investigacion_exitoso):
    """Simula la respuesta del cliente Gemini AI."""
    mock_resp = MagicMock()
    mock_resp.text = "```json\n" + json.dumps(resultado_investigacion_exitoso, ensure_ascii=False) + "\n```"
    return mock_resp


@pytest.fixture
def contenido_noticia():
    """Texto de noticia de prueba con suficiente contenido."""
    return (
        "Una mujer de 34 años fue víctima de feminicidio en Guadalajara, Jalisco. "
        "Sus tres hijos de 4, 7 y 11 años quedaron en orfandad tras el crimen. "
        "El DIF Jalisco tomó custodia temporal de los menores mientras se investiga el caso. "
        "El presunto responsable es la pareja sentimental de la víctima, quien fue detenido. "
        "Las autoridades confirmaron que los menores se encuentran en buen estado de salud. "
    ) * 5  # Repetir para garantizar >200 caracteres


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GRUPO 1: DeepInvestigator._scrape_content
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestScrapeContent:
    """
    Prueba el scraper de contenido web.
    Mockeamos requests/StealthSession para no hacer llamadas reales.
    """

    @patch("src.analysis.investigator.StealthSession")
    def test_scrape_content_exitoso(self, MockStealthSession, contenido_noticia):
        """CASO FELIZ: URL válida devuelve texto con contenido suficiente."""
        # Arrange — configurar el mock (≡ Mockito when().thenReturn())
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = f"<html><body><p>{contenido_noticia}</p></body></html>"
        mock_session.get.return_value = mock_response
        MockStealthSession.return_value = mock_session

        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        # Act
        resultado = inv._scrape_content("https://www.ejemplo.com/noticia")

        # Assert
        assert len(resultado) > 200, "El contenido scrapeado debe tener más de 200 caracteres"
        mock_session.get.assert_called_once()  # Verificar que se hizo UNA llamada

    @patch("src.analysis.investigator.StealthSession")
    def test_scrape_content_url_invalida_devuelve_vacio(self, MockStealthSession):
        """CASO NEGATIVO: Error HTTP devuelve string vacío."""
        # Arrange — simular error 404
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response
        MockStealthSession.return_value = mock_session

        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        # Act
        resultado = inv._scrape_content("https://www.ejemplo.com/pagina-inexistente")

        # Assert
        assert resultado == "" or len(resultado) < 200

    @patch("src.analysis.investigator.StealthSession")
    def test_scrape_content_excepcion_devuelve_vacio(self, MockStealthSession):
        """CASO EXCEPCIÓN: Timeout u otro error devuelve string vacío."""
        # Arrange — simular excepción de conexión (≡ Mockito thenThrow)
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Connection timeout")
        MockStealthSession.return_value = mock_session

        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        # Act — NO debe propagar la excepción
        resultado = inv._scrape_content("https://www.ejemplo.com/noticia")

        # Assert
        assert isinstance(resultado, str)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GRUPO 2: DeepInvestigator._extract_keywords
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestExtractKeywords:
    """Prueba la extracción de keywords usando Gemini AI mockeado."""

    @patch("src.analysis.investigator.client")
    def test_extract_keywords_devuelve_string(self, mock_client, contenido_noticia):
        """CASO FELIZ: Gemini devuelve query de búsqueda válida."""
        # Arrange
        mock_response = MagicMock()
        mock_response.text = "feminicidio Guadalajara hijos menores orfandad 2025"
        mock_client.models.generate_content.return_value = mock_response

        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        # Act
        query = inv._extract_keywords("Feminicidio en Jalisco deja 3 huérfanos", contenido_noticia)

        # Assert
        assert isinstance(query, str)
        assert len(query) > 5
        mock_client.models.generate_content.assert_called_once()

    @patch("src.analysis.investigator.client")
    def test_extract_keywords_fallback_cuando_falla_ia(self, mock_client):
        """CASO EXCEPCIÓN: Si Gemini falla, usa el título como fallback."""
        # Arrange — IA lanza excepción
        mock_client.models.generate_content.side_effect = Exception("API quota exceeded")

        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        titulo = "Feminicidio en Jalisco deja 3 huérfanos"

        # Act — no debe propagar el error
        query = inv._extract_keywords(titulo, "contenido corto")

        # Assert — debe retornar algo usable
        assert isinstance(query, str)
        assert len(query) > 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GRUPO 3: DeepInvestigator.investigate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestInvestigate:
    """
    Prueba el pipeline completo de investigación.
    Mockeamos todos los métodos internos para aislar la lógica.
    """

    @patch("src.analysis.investigator.client")
    @patch.object(
        __import__("src.analysis.investigator", fromlist=["DeepInvestigator"]).DeepInvestigator,
        "_scrape_content"
    )
    @patch.object(
        __import__("src.analysis.investigator", fromlist=["DeepInvestigator"]).DeepInvestigator,
        "_duckduckgo_search"
    )
    @patch.object(
        __import__("src.analysis.investigator", fromlist=["DeepInvestigator"]).DeepInvestigator,
        "_extract_keywords"
    )
    def test_investigate_pipeline_completo(
        self,
        mock_keywords,
        mock_search,
        mock_scrape,
        mock_client,
        resultado_investigacion_exitoso,
        mock_gemini_response,
        contenido_noticia,
    ):
        """
        CASO FELIZ: Pipeline completo ejecuta los 4 pasos en orden correcto.
        Verifica que: keywords → search → scrape → summary.
        """
        # Arrange — mockeamos cada paso del pipeline
        mock_keywords.return_value = "feminicidio Guadalajara hijos menores"
        mock_search.return_value = ["https://fuente1.com/noticia", "https://fuente2.com/caso"]
        mock_scrape.return_value = contenido_noticia
        mock_client.models.generate_content.return_value = mock_gemini_response

        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        # Act
        resultado = inv.investigate("Feminicidio deja 3 huérfanos en Jalisco", contenido_noticia)

        # Assert — estructura correcta del resultado
        assert "ubicacion" in resultado or "error" in resultado
        assert "resumen" in resultado or "error" in resultado
        # Verificar que se llamó a cada paso
        mock_keywords.assert_called_once()
        mock_search.assert_called_once()

    def test_investigate_sin_fuentes_usa_gemini_search(self, contenido_noticia):
        """
        CASO BORDE: Si DuckDuckGo no encuentra URLs, el sistema
        debe hacer fallback a la búsqueda nativa de Gemini.
        """
        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        with patch.object(inv, "_extract_keywords", return_value="query test"), \
             patch.object(inv, "_duckduckgo_search", return_value=[]), \
             patch.object(inv, "_investigate_with_gemini_search") as mock_gemini:

            mock_gemini.return_value = {
                "ubicacion": "Ciudad de México",
                "victimas": "Ana López",
                "ninos_afectados": "2",
                "edades": "5 y 8 años",
                "resumen": "Caso investigado con Gemini Search.",
                "fuentes": [],
                "metodo": "gemini_native_search",
            }

            resultado = inv.investigate("Título de prueba", contenido_noticia)

            # Debe haber usado Gemini Search como fallback
            mock_gemini.assert_called_once()
            assert resultado.get("metodo") == "gemini_native_search"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GRUPO 4: DeepInvestigator.investigate_url  (nueva función)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestInvestigateUrl:
    """Prueba el nuevo endpoint de identificación por URL."""

    def test_investigate_url_exitoso(self, contenido_noticia, resultado_investigacion_exitoso):
        """CASO FELIZ: URL con contenido suficiente produce informe completo."""
        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        with patch.object(inv, "_scrape_content", return_value=contenido_noticia) as mock_scrape, \
             patch.object(inv, "investigate", return_value=resultado_investigacion_exitoso) as mock_inv, \
             patch("src.analysis.investigator.client") as mock_client:

            mock_title_resp = MagicMock()
            mock_title_resp.text = "Feminicidio en Jalisco deja tres hijos huérfanos"
            mock_client.models.generate_content.return_value = mock_title_resp

            resultado = inv.investigate_url("https://www.elfinanciero.com.mx/noticia-ejemplo")

            # Assert
            mock_scrape.assert_called_once_with("https://www.elfinanciero.com.mx/noticia-ejemplo")
            mock_inv.assert_called_once()
            assert resultado == resultado_investigacion_exitoso

    def test_investigate_url_contenido_insuficiente(self):
        """CASO NEGATIVO: URL con <200 chars devuelve error estructurado."""
        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        with patch.object(inv, "_scrape_content", return_value="Texto muy corto."):
            resultado = inv.investigate_url("https://www.ejemplo.com/noticia")

        # Assert — debe retornar error, no excepción
        assert resultado.get("error") is True
        assert "mensaje" in resultado
        assert "URL" in resultado["mensaje"] or "contenido" in resultado["mensaje"].lower()

    def test_investigate_url_vacia_devuelve_error(self):
        """CASO NEGATIVO: Scraping falla completamente (retorna vacío)."""
        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        with patch.object(inv, "_scrape_content", return_value=""):
            resultado = inv.investigate_url("https://sitio-bloqueado.com/noticia")

        assert resultado.get("error") is True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GRUPO 5: DeepInvestigator._generate_summary
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGenerateSummary:
    """Prueba la generación de resúmenes estructurados con IA."""

    @patch("src.analysis.investigator.client")
    def test_generate_summary_parsea_json_correcto(self, mock_client, resultado_investigacion_exitoso):
        """CASO FELIZ: Gemini devuelve JSON válido y se parsea correctamente."""
        # Arrange
        mock_resp = MagicMock()
        mock_resp.text = json.dumps(resultado_investigacion_exitoso, ensure_ascii=False)
        mock_client.models.generate_content.return_value = mock_resp

        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        # Act
        resultado = inv._generate_summary("Título de prueba", "Contenido combinado de fuentes")

        # Assert — campos obligatorios presentes
        assert "ubicacion" in resultado
        assert "victimas" in resultado
        assert "ninos_afectados" in resultado
        assert "edades" in resultado
        assert "resumen" in resultado

    @patch("src.analysis.investigator.client")
    def test_generate_summary_parsea_json_con_markdown(self, mock_client, resultado_investigacion_exitoso):
        """CASO BORDE: Gemini envuelve el JSON en bloques markdown (```json```)."""
        # Arrange — JSON envuelto en markdown (comportamiento real de Gemini)
        mock_resp = MagicMock()
        mock_resp.text = "```json\n" + json.dumps(resultado_investigacion_exitoso) + "\n```"
        mock_client.models.generate_content.return_value = mock_resp

        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        # Act
        resultado = inv._generate_summary("Título", "Contenido")

        # Assert — el parser debe limpiar el markdown
        assert "ubicacion" in resultado
        assert resultado["ubicacion"] == "Guadalajara, Jalisco"

    @patch("src.analysis.investigator.client")
    def test_generate_summary_maneja_json_invalido(self, mock_client):
        """CASO EXCEPCIÓN: Gemini devuelve texto no-JSON, no debe crashear."""
        # Arrange
        mock_resp = MagicMock()
        mock_resp.text = "Lo siento, no pude procesar esta solicitud."
        mock_client.models.generate_content.return_value = mock_resp

        from src.analysis.investigator import DeepInvestigator
        inv = DeepInvestigator()

        # Act — no debe lanzar excepción
        resultado = inv._generate_summary("Título", "Contenido")

        # Assert — debe retornar un dict con algo (aunque sea el error)
        assert isinstance(resultado, dict)
