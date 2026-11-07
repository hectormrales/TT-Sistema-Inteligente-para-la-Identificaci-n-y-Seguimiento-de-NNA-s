"""
src/analysis/semantic_detector.py
=================================
Fachada ligera de detección semántica impulsada por LLMExtractor y los 5 Candados
Anti-Falsos-Positivos (Producción v2026).

Reemplaza la antigua pila pesada de PyTorch + BETO + spaCy (~1 GB RAM) por
`LLMExtractor` (Groq / Gemini / OpenRouter / Azure OpenAI + Fallback Determinista
con 5 candados estrictos), manteniendo compatibilidad total con la interfaz
`SemanticDetector` usada por el pipeline y las pruebas unitarias.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from src.analysis.llm_extractor import LLMExtractor

logger = logging.getLogger(__name__)

# Atributos simbólicos mantenidos por compatibilidad con mocks de pruebas unitarias
AutoTokenizer = None
AutoModel = None


class SemanticDetector:
    """
    Detector semántico basado en `LLMExtractor` con 5 candados estrictos.
    No requiere `torch`, `transformers` ni `spacy`.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        mode: str = "llm_5_candados",
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.model_path = model_path
        self.mode = mode
        self.extractor = LLMExtractor(preferred_provider=provider)

    @staticmethod
    def _confidence_level(score: float) -> str:
        """
        Determina el nivel de confianza de una predicción según su distancia al umbral 0.5.
        """
        distance = abs(score - 0.5)
        if distance > 0.3:
            return "alta"
        elif distance > 0.15:
            return "media"
        return "baja"

    def predict(
        self,
        titulo: str,
        contenido: str,
        score_heuristico: Optional[float] = None,
        enlace: str = "",
    ) -> dict:
        """
        Evalúa una noticia individual con los 5 candados de `LLMExtractor`.
        """
        res = self.extractor.analyze_article(
            title=titulo,
            content=contenido,
            source_url=enlace,
        )
        score_sem = float(res.get("score_semantico", 0.05))
        return {
            "score_semantico": score_sem,
            "score_final": score_sem,
            "relevancia_final": score_sem,
            "clasificacion": res.get("clasificacion", "No relevante"),
            "clasificacion_final": res.get("clasificacion_final", "No relevante"),
            "menores_identificados": res.get("menores_identificados", "No"),
            "modo_deteccion": res.get("modo_deteccion", self.mode),
            "nivel_confianza": self._confidence_level(score_sem),
            "investigacion_json": res.get("investigacion_json"),
        }

    def predict_batch(
        self,
        titulos: list[str],
        contenidos: list[str],
        enlaces: Optional[list[str]] = None,
        batch_size: int = 16,
    ) -> list[dict]:
        """
        Evalúa un lote de noticias con Gatekeeper + LLMExtractor (5 candados).
        """
        batch_results = self.extractor.analyze_batch(
            titles=titulos,
            contents=contenidos,
            urls=enlaces,
        )
        enriched: list[dict] = []
        for item in batch_results:
            score_sem = float(item.get("score_semantico", 0.05))
            item["score_final"] = score_sem
            item["nivel_confianza"] = self._confidence_level(score_sem)
            enriched.append(item)
        return enriched

    def prepare_training_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepara un DataFrame etiquetado (`texto`, `etiqueta`) para auditoría o
        evaluación de clasificadores a partir de resultados históricos.
        """
        data = df.copy()
        titulos = data.get("titulo", pd.Series("", index=data.index)).fillna("").astype(str)
        contenidos = data.get("contenido", pd.Series("", index=data.index)).fillna("").astype(str)
        data["texto"] = titulos + " [SEP] " + contenidos

        clasif_col = (
            "clasificacion_final"
            if "clasificacion_final" in data.columns
            else "clasificacion"
        )
        score_col = (
            "relevancia_final"
            if "relevancia_final" in data.columns
            else "score_compuesto"
        )

        def _label_row(row) -> int:
            c = str(row.get(clasif_col, "No relevante"))
            s = float(row.get(score_col, 0.0) or 0.0)
            if c == "Alta" or (c == "Media" and s >= 0.50):
                return 1
            return 0

        data["etiqueta"] = data.apply(_label_row, axis=1).astype(int)
        result = data[["texto", "etiqueta"]].dropna().reset_index(drop=True)
        return result
