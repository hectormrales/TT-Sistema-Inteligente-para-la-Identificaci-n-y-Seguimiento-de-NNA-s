"""
tests/test_expedientes_casos.py
===============================
Suite de pruebas unitarias e integración para la Subfase 3.1:
  1. Generación de clave determinista de agrupación (`generar_clave_expediente`).
  2. Consolidación inteligente de datos entre múltiples notas (`consolidar_datos_expediente`).
  3. Agrupación automática de múltiples noticias del mismo feminicidio en un único
     `ExpedienteCaso` dentro de `NoticiasRepository.crear_batch()`.
  4. Flujo de seguimiento operativo de la ONG (`detectado` → `en_verificacion` →
     `contacto_dif_fiscalia` → `en_acompanamiento` → `archivado`) con bitácora de notas
     y sincronización automática en todas las noticias vinculadas.
"""

import pytest
from flask import Flask

from app.models import db
from src.database.models_noticias import (
    ExpedienteCaso,
    Noticia,
    consolidar_datos_expediente,
    generar_clave_expediente,
)
from src.database.repository import NoticiasRepository


class TestClaveExpedienteYConsolidacion:
    """Pruebas puras de agrupación y fusión de datos entre múltiples medios."""

    def test_misma_victima_distintos_medios_genera_misma_clave(self):
        inv_infobae = {
            "ubicacion": "Cuautitlán, Estado de México",
            "estado": "Estado de México",
            "municipio": "Cuautitlán",
            "victimas": "Cindy, 25 años; Teresita, 52 años",
            "ninos_afectados": "2",
        }
        inv_serendipia = {
            "ubicacion": "Cuautitlán, Edomex",
            "estado": "Estado de México",
            "municipio": "Cuautitlán",
            "victimas": "Cindy y su madre Teresita",
            "ninos_afectados": "2",
        }
        k1 = generar_clave_expediente(inv_infobae, "Nota de Infobae")
        k2 = generar_clave_expediente(inv_serendipia, "Nota de Serendipia")
        assert k1 == k2
        assert k1 == "vic:estado-de-mexico:cindy-teresita"

    def test_victimas_distintas_generan_claves_distintas(self):
        inv_cindy = {
            "estado": "Estado de México",
            "municipio": "Cuautitlán",
            "victimas": "Cindy",
        }
        inv_mariana = {
            "estado": "Estado de México",
            "municipio": "Naucalpan",
            "victimas": "Mariana",
        }
        assert generar_clave_expediente(inv_cindy) != generar_clave_expediente(inv_mariana)

    def test_caso_sin_nombre_agrupa_por_estado_municipio_nna_y_mes(self):
        inv_a = {
            "ubicacion": "Irapuato, Guanajuato",
            "estado": "Guanajuato",
            "municipio": "Irapuato",
            "victimas": "No especificada",
            "ninos_afectados": "2",
        }
        inv_b = {
            "ubicacion": "Irapuato, Guanajuato",
            "estado": "Guanajuato",
            "municipio": "Irapuato",
            "victimas": "Mujer vendedora",
            "ninos_afectados": "2 hijos",
        }
        k1 = generar_clave_expediente(inv_a, "Título A", "2026-10-12")
        k2 = generar_clave_expediente(inv_b, "Título B", "2026-10-14")
        assert k1 == k2
        assert k1 == "mun:guanajuato:irapuato:nna-2:2026-10"

    def test_consolidar_datos_expediente_rellena_campos_faltantes(self):
        nota_1 = {
            "ubicacion": "Cuautitlán, Estado de México",
            "estado": "Estado de México",
            "municipio": "Cuautitlán",
            "victimas": "Cindy",
            "ninos_afectados": "2",
            "edades": "No especificadas",
            "situacion_actual": "No especificada",
            "medios_contacto": "DIF",
            "cita_textual_evidencia": "dejó dos menores en orfandad",
            "resumen": "Resumen preliminar",
            "fuentes": ["https://medio1.mx/nota1"],
        }
        nota_2 = {
            "ubicacion": "Cuautitlán, Estado de México",
            "estado": "Estado de México",
            "municipio": "Cuautitlán",
            "victimas": "Cindy, 25 años y Teresita, 52 años",
            "ninos_afectados": "2",
            "edades": "6 y 3 años",
            "situacion_actual": "Bajo resguardo del DIF de Cuautitlán",
            "medios_contacto": "DIF Cuautitlán / FGJEM",
            "cita_textual_evidencia": "los menores de 6 y 3 años quedaron en orfandad bajo resguardo del DIF",
            "resumen": "Doble feminicidio en Cuautitlán donde dos menores quedaron en orfandad.",
            "fuentes": ["https://medio2.mx/nota2"],
        }
        consolidado = consolidar_datos_expediente(nota_1, nota_2)
        assert consolidado["edades"] == "6 y 3 años"
        assert consolidado["situacion_actual"] == "Bajo resguardo del DIF de Cuautitlán"
        assert "Teresita" in consolidado["victimas"]
        assert len(consolidado["fuentes"]) == 2


@pytest.fixture
def db_ctx():
    """Crea una base de datos SQLite en memoria aislada para probar ExpedienteCaso."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


class TestExpedienteRepositoryFlow:
    """Pruebas de integración de NoticiasRepository con ExpedienteCaso en BD."""

    def test_crear_batch_agrupa_tres_noticias_del_mismo_caso_en_un_solo_expediente(self, db_ctx):
        records = [
            {
                "titulo": "Feminicidio de Cindy en Cuautitlán deja a dos menores en orfandad - Serendipia",
                "contenido": "Cindy fue asesinada en Cuautitlán, Estado de México, dejando dos hijos en orfandad.",
                "enlace": "https://serendipia.digital/caso-cindy-1",
                "fuente": "Serendipia",
                "clasificacion": "Alta",
                "clasificacion_final": "Alta",
                "relevancia_final": 0.92,
                "menores_identificados": "Si",
                "content_hash": "hash_cindy_1",
                "investigacion_json": {
                    "ubicacion": "Cuautitlán, Estado de México",
                    "estado": "Estado de México",
                    "municipio": "Cuautitlán",
                    "victimas": "Cindy, Teresita",
                    "ninos_afectados": 2,
                    "edades": "No especificadas",
                    "situacion_actual": "No especificada",
                    "medios_contacto": "FGJEM",
                    "cita_textual_evidencia": "dejando dos hijos en orfandad",
                    "resumen": "Caso de Cindy en Cuautitlán.",
                },
            },
            {
                "titulo": "Capturan a Eric Antonio por feminicidio de Cindy y Teresita en Cuautitlán - TV Azteca",
                "contenido": "Los dos menores de 6 y 3 años quedaron bajo resguardo del DIF tras el crimen.",
                "enlace": "https://tvazteca.com/caso-cindy-2",
                "fuente": "TV Azteca",
                "clasificacion": "Alta",
                "clasificacion_final": "Alta",
                "relevancia_final": 0.96,
                "menores_identificados": "Si",
                "content_hash": "hash_cindy_2",
                "investigacion_json": {
                    "ubicacion": "Cuautitlán, Estado de México",
                    "estado": "Estado de México",
                    "municipio": "Cuautitlán",
                    "victimas": "Cindy, 25 años y Teresita, 52 años",
                    "ninos_afectados": 2,
                    "edades": "6 y 3 años",
                    "situacion_actual": "Bajo resguardo del DIF municipal",
                    "medios_contacto": "DIF Cuautitlán / FGJEM",
                    "cita_textual_evidencia": "Los dos menores de 6 y 3 años quedaron bajo resguardo del DIF",
                    "resumen": "Detienen al responsable; niños de 6 y 3 años en el DIF.",
                },
            },
            {
                "titulo": "Asesinan a Mariana frente a su hijo de 5 años en Naucalpan - Telediario",
                "contenido": "Mariana fue asesinada a balazos dentro de su auto frente a su hijo de 5 años.",
                "enlace": "https://telediario.mx/caso-mariana-1",
                "fuente": "Telediario",
                "clasificacion": "Alta",
                "clasificacion_final": "Alta",
                "relevancia_final": 0.90,
                "menores_identificados": "Si",
                "content_hash": "hash_mariana_1",
                "investigacion_json": {
                    "ubicacion": "Naucalpan, Estado de México",
                    "estado": "Estado de México",
                    "municipio": "Naucalpan",
                    "victimas": "Mariana",
                    "ninos_afectados": 1,
                    "edades": "5 años",
                    "situacion_actual": "Con familiares",
                    "medios_contacto": "FGJEM Naucalpan",
                    "cita_textual_evidencia": "frente a su hijo de 5 años",
                    "resumen": "Feminicidio de Mariana en Naucalpan frente a su hijo.",
                },
            },
        ]

        inserted = NoticiasRepository.crear_batch(records)
        assert inserted == 3

        # Deben existir exactamente 2 expedientes (1 para Cindy con 2 notas, y 1 para Mariana con 1 nota)
        expedientes = NoticiasRepository.listar_expedientes()
        assert len(expedientes) == 2

        exp_cindy = next(e for e in expedientes if "Cindy" in e["victimas"])
        assert exp_cindy["num_noticias"] == 2
        assert exp_cindy["edades"] == "6 y 3 años"
        assert exp_cindy["situacion_actual"] == "Bajo resguardo del DIF municipal"
        assert len(exp_cindy["fuentes"]) == 2
        assert exp_cindy["estado_seguimiento"] == "detectado"
        assert exp_cindy["en_seguimiento"] is False

        # Actualizar estado de seguimiento en el expediente de Cindy y verificar sincronización
        actualizado = NoticiasRepository.actualizar_seguimiento_expediente(
            exp_cindy["id"],
            estado_seguimiento="contacto_dif_fiscalia",
            nota="Se solicitó informe a Procuraduría de Protección de NNA de Cuautitlán.",
            usuario="Trabajadora Social ANA",
        )
        assert actualizado is not None
        assert actualizado["en_seguimiento"] is True
        assert actualizado["estado_seguimiento"] == "contacto_dif_fiscalia"
        assert len(actualizado["notas_seguimiento"]) == 1

        # Ambas noticias de Cindy deben reflejar el nuevo estado en su investigacion_json
        noticias_cindy = Noticia.query.filter_by(expediente_id=exp_cindy["id"]).all()
        assert len(noticias_cindy) == 2
        for n in noticias_cindy:
            assert n.investigacion_json["en_seguimiento"] is True
            assert n.investigacion_json["estado_seguimiento"] == "contacto_dif_fiscalia"
            assert n.investigacion_json["folio_expediente"] == exp_cindy["folio"]

