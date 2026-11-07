# tests/test_llm_extractor.py — Suite de pruebas de Subfase 1.1 (LLMExtractor y 5 Candados Anti-FP)
"""
Verifica exhaustivamente:
  1. El Pre-filtro de Admisión (`passes_admission_gate`)
  2. Los 5 Candados Anti-Falsos Positivos (`aplicar_candados_estrictos`)
  3. El verificador anti-alucinaciones de cita textual (`_verify_quote_in_text`)
  4. El flujo completo de `LLMExtractor` (con mock de proveedores Groq/Gemini y fallback determinista)
"""

import json
from unittest.mock import patch, MagicMock
import pytest

from src.analysis.llm_extractor import (
    CasoExtraidoSchema,
    LLMExtractor,
    passes_admission_gate,
    aplicar_candados_estrictos,
    _verify_quote_in_text,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. PRUEBAS DEL PRE-FILTRO DE ADMISIÓN RÁPIDO (`passes_admission_gate`)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAdmissionGate:
    def test_accepts_genuine_femicide_with_orphans(self):
        title = "Asesinan a Mariana frente a su hijo de 5 años en Ecatepec"
        content = (
            "Una mujer de 28 años fue privada de la vida en su domicilio en Ecatepec, "
            "Estado de México. Sus dos hijos menores quedaron bajo resguardo del DIF municipal."
        )
        passed, reason = passes_admission_gate(title, content, "https://eluniversal.com.mx/nota1")
        assert passed is True
        assert "Candidata válida" in reason

    def test_rejects_sports_and_entertainment_noise(self):
        title = "Liga MX: América golea en el clásico y avanza a la liguilla"
        content = "El partido terminó con tres goles frente a miles de niños y familias en el estadio."
        passed, reason = passes_admission_gate(title, content)
        assert passed is False
        assert "Ruido temático" in reason

    def test_rejects_matricide_in_title(self):
        title = "Joven de 19 años asesina a su madre a puñaladas en Guadalajara"
        content = "El hijo de la víctima fue detenido por la policía tras atacar a su propia madre en Jalisco."
        passed, reason = passes_admission_gate(title, content)
        assert passed is False
        assert "Matricidio" in reason

    def test_rejects_foreign_country_news(self):
        title = "Conmoción en Bogotá: asesinan a madre de dos niños en Colombia"
        content = "El crimen ocurrió en Medellín, Colombia, donde las autoridades colombianas investigan el feminicidio."
        passed, reason = passes_admission_gate(title, content, "https://eltiempo.com/colombia")
        assert passed is False
        assert "internacional" in reason.lower()

    def test_rejects_news_without_children_mention(self):
        title = "Hallan sin vida a una mujer en terreno baldío de Puebla"
        content = "La Fiscalía General del Estado de Puebla inició carpeta de investigación por feminicidio."
        passed, reason = passes_admission_gate(title, content)
        assert passed is False
        assert "Sin mención a hijos" in reason

    def test_rejects_pure_legislative_or_statistical_title(self):
        title = "Congreso aprueba Ley Monzón para quitar patria potestad a feminicidas en México"
        content = "Los diputados votaron por unanimidad la iniciativa de reforma en favor de los menores en orfandad."
        passed, reason = passes_admission_gate(title, content)
        assert passed is False
        assert "legislativa o estadística" in reason

    @pytest.mark.parametrize(
        "title,source_text",
        [
            ('"Mi papá es malo": revelan testimonio de niño que presenció feminicidio de su mamá y abuela en Cuautitlán', 'Infobae México'),
            ('Capturan a Eric Antonio "N" por el feminicidio de Teresita y Cindy en Cuautitlán; hijo de 6 años narró el crimen', 'TV Azteca México'),
            ('Fiscalía de Michoacán ofrece recompensa de 100 mil pesos, por localización de René García, quien es acusado del feminicidio de su ex pareja Ana Gabriela y también de sustraer a su hijo de 2 años', 'Michoacán'),
            ('Moisés "N" asesinó a su esposa y llamó a su hijo para contarle detalles del feminicidio que cometió en calles de la CDMX', 'El Heraldo de México'),
            ('Cronología del doble feminicidio en Cuautitlán, Eric Antonio "N" las mató a pisadas dijo el hijo de Cindy', 'Eje Central México'),
            ('En Chiapas, mujer es asesinada a balazos por su pareja frente a sus tres hijos', 'Milenio'),
            ('Mujer es asesinada cuando iba a dejar a sus hijos a la escuela en Tochimilco | Puebla', 'e-consulta.com'),
            ('Feminicidio de Cindy en Cuautitlán: lo que se sabe del doble asesinato que dejó a dos menores en orfandad', 'Serendipia México'),
            ('¡Frente a su hijo de 5 años! Mariana es asesinada a balazos dentro de su carro en Naucalpan; iba con su pareja', 'Telediario México'),
            ('Asesinan a Mujer Vendedora de Frituras en Irapuato, Guanajuato; Era Madre de Dos Hijos', 'N+'),
            ('"Sus hijos están solos", familiar de Lina Alejandra revela que la empresaria asesinada era madre de 4 niños', 'El Heraldo de México'),
            ('Familiares de Ángela Louise Birkenbach protestan frente al DIF Nacional en Benito Juárez: exigen justicia por su feminicidio y protección para sus hijos', 'primeralinea.mx'),
        ],
    )
    def test_accepts_all_12_historical_real_cases(self, title, source_text):
        passed, reason = passes_admission_gate(title, source_text)
        assert passed is True, f"Falló admisión en caso real: {title} ({reason})"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. PRUEBAS DE LOS 5 CANDADOS ANTI-FALSOS POSITIVOS (`aplicar_candados_estrictos`)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCincoCandados:
    def test_all_five_locks_true_with_valid_quote_returns_alta(self):
        title = "Feminicidio en Puebla: asesinan a Elena y deja dos niños en la orfandad"
        content = (
            "Elena N., de 31 años, fue asesinada por su expareja en Tehuacán, Puebla. "
            "La víctima era madre de dos pequeños de 4 y 8 años que quedaron en la orfandad "
            "y actualmente están bajo resguardo de sus abuelos maternos."
        )
        schema = CasoExtraidoSchema(
            candado_1_es_caso_concreto=True,
            candado_2_ocurrio_en_mexico=True,
            candado_3_victima_mortal_es_mujer_madre=True,
            candado_4_menor_no_es_el_agresor=True,
            candado_5_hay_nna_huerfanos_o_sobrevivientes=True,
            cita_textual_evidencia="era madre de dos pequeños de 4 y 8 años que quedaron en la orfandad",
            clasificacion="Alta",
            confianza=0.96,
            estado="Puebla",
            municipio="Tehuacán",
            victimas="Elena N., 31 años",
            ninos_afectados=2,
            edades="4 y 8 años",
            situacion_actual="Bajo resguardo de abuelos maternos",
            medios_contacto="DIF Municipal de Tehuacán / FGE Puebla",
            resumen="Elena fue asesinada en Tehuacán dejando a dos niños de 4 y 8 años huérfanos.",
        )
        res = aplicar_candados_estrictos(schema, title, content)
        assert res["clasificacion_final"] == "Alta"
        assert res["es_relevante"] is True
        assert res["menores_identificados"] == "Si"
        assert res["nna_victima_indirecta"] == "Si"
        assert res["score_semantico"] >= 0.85
        assert res["investigacion_json"] is not None
        assert res["investigacion_json"]["ubicacion"] == "Tehuacán, Puebla"
        assert res["investigacion_json"]["ninos_afectados"] == 2
        assert res["investigacion_json"]["candados"]["cita_verificada_en_texto"] is True

    @pytest.mark.parametrize(
        "broken_field,expected_reason_fragment",
        [
            ("candado_1_es_caso_concreto", "Candado 1"),
            ("candado_2_ocurrio_en_mexico", "Candado 2"),
            ("candado_3_victima_mortal_es_mujer_madre", "Candado 3"),
            ("candado_4_menor_no_es_el_agresor", "Candado 4"),
            ("candado_5_hay_nna_huerfanos_o_sobrevivientes", "Candado 5"),
        ],
    )
    def test_any_single_broken_lock_forces_no_relevante_even_if_llm_says_alta(
        self, broken_field, expected_reason_fragment
    ):
        """
        Incluso si el LLM alucinara `clasificacion='Alta'` y `confianza=0.99`,
        si cualquiera de los 5 candados es False, Python fuerza 'No relevante'.
        """
        title = "Noticia de prueba en México"
        content = "La víctima era madre de dos niños que quedaron en orfandad."
        kwargs = {
            "candado_1_es_caso_concreto": True,
            "candado_2_ocurrio_en_mexico": True,
            "candado_3_victima_mortal_es_mujer_madre": True,
            "candado_4_menor_no_es_el_agresor": True,
            "candado_5_hay_nna_huerfanos_o_sobrevivientes": True,
            "cita_textual_evidencia": "era madre de dos niños que quedaron en orfandad",
            "clasificacion": "Alta",
            "confianza": 0.99,
        }
        kwargs[broken_field] = False
        schema = CasoExtraidoSchema(**kwargs)

        res = aplicar_candados_estrictos(schema, title, content)
        assert res["clasificacion_final"] == "No relevante"
        assert res["es_relevante"] is False
        assert res["investigacion_json"] is None
        assert expected_reason_fragment in res["motivo_descarte"]

    def test_hallucinated_quote_downgrades_alta_to_media(self):
        """
        Si el LLM pone los 5 candados en True pero inventa una cita que NO está
        en el texto de la noticia, el verificador anti-alucinaciones la degrada a 'Media'.
        """
        title = "Asesinan a una mujer en Monterrey, Nuevo León"
        content = "Vecinos reportaron detonaciones en la colonia Independencia de Monterrey."
        schema = CasoExtraidoSchema(
            candado_1_es_caso_concreto=True,
            candado_2_ocurrio_en_mexico=True,
            candado_3_victima_mortal_es_mujer_madre=True,
            candado_4_menor_no_es_el_agresor=True,
            candado_5_hay_nna_huerfanos_o_sobrevivientes=True,
            cita_textual_evidencia="Sus cuatro pequeños hijos quedaron resguardados por el DIF estatal",
            clasificacion="Alta",
            confianza=0.95,
        )
        res = aplicar_candados_estrictos(schema, title, content)
        assert res["clasificacion_final"] == "Media"
        assert res["auditoria_completa"]["candados"]["cita_verificada_en_texto"] is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. PRUEBAS DEL CONECTOR MULTI-PROVEEDOR Y FALLBACK DETERMINISTA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestLLMExtractorFlow:
    def test_deterministic_fallback_identifies_real_case_and_rejects_traps(self, monkeypatch):
        """Sin API keys configuradas, el fallback determinista local debe acertar casos reales y rechazar trampas."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        extractor = LLMExtractor()
        assert extractor.providers == []

        # Caso 1: Positivo Verdadero
        vp = extractor.analyze_article(
            title="Feminicidio en Ecatepec: asesinan a joven madre frente a sus dos hijos",
            content=(
                "Una mujer de 26 años fue asesinada en Ecatepec, Estado de México. "
                "El ataque ocurrió frente a sus dos hijos menores de 4 y 6 años, "
                "quienes quedaron en orfandad bajo resguardo del DIF."
            ),
        )
        assert vp["clasificacion_final"] == "Alta"
        assert vp["menores_identificados"] == "Si"

        # Caso 2: Falso Positivo — Niña como víctima directa sin hijos huérfanos
        fp_nina = extractor.analyze_article(
            title="Justicia por el feminicidio de niña de 8 años en Chihuahua",
            content=(
                "Una niña de 8 años fue hallada sin vida en Ciudad Juárez, Chihuahua. "
                "Su madre exigió justicia ante la Fiscalía del Estado por el asesinato de su hija."
            ),
        )
        assert fp_nina["clasificacion_final"] == "No relevante"

        # Caso 3: Falso Positivo — Estadísticas de orfandad
        fp_stats = extractor.analyze_article(
            title="REDIM advierte que cifras de feminicidio dejan miles de niños huérfanos en México",
            content=(
                "De acuerdo con estadísticas de feminicidio e informe anual del INEGI, "
                "en la última década miles de menores han quedado en orfandad en México."
            ),
        )
        assert fp_stats["clasificacion_final"] == "No relevante"

    def test_provider_fallback_on_rate_limit(self, monkeypatch):
        """
        Si el primer proveedor (Groq) devuelve 429 Rate Limit, LLMExtractor
        salta automáticamente al segundo proveedor (Gemini) sin fallar.
        """
        monkeypatch.setenv("GROQ_API_KEY", "fake-groq-key")
        monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

        extractor = LLMExtractor()
        assert [p["name"] for p in extractor.providers[:2]] == ["groq", "gemini"]

        title = "Asesinan a madre de tres niños en Xalapa, Veracruz"
        content = (
            "Una mujer fue asesinada en Xalapa, Veracruz. "
            "La víctima dejó tres hijos menores en la orfandad que fueron entregados al DIF."
        )

        mock_gemini_response = {
            "candado_1_es_caso_concreto": True,
            "candado_2_ocurrio_en_mexico": True,
            "candado_3_victima_mortal_es_mujer_madre": True,
            "candado_4_menor_no_es_el_agresor": True,
            "candado_5_hay_nna_huerfanos_o_sobrevivientes": True,
            "cita_textual_evidencia": "La víctima dejó tres hijos menores en la orfandad que fueron entregados al DIF.",
            "motivo_descarte": None,
            "clasificacion": "Alta",
            "confianza": 0.94,
            "estado": "Veracruz",
            "municipio": "Xalapa",
            "ubicacion": "Xalapa, Veracruz",
            "victimas": "Mujer no identificada",
            "ninos_afectados": 3,
            "edades": "Menores de edad",
            "situacion_actual": "Entregados al DIF",
            "medios_contacto": "DIF Xalapa",
            "resumen": "Mujer asesinada en Xalapa deja tres hijos en la orfandad bajo resguardo del DIF.",
        }

        with patch.object(
            extractor, "_call_openai_compatible", side_effect=RuntimeError("Rate limit (429) en proveedor groq")
        ) as mock_groq, patch.object(
            extractor, "_call_gemini", return_value=mock_gemini_response
        ) as mock_gemini:
            result = extractor.analyze_article(title, content)

        assert mock_groq.called
        assert mock_gemini.called
        assert result["clasificacion_final"] == "Alta"
        assert result["modo"].startswith("llm_gemini:")
        assert result["investigacion_json"]["ubicacion"] == "Xalapa, Veracruz"
        assert result["investigacion_json"]["ninos_afectados"] == 3
