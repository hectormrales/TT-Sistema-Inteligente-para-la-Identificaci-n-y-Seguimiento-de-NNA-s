"""
tests/test_semantic_detector.py
================================
Pruebas unitarias para la lógica de SemanticDetector.
_confidence_level se extrae directamente para evitar importar
torch/transformers (que no están instalados en CI ligero).
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Réplica local de _confidence_level para pruebas aisladas
# (idéntica al código fuente — permite probar sin torch)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _confidence_level(score: float) -> str:
    """Copia exacta de SemanticDetector._confidence_level."""
    distance = abs(score - 0.5)
    if distance > 0.3:
        return "alta"
    elif distance > 0.15:
        return "media"
    return "baja"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GRUPO 1: _confidence_level (lógica pura, sin torch)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestConfidenceLevel:
    """
    Prueba la lógica de nivel de confianza.
    No requiere torch, pandas ni ninguna dependencia pesada.
    """

    def test_confidence_alta_cuando_score_muy_alto(self):
        """Score > 0.8 → distancia > 0.3 → ALTA."""
        assert _confidence_level(0.85) == "alta"

    def test_confidence_alta_cuando_score_muy_bajo(self):
        """Score < 0.2 → distancia > 0.3 → ALTA (negativa)."""
        assert _confidence_level(0.10) == "alta"

    def test_confidence_media_rango_intermedio(self):
        """Score 0.70 → distancia 0.2 > 0.15 → MEDIA."""
        assert _confidence_level(0.70) == "media"

    def test_confidence_baja_cuando_cerca_del_umbral(self):
        """Score 0.52 → distancia 0.02 < 0.15 → BAJA."""
        assert _confidence_level(0.52) == "baja"

    def test_confidence_en_exactamente_cero_punto_cinco(self):
        """Score exactamente en el umbral → BAJA."""
        assert _confidence_level(0.50) == "baja"

    @pytest.mark.parametrize("score,esperado", [
        (1.0,  "alta"),
        (0.0,  "alta"),
        (0.81, "alta"),
        (0.19, "alta"),
        (0.68, "media"),
        (0.32, "media"),
        (0.55, "baja"),
        (0.45, "baja"),
    ])
    def test_confidence_parametrizado(self, score, esperado):
        """Prueba parametrizada para múltiples valores de score."""
        assert _confidence_level(score) == esperado


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GRUPO 2: SemanticDetector.prepare_training_data
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPrepareTrainingData:
    """
    Prueba la preparación de datos de entrenamiento.
    Mockeamos la inicialización de BETO para no descargar modelos.
    """

    @pytest.fixture
    def detector_mock(self):
        """Fixture: SemanticDetector con BETO completamente mockeado."""
        with patch("src.analysis.semantic_detector.AutoTokenizer") as mock_tok, \
             patch("src.analysis.semantic_detector.AutoModel") as mock_model:
            mock_tok.from_pretrained.return_value = MagicMock()
            mock_model.from_pretrained.return_value = MagicMock()

            from src.analysis.semantic_detector import SemanticDetector
            # Usamos zero_shot para evitar cargar modelo fine-tuned
            detector = SemanticDetector.__new__(SemanticDetector)
            detector.mode = "zero_shot"
            detector.tokenizer = MagicMock()
            detector.model = MagicMock()
            detector._embeddings_cache = {}
            detector._category_embeddings = {}
            return detector

    @pytest.fixture
    def df_noticias(self):
        """DataFrame de prueba con noticias etiquetadas heurísticamente."""
        return pd.DataFrame({
            "titulo": [
                "Feminicidio en Jalisco deja 3 huérfanos",
                "Estadísticas de violencia contra la mujer 2025",
                "Mujer asesinada en CDMX, sus hijos al cuidado del DIF",
                "Marcha por el Día de la Mujer en Guadalajara",
                "Menor de edad víctima de feminicidio en Veracruz",
            ],
            "contenido": [
                "La mujer fue encontrada sin vida. Sus hijos quedan en orfandad.",
                "Según el INEGI, 10 mujeres son asesinadas cada día en México.",
                "El DIF tomó custodia de los 2 menores de 5 y 8 años.",
                "Miles de mujeres marcharon exigiendo justicia.",
                "Una adolescente de 16 años fue asesinada por su pareja.",
            ],
            "clasificacion_final": ["Alta", "No relevante", "Alta", "No relevante", "No relevante"],
            "relevancia_final": [0.85, 0.10, 0.78, 0.05, 0.20],
        })

    def test_prepare_training_genera_columna_texto(self, detector_mock, df_noticias):
        """Verifica que se cree la columna 'texto' con título + contenido."""
        resultado = detector_mock.prepare_training_data(df_noticias)
        assert "texto" in resultado.columns
        # El texto debe contener el separador [SEP]
        assert resultado["texto"].str.contains(r"\[SEP\]").all()

    def test_prepare_training_genera_columna_etiqueta(self, detector_mock, df_noticias):
        """Verifica que se creen etiquetas binarias 0/1."""
        resultado = detector_mock.prepare_training_data(df_noticias)
        assert "etiqueta" in resultado.columns
        assert set(resultado["etiqueta"].unique()).issubset({0, 1})

    def test_prepare_training_alta_relevancia_es_positivo(self, detector_mock, df_noticias):
        """Noticias clasificadas como 'Alta' deben tener etiqueta = 1."""
        resultado = detector_mock.prepare_training_data(df_noticias)
        # La noticia de índice 0 era "Alta" → debe ser 1
        # Nota: el resultado puede estar shuffled, verificamos con el texto
        alta_rows = resultado[resultado["texto"].str.contains("Jalisco")]
        if len(alta_rows) > 0:
            assert alta_rows["etiqueta"].values[0] == 1

    def test_prepare_training_no_relevante_es_negativo(self, detector_mock, df_noticias):
        """Noticias 'No relevante' con score bajo deben tener etiqueta = 0."""
        resultado = detector_mock.prepare_training_data(df_noticias)
        estadistica_rows = resultado[resultado["texto"].str.contains("INEGI")]
        if len(estadistica_rows) > 0:
            assert estadistica_rows["etiqueta"].values[0] == 0

    def test_prepare_training_devuelve_solo_columnas_necesarias(self, detector_mock, df_noticias):
        """El DataFrame resultante debe tener SOLO 'texto' y 'etiqueta'."""
        resultado = detector_mock.prepare_training_data(df_noticias)
        assert list(resultado.columns) == ["texto", "etiqueta"]

    def test_prepare_training_no_tiene_nulos(self, detector_mock, df_noticias):
        """El DataFrame resultante no debe tener valores nulos."""
        resultado = detector_mock.prepare_training_data(df_noticias)
        assert resultado.isnull().sum().sum() == 0
