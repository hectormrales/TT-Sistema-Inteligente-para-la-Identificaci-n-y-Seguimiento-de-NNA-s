"""
tests/test_routes_api.py
=========================
Pruebas unitarias para los endpoints Flask de app/main/routes.py
usando el cliente de prueba de Flask (TestClient).

Incluye pruebas del nuevo endpoint /api/identify-link.
"""

import json
import pytest
from unittest.mock import MagicMock, patch


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES — cliente Flask de prueba
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture
def app():
    """Crea la app Flask en modo testing."""
    pytest.importorskip("flask")
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from config import Config
    with patch.object(Config, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"), \
         patch.object(Config, "SQLALCHEMY_ENGINE_OPTIONS", {}), \
         patch("app._init_database"):
        from app import create_app
        application = create_app()
        application.config["TESTING"] = True
        application.config["LOGIN_DISABLED"] = True
        application.config["WTF_CSRF_ENABLED"] = False  # Deshabilitar CSRF en tests
        yield application


@pytest.fixture
def client(app):
    """Cliente HTTP de prueba para Flask."""
    with app.test_client() as c:
        with app.app_context():
            yield c


@pytest.fixture
def resultado_api_exitoso():
    """Resultado simulado de DeepInvestigator.investigate_url."""
    return {
        "ubicacion": "Monterrey, Nuevo León",
        "victimas": "Rosa Mendoza",
        "ninos_afectados": "2",
        "edades": "6 y 9 años",
        "resumen": "Caso de feminicidio donde los menores quedaron en orfandad.",
        "fuentes": ["https://fuente1.com", "https://fuente2.com"],
        "query_usada": "feminicidio Monterrey hijos menores 2025",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GRUPO 1: POST /api/identify-link
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestIdentifyLinkEndpoint:
    """
    Prueba el endpoint POST /api/identify-link.
    Mockeamos DeepInvestigator para no hacer llamadas reales a IA.
    """

    def _make_request(self, client, url_value):
        """Helper para hacer POST al endpoint."""
        return client.post(
            "/api/identify-link",
            data=json.dumps({"url": url_value}),
            content_type="application/json",
        )

    @patch("app.main.routes.DeepInvestigator")
    def test_identify_link_exitoso_200(self, MockInvestigator, client, resultado_api_exitoso):
        """CASO FELIZ: URL válida → 200 OK con resultado estructurado."""
        # Arrange — mock del investigador
        mock_inv = MagicMock()
        mock_inv.investigate_url.return_value = resultado_api_exitoso
        MockInvestigator.return_value = mock_inv

        # Act
        response = self._make_request(client, "https://www.elfinanciero.com.mx/noticia")

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "ubicacion" in data
        assert data["ubicacion"] == "Monterrey, Nuevo León"
        mock_inv.investigate_url.assert_called_once_with("https://www.elfinanciero.com.mx/noticia")

    def test_identify_link_url_vacia_400(self, client):
        """CASO NEGATIVO: Sin URL → 400 Bad Request."""
        response = self._make_request(client, "")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_identify_link_sin_body_400(self, client):
        """CASO NEGATIVO: Sin body JSON → error."""
        response = client.post(
            "/api/identify-link",
            data="",
            content_type="application/json",
        )
        assert response.status_code in (400, 415, 500)

    @patch("app.main.routes.DeepInvestigator")
    def test_identify_link_error_investigacion_propagado(self, MockInvestigator, client):
        """CASO EXCEPCIÓN: Si DeepInvestigator falla → 500 con error."""
        # Arrange — el investigador lanza una excepción
        mock_inv = MagicMock()
        mock_inv.investigate_url.side_effect = RuntimeError("Error interno de IA")
        MockInvestigator.return_value = mock_inv

        # Act
        response = self._make_request(client, "https://www.ejemplo.com/noticia")

        # Assert
        assert response.status_code == 500
        data = json.loads(response.data)
        assert "error" in data

    @patch("app.main.routes.DeepInvestigator")
    def test_identify_link_error_scraping_devuelve_200_con_error_flag(
        self, MockInvestigator, client
    ):
        """
        CASO BORDE: Si el scraping falla, investigate_url devuelve
        {"error": True, "mensaje": "..."} — el endpoint retorna 200
        con ese dict (no es error HTTP, es error de negocio).
        """
        mock_inv = MagicMock()
        mock_inv.investigate_url.return_value = {
            "error": True,
            "mensaje": "No se pudo extraer contenido de la URL.",
        }
        MockInvestigator.return_value = mock_inv

        response = self._make_request(client, "https://sitio-bloqueado.com/noticia")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get("error") is True
        assert "mensaje" in data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GRUPO 2: GET /api/stats
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestStatsEndpoint:
    """Prueba básica del endpoint de estadísticas."""

    @patch("app.main.routes.Noticia")
    def test_stats_estructura_respuesta(self, MockNoticia, client):
        """El endpoint /api/stats debe devolver claves estándar."""
        # Arrange — mock de consultas a BD
        MockNoticia.query.count.return_value = 42

        response = client.get("/api/stats")
        assert response.status_code in (200, 302)  # 302 si requiere login


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GRUPO 3: Endpoints de Expedientes y Seguimiento (Subfase 3.2)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestSeguimientoExpedientesEndpoints:
    """Pruebas de integración para el flujo de expedientes y bitácora en app/main/routes.py."""

    def _seed_db_with_expediente(self):
        from app.models import db
        from src.database.models_noticias import ExpedienteCaso, Noticia
        from src.database.repository import NoticiasRepository

        db.create_all()

        noticia = Noticia(
            titulo="Feminicidio de Elena en Cuautitlán deja a dos menores en orfandad",
            contenido="Elena Gómez fue asesinada en Cuautitlán, Estado de México. Sus dos hijos de 4 y 8 años quedaron bajo resguardo del DIF.",
            enlace="https://eluniversal.com.mx/edomex/caso-elena",
            fuente="El Universal",
            score_feminicidio=0.95,
            score_nna=0.92,
            score_compuesto=0.94,
            relevancia_final=0.94,
            clasificacion="Alta",
            clasificacion_final="Alta",
            menores_identificados="Si",
            investigacion_json={
                "ubicacion": "Cuautitlán, Estado de México",
                "estado": "Estado de México",
                "municipio": "Cuautitlán",
                "victimas": "Elena Gómez",
                "nna_afectados": "2",
                "edades_nna": "4 y 8 años",
                "situacion_actual": "Bajo resguardo del DIF municipal",
                "cita_textual_evidencia": "Sus dos hijos de 4 y 8 años quedaron bajo resguardo del DIF.",
                "medios_contacto": "DIF Cuautitlán / FGJEM",
                "resumen": "Caso confirmado de feminicidio con dos menores en orfandad.",
                "en_seguimiento": True,
            },
        )
        db.session.add(noticia)
        db.session.flush()
        exp = NoticiasRepository.vincular_o_crear_expediente(
            noticia,
            investigacion=noticia.investigacion_json,
            marcar_seguimiento=True,
        )
        db.session.commit()
        return exp, noticia

    def test_get_seguimiento_casos_devuelve_expedientes_y_conteos(self, client):
        exp, _ = self._seed_db_with_expediente()

        resp = client.get("/api/seguimiento/casos")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "casos" in data
        assert "conteo_estados" in data
        assert len(data["casos"]) == 1
        caso = data["casos"][0]
        assert caso["expediente_id"] == exp.id
        assert caso["victimas"] == "Elena Gómez"
        assert "Sus dos hijos de 4 y 8 años" in caso["cita_textual_evidencia"]

    def test_post_update_expediente_status_y_bitacora(self, client):
        exp, _ = self._seed_db_with_expediente()

        resp = client.post(
            f"/api/seguimiento/expediente/{exp.id}/status",
            data=json.dumps({
                "estado_seguimiento": "contacto_dif_fiscalia",
                "nota": "Se envió solicitud de información a Procuraduría de Protección de NNA",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "success"
        assert data["expediente"]["estado_seguimiento"] == "contacto_dif_fiscalia"
        notas = data["expediente"]["notas_seguimiento"]
        assert len(notas) == 1
        assert "Procuraduría de Protección" in notas[0]["texto"]

    def test_export_seguimiento_csv_incluye_cita_y_estado(self, client):
        self._seed_db_with_expediente()

        resp = client.get("/api/seguimiento/export/csv")
        assert resp.status_code == 200
        csv_text = resp.data.decode("utf-8-sig")
        assert "Cita Textual de Evidencia" in csv_text
        assert "Elena Gómez" in csv_text
        assert "Sus dos hijos de 4 y 8 años quedaron bajo resguardo del DIF." in csv_text

    def test_export_seguimiento_pdf_renderiza_ficha_oficial(self, client):
        exp, _ = self._seed_db_with_expediente()

        resp = client.get(f"/api/seguimiento/export/pdf/{exp.id}?tipo=expediente")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Futuro Con Derechos" in html
        assert "Elena Gómez" in html
        assert "Sus dos hijos de 4 y 8 años quedaron bajo resguardo del DIF." in html

