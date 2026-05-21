# src/analysis/semantic_detector.py — Detector semántico con BETO/BERT
"""
OE-1: Migración de detección sintáctica a semántica.

Implementa un clasificador binario basado en BETO (BERT para español)
para determinar si una noticia está relacionada con feminicidio/NNA.

Arquitectura:
  ┌─────────────────────────────────────────────────────────┐
  │  Texto (título + contenido)                             │
  │         ↓                                               │
  │  Tokenizer BETO (WordPiece, max_length=512)             │
  │         ↓                                               │
  │  BETO Encoder (12 capas Transformer, 768-dim)           │
  │         ↓                                               │
  │  [CLS] token → embedding 768-dim                        │
  │         ↓                                               │
  │  Clasificador binario (Linear 768→256→1 + Sigmoid)      │
  │         ↓                                               │
  │  P(relevante) ∈ [0, 1]                                  │
  └─────────────────────────────────────────────────────────┘

Modos de operación (prioridad v5.1):
  1. Fine-tuned (PRIORITARIO): Clasificador binario entrenado con datos
     etiquetados del pipeline heurístico. Es el único modo que comprende
     sintaxis relacional (ej. "niña sobrevive" ≠ "niña asesinada").
  2. Zero-shot (ÚLTIMO RECURSO): Similitud coseno con BETO pre-entrenado.
     Genera falsos positivos en contextos relacionales. Solo se activa si
     no existe modelo fine-tuned, con advertencia explícita en el logger.
  3. Auto: Selecciona finetuned si el modelo existe, zero_shot con warning
     si no existe.

Modelo base:
  - dccuchile/bert-base-spanish-wwm-cased (BETO)
  - Entrenado con corpus en español (Wikipedia + OPUS)
  - 110M parámetros, 12 capas, 768-dim embeddings

Métricas objetivo (OE-1):
  - Precisión ≥ 95%
  - Recall ≥ 90%
  - Falsos positivos ≤ 3%
"""

import os
import json
import logging
import hashlib
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModel,
    AutoModelForSequenceClassification,
    pipeline,
)
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    classification_report, confusion_matrix,
)

logger = logging.getLogger(__name__)

# Import lazy del módulo PoC de roles (spaCy — carga pesada, se hace on-demand)
try:
    from scripts.poc_roles_victimas import analizar_roles_victimas as _poc_analizar
    _POC_DISPONIBLE = True
except ImportError:
    try:
        # Fallback: módulo en el mismo directorio / PYTHONPATH alternativo
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / "scripts"))
        from poc_roles_victimas import analizar_roles_victimas as _poc_analizar
        _POC_DISPONIBLE = True
    except ImportError:
        _poc_analizar = None
        _POC_DISPONIBLE = False
        logger.warning(
            "[SemanticDetector] poc_roles_victimas no encontrado. "
            "Pre-filtro sintáctico DESHABILITADO."
        )
 
# ── Configuración del modelo ────────────────────────────────

BETO_MODEL_NAME = "dccuchile/bert-base-spanish-wwm-cased"
MAX_SEQ_LENGTH = 512
BATCH_SIZE = 4
LEARNING_RATE = 2e-5
NUM_EPOCHS = 4
WARMUP_RATIO = 0.1
CACHE_DIR = os.environ.get("MODEL_CACHE_DIR", "models/cache")
FINETUNED_DIR = os.environ.get("FINETUNED_MODEL_DIR", "models/finetuned")

# Descripciones de categorías para zero-shot classification
# v2.0: Descripciones mucho más específicas para el caso de uso exacto.
CATEGORY_DESCRIPTIONS = {
    "relevante": (
        "Caso individual, particular y concreto de feminicidio en México donde una mujer fue asesinada, "
        "y como consecuencia directa, sus propios hijos (niños, niñas o adolescentes) "
        "quedaron huérfanos, desamparados o fueron resguardados por el DIF u otra autoridad. "
        "Noticia que relata un evento criminal específico detallando la pérdida de la madre y el impacto directo en sus hijos menores."
    ),
    "no_relevante": (
        "Noticia general que NO relata un caso de orfandad por feminicidio. "
        "ESTO INCLUYE Y DEBE CLASIFICARSE COMO NO RELEVANTE: "
        "1. Cifras, estadísticas, informes anuales o reportes trimestrales de violencia. "
        "2. Políticas públicas, leyes, debates en el congreso, programas de becas o entregas de apoyos económicos. "
        "3. Feminicidios donde la persona asesinada (víctima directa) es una niña, menor de edad o adolescente. "
        "4. Crímenes donde el agresor o asesino es un menor de edad o el propio hijo de la víctima. "
        "5. Marchas, protestas, columnas de opinión o conferencias sin relatar un crimen en particular."
    ),
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dataset para fine-tuning
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class NNANewsDataset(Dataset):
    """
    Dataset PyTorch para noticias etiquetadas.

    Cada muestra es (texto, etiqueta):
      - texto: título + " [SEP] " + contenido (truncado a MAX_SEQ_LENGTH)
      - etiqueta: 1 = relevante (feminicidio/NNA), 0 = no relevante

    La tokenización usa WordPiece de BETO que divide palabras
    desconocidas en sub-tokens, permitiendo manejar vocabulario abierto.
    """

    def __init__(
        self,
        texts: list[str],
        labels: list[int],
        tokenizer,
        max_length: int = MAX_SEQ_LENGTH,
    ):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.texts[idx],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels": torch.tensor(self.labels[idx], dtype=torch.long),
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Clasificador binario con cabeza de clasificación
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BETOClassifier(nn.Module):
    """
    Clasificador binario basado en BETO.

    Arquitectura de la cabeza de clasificación:
      [CLS] embedding (768) → Dropout(0.3) → Linear(768, 256)
      → ReLU → Dropout(0.2) → Linear(256, 2) → Softmax

    La capa de dropout previene sobre-ajuste.
    ReLU introduce no-linealidad necesaria para aprender
    patrones complejos de relevancia.
    """

    def __init__(self, num_classes: int = 2, dropout: float = 0.3):
        super().__init__()
        self.bert = AutoModel.from_pretrained(
            BETO_MODEL_NAME, cache_dir=CACHE_DIR
        )
        hidden_size = self.bert.config.hidden_size  # 768

        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, num_classes),
        )

    def forward(self, input_ids, attention_mask, labels=None):
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )
        # Usar el token [CLS] (primer token) como representación
        cls_output = outputs.last_hidden_state[:, 0, :]
        logits = self.classifier(cls_output)

        loss = None
        if labels is not None:
            loss_fn = nn.CrossEntropyLoss()
            loss = loss_fn(logits, labels)

        return {"loss": loss, "logits": logits}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Detector semántico principal
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SemanticDetector:
    """
    Detector semántico de noticias relevantes usando BETO.

    Soporta tres modos de operación:
      1. zero_shot: Clasificación sin entrenamiento previo.
         Usa embeddings de BETO para calcular similitud coseno
         entre el texto y descripciones de categorías.
      2. finetuned: Clasificador entrenado con datos del sistema.
      3. hybrid: Combina score semántico + heurístico.

    El modo se selecciona automáticamente:
      - Si existe modelo fine-tuned guardado → usa finetuned
      - Si hay GPU disponible → usa zero_shot
      - Fallback → usa embeddings para scoring
    """

    def __init__(self, mode: str = "auto"):
        """
        Args:
            mode: 'zero_shot', 'finetuned', 'hybrid', 'auto'
        """
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        logger.info(f"SemanticDetector usando dispositivo: {self.device}")

        self.tokenizer = None
        self.model = None
        self.zero_shot_pipeline = None
        self._embeddings_cache: dict[str, np.ndarray] = {}
        self.mode = mode

        # Pre-filtro sintáctico (spaCy) — carga lazy
        self._spacy_nlp = None          # instancia spaCy (se carga al primer uso)
        self._prefiltro_habilitado = _POC_DISPONIBLE

        if mode == "auto":
            self.mode = self._detect_mode()

        self._initialize()

    def _detect_mode(self) -> str:
        """
        Detecta el mejor modo disponible (v5.1).

        Prioridad estricta:
          1. finetuned — si model.pt existe en FINETUNED_DIR
          2. zero_shot — ÚLTIMO RECURSO con advertencia explícita

        Zero-shot produce falsos positivos críticos en contextos
        relacionales (ej. "madre asesinada, niña sobrevive").
        Se requiere ejecutar fine_tune() antes de usar en producción.
        """
        finetuned_path = os.path.join(FINETUNED_DIR, "model.pt")
        if os.path.exists(finetuned_path):
            logger.info(f"Modelo fine-tuned encontrado en: {finetuned_path}")
            return "finetuned"

        logger.warning(
            "[SemanticDetector] ⚠️  MODELO FINE-TUNED NO ENCONTRADO en '%s'. "
            "Cayendo en zero_shot como último recurso. "
            "Este modo genera falsos positivos en contextos relacionales. "
            "Ejecute fine_tune() con datos etiquetados antes de usar en producción.",
            FINETUNED_DIR,
        )
        return "zero_shot"

    def _initialize(self):
        """
        Inicializa tokenizer y modelo según el modo (v5.1).

        Para 'finetuned': carga model.pt desde FINETUNED_DIR.
        Para 'zero_shot': advierte del riesgo y carga BETO base.
        Para 'hybrid': intenta finetuned; si falla, cae en zero_shot CON WARNINGS.
        """
        logger.info(f"Inicializando SemanticDetector en modo: {self.mode}")

        os.makedirs(CACHE_DIR, exist_ok=True)

        # Tokenizer siempre necesario
        self.tokenizer = AutoTokenizer.from_pretrained(
            BETO_MODEL_NAME, cache_dir=CACHE_DIR
        )

        if self.mode == "finetuned":
            self._load_finetuned()

        elif self.mode == "zero_shot":
            logger.warning(
                "[SemanticDetector] ⚠️  Modo zero_shot activo. "
                "La similitud coseno NO comprende sintaxis relacional. "
                "Se recomienda ejecutar fine_tune() para producción."
            )
            self._init_zero_shot()

        elif self.mode == "hybrid":
            try:
                self._load_finetuned()
                logger.info("Modo hybrid: usando modelo fine-tuned como base")
            except FileNotFoundError:
                logger.warning(
                    "[SemanticDetector] ⚠️  Modo hybrid: fine-tuned no disponible. "
                    "Degradando a zero_shot. Ejecute fine_tune() para mejorar precisión."
                )
                self.mode = "zero_shot"
                self._init_zero_shot()

    def _init_zero_shot(self):
        """
        Inicializa clasificación zero-shot.

        Usa el modelo BETO base para generar embeddings del texto
        y las descripciones de categorías. La clasificación se hace
        por similitud coseno entre embeddings.

        Ventaja: No requiere datos de entrenamiento.
        Limitación: Precisión inferior a fine-tuning (~80-85%).
        """
        self.model = AutoModel.from_pretrained(
            BETO_MODEL_NAME, cache_dir=CACHE_DIR
        ).to(self.device)
        self.model.eval()

        # Pre-calcular embeddings de categorías
        self._category_embeddings = {}
        for cat, desc in CATEGORY_DESCRIPTIONS.items():
            self._category_embeddings[cat] = self._get_embedding(desc)

        logger.info("Zero-shot inicializado con embeddings de categorías")

    def _load_finetuned(self):
        """Carga modelo fine-tuned desde disco."""
        finetuned_path = os.path.join(FINETUNED_DIR, "model.pt")
        if not os.path.exists(finetuned_path):
            raise FileNotFoundError(
                f"Modelo fine-tuned no encontrado en {finetuned_path}"
            )

        self.model = BETOClassifier(num_classes=2)
        self.model.load_state_dict(
            torch.load(finetuned_path, map_location=self.device, weights_only=True)
        )
        self.model.to(self.device)
        self.model.eval()
        logger.info(f"Modelo fine-tuned cargado desde {finetuned_path}")

    def _get_embedding(self, text: str) -> np.ndarray:
        """
        Obtiene embedding [CLS] de BETO para un texto.

        El token [CLS] en BERT/BETO es una representación condensada
        de toda la secuencia, entrenada para capturar el significado
        global del texto.

        Proceso:
          1. Tokenización WordPiece del texto
          2. Forward pass por las 12 capas Transformer
          3. Extracción del hidden state del token [CLS]
          4. Normalización L2 para similitud coseno

        Returns:
            Vector numpy de 768 dimensiones normalizado.
        """
        # Cache por hash del texto
        text_hash = hashlib.md5(text[:500].encode()).hexdigest()
        if text_hash in self._embeddings_cache:
            return self._embeddings_cache[text_hash]

        inputs = self.tokenizer(
            text,
            max_length=MAX_SEQ_LENGTH,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

        # [CLS] token embedding
        cls_emb = outputs.last_hidden_state[:, 0, :].cpu().numpy().flatten()

        # Normalización L2
        norm = np.linalg.norm(cls_emb)
        if norm > 0:
            cls_emb = cls_emb / norm

        self._embeddings_cache[text_hash] = cls_emb
        return cls_emb

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Similitud coseno entre dos vectores normalizados."""
        return float(np.dot(a, b))

    # ── Pre-filtro sintáctico (spaCy + PoC) ──────────────────

    def _cargar_spacy(self):
        """Carga es_core_news_lg de forma lazy (solo la primera vez que se necesita)."""
        if self._spacy_nlp is None:
            try:
                import spacy
                self._spacy_nlp = spacy.load("es_core_news_lg")
                logger.info("[PreFiltro] Modelo spaCy es_core_news_lg cargado.")
            except Exception as exc:
                logger.warning(
                    "[PreFiltro] No se pudo cargar spaCy (%s). "
                    "Pre-filtro deshabilitado para esta sesión.", exc
                )
                self._prefiltro_habilitado = False

    def pre_filtro_sintactico(self, texto: str) -> dict:
        """
        Ejecuta la PoC de roles víctima/agresor sobre el texto ANTES de BETO.

        Objetivo dual:
          1. BLOQUEO rápido (score=0.0): si la PoC detecta que el menor es
             víctima directa de violencia (FP sintáctico confirmado), se
             retorna inmediatamente sin invocar BETO — ahorrando ~200-600 ms
             de inferencia por noticia y blindando el sistema.
          2. ACELERACIÓN positiva: si la PoC confirma el patrón
             (mujer víctima + menor superviviente), se añade la señal al
             dict de retorno para que predict() pueda usarla como boost
             si lo desea en versiones futuras.

        Args:
            texto: Texto completo de la noticia (título + contenido).

        Returns:
            dict con claves:
              - habilitado (bool): Si el pre-filtro pudo ejecutarse.
              - bloquear (bool): True ⇒ FP confirmado, NO pasar a BETO.
              - caso_valido (bool): True ⇒ PoC detectó patrón positivo.
              - roles (dict): Detalle de roles extraídos por la PoC.
              - razon (str): Descripción legible del resultado.
        """
        if not self._prefiltro_habilitado:
            return {"habilitado": False, "bloquear": False,
                    "caso_valido": False, "roles": {}, "razon": "pre-filtro no disponible"}

        self._cargar_spacy()
        if not self._prefiltro_habilitado:  # carga falló
            return {"habilitado": False, "bloquear": False,
                    "caso_valido": False, "roles": {}, "razon": "spaCy no disponible"}

        try:
            caso_valido, roles = _poc_analizar(texto, self._spacy_nlp)
            es_fp = roles.get("menor_victima_directa", False)

            if es_fp:
                razon = (
                    f"FP bloqueado: menor como víctima directa de violencia — "
                    f"verbo(s): {[t.get('verbo') for t in roles.get('oraciones_procesadas', []) if t.get('tipo') == 'FALSO_POSITIVO']}"
                )
                logger.info("[PreFiltro] BLOQUEO → %s", razon)
                return {
                    "habilitado": True, "bloquear": True,
                    "caso_valido": False, "roles": roles, "razon": razon,
                }

            razon = "caso_valido" if caso_valido else "sin_evidencia_suficiente"
            return {
                "habilitado": True, "bloquear": False,
                "caso_valido": caso_valido, "roles": roles, "razon": razon,
            }

        except Exception as exc:
            logger.warning("[PreFiltro] Error en análisis sintáctico: %s", exc)
            return {"habilitado": False, "bloquear": False,
                    "caso_valido": False, "roles": {}, "razon": str(exc)}

    # ── Clasificación ───────────────────────────────────────

    def predict(self, title: str, content: str) -> dict:
        """
        Clasifica una noticia como relevante o no relevante.

        Flujo con pre-filtro sintáctico (v3):
          1. pre_filtro_sintactico(): análisis spaCy de roles víctima/agresor.
             • Si hay FP confirmado (menor asesinado) → retorna score=0.0
               SIN invocar BETO (ahorra ~200-600 ms por noticia).
             • Si no hay bloqueo → continúa con BETO normalmente.
          2. BETO (finetuned o zero_shot).

        Args:
            title: Título de la noticia.
            content: Contenido/cuerpo de la noticia.

        Returns:
            dict con:
              - score_semantico (float): Probabilidad de relevancia [0, 1]
              - es_relevante (bool): True si score >= 0.5
              - confianza (str): 'alta', 'media', 'baja'
              - modo (str): modo de clasificación usado
              - prefiltro (dict): resultado del pre-filtro sintáctico
        """
        texto_completo = f"{title} {content[:1500]}"

        # ── Pre-filtro sintáctico ────────────────────────────────────────
        prefiltro = self.pre_filtro_sintactico(texto_completo)
        if prefiltro["bloquear"]:
            return {
                "score_semantico": 0.0,
                "es_relevante": False,
                "confianza": "alta",
                "modo": "prefiltro_sintactico_bloqueado",
                "clasificacion": "No relevante",
                "prefiltro": prefiltro,
            }

        # ── Inferencia BETO ──────────────────────────────────────────────
        text = f"{title} [SEP] {content[:1500]}"
        if self.mode == "finetuned":
            resultado = self._predict_finetuned(text)
        else:
            resultado = self._predict_zero_shot(text)

        resultado["prefiltro"] = prefiltro
        return resultado

    def _predict_zero_shot(self, text: str) -> dict:
        """
        Clasificación zero-shot por similitud coseno.

        Calcula la similitud entre el embedding del texto y los
        embeddings de las descripciones de categorías.
        La categoría con mayor similitud determina la clasificación.

        score = sim(texto, "relevante") / (sim(texto, "relevante") + sim(texto, "no_relevante"))
        """
        text_emb = self._get_embedding(text)

        sim_relevante = self._cosine_similarity(
            text_emb, self._category_embeddings["relevante"]
        )
        sim_no_relevante = self._cosine_similarity(
            text_emb, self._category_embeddings["no_relevante"]
        )

        # Normalizar a probabilidad con softmax
        exp_rel = np.exp(sim_relevante * 5)  # Factor de temperatura
        exp_norel = np.exp(sim_no_relevante * 5)
        score = exp_rel / (exp_rel + exp_norel)

        return {
            "score_semantico": round(float(score), 4),
            "es_relevante": score >= 0.5,
            "confianza": self._confidence_level(score),
            "modo": "zero_shot",
            "sim_relevante": round(float(sim_relevante), 4),
            "sim_no_relevante": round(float(sim_no_relevante), 4),
        }

    def _predict_finetuned(self, text: str) -> dict:
        """
        Clasificación con modelo fine-tuned.

        Pasa el texto por BETO + cabeza de clasificación.
        El output son logits que se convierten a probabilidades con softmax.
        """
        inputs = self.tokenizer(
            text,
            max_length=MAX_SEQ_LENGTH,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
            )

        logits = outputs["logits"]
        probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
        score = float(probs[1])  # Probabilidad de clase "relevante"

        return {
            "score_semantico": round(score, 4),
            "es_relevante": score >= 0.5,
            "confianza": self._confidence_level(score),
            "modo": "finetuned",
        }

    def predict_batch(
        self, titles: list[str], contents: list[str]
    ) -> list[dict]:
        """
        Clasificación por lotes para eficiencia.

        Flujo con pre-filtro sintáctico (v3):
          Para cada noticia, ejecuta pre_filtro_sintactico() ANTES de
          acumular el lote para BETO. Las noticias con FP confirmado se
          cortocircuitan inmediatamente (score=0.0) y NO entran al lote
          de inferencia BETO, reduciendo el tamaño efectivo del batch.

        Procesa el resto en lotes de BATCH_SIZE, aprovechando paralelismo
        de GPU si está disponible.
        """
        n = len(titles)
        # Mapa: índice original → resultado (para los FP bloqueados)
        resultados_finales: list[Optional[dict]] = [None] * n
        # Índices y textos que SHI pasan al batch BETO
        indices_beto: list[int] = []
        texts_beto: list[str] = []

        # ── Pre-filtro por noticia ──────────────────────────────────
        for idx, (title, content) in enumerate(zip(titles, contents)):
            texto_completo = f"{title} {content[:1500]}"
            prefiltro = self.pre_filtro_sintactico(texto_completo)
            if prefiltro["bloquear"]:
                resultados_finales[idx] = {
                    "score_semantico": 0.0,
                    "es_relevante": False,
                    "confianza": "alta",
                    "modo": "prefiltro_sintactico_bloqueado",
                    "clasificacion": "No relevante",
                    "prefiltro": prefiltro,
                }
            else:
                indices_beto.append(idx)
                texts_beto.append(f"{title} [SEP] {content[:1500]}")

        # ── Batch BETO solo con las noticias no bloqueadas ───────────
        if texts_beto:
            if self.mode == "finetuned":
                dataset = NNANewsDataset(
                    texts_beto, [0] * len(texts_beto), self.tokenizer
                )
                loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=False)

                beto_results: list[dict] = []
                self.model.eval()
                with torch.no_grad():
                    for batch in loader:
                        input_ids = batch["input_ids"].to(self.device)
                        attention_mask = batch["attention_mask"].to(self.device)

                        outputs = self.model(
                            input_ids=input_ids,
                            attention_mask=attention_mask,
                        )
                        probs = torch.softmax(outputs["logits"], dim=1)
                        scores = probs[:, 1].cpu().numpy()

                        for score in scores:
                            s = float(score)
                            beto_results.append({
                                "score_semantico": round(s, 4),
                                "es_relevante": s >= 0.5,
                                "confianza": self._confidence_level(s),
                                "modo": "finetuned",
                            })
            else:
                beto_results = self._predict_zero_shot_batch(texts_beto)

            # Reinsertar en posiciones originales
            for local_idx, orig_idx in enumerate(indices_beto):
                resultados_finales[orig_idx] = beto_results[local_idx]

        return resultados_finales  # type: ignore[return-value]

    def _get_embeddings_batch(self, texts: list[str]) -> np.ndarray:
        """Obtiene embeddings [CLS] de BETO para un lote de textos."""
        all_embeddings = []
        
        # Procesar en mini-lotes para no desbordar RAM/VRAM
        for i in range(0, len(texts), BATCH_SIZE):
            batch_texts = texts[i:i + BATCH_SIZE]
            inputs = self.tokenizer(
                batch_texts,
                max_length=MAX_SEQ_LENGTH,
                padding=True,
                truncation=True,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)

            # [CLS] token embeddings (batch_size, 768)
            cls_embs = outputs.last_hidden_state[:, 0, :].cpu().numpy()
            
            # Normalización L2 por fila
            norms = np.linalg.norm(cls_embs, axis=1, keepdims=True)
            norms[norms == 0] = 1  # Evitar división por cero
            cls_embs = cls_embs / norms
            
            all_embeddings.extend(cls_embs)
            
        return np.array(all_embeddings)

    def _predict_zero_shot_batch(self, texts: list[str]) -> list[dict]:
        """Clasificación zero-shot por lotes."""
        if not texts:
            return []
            
        text_embs = self._get_embeddings_batch(texts)  # (N, 768)
        
        cat_rel = self._category_embeddings["relevante"]  # (768,)
        cat_norel = self._category_embeddings["no_relevante"]
        
        # Similitud coseno (al estar normalizados, es solo producto punto)
        sim_relevante = np.dot(text_embs, cat_rel)  # (N,)
        sim_no_relevante = np.dot(text_embs, cat_norel)  # (N,)
        
        # Normalizar a probabilidad con softmax y temperatura
        exp_rel = np.exp(sim_relevante * 5)
        exp_norel = np.exp(sim_no_relevante * 5)
        scores = exp_rel / (exp_rel + exp_norel)
        
        results = []
        for i in range(len(texts)):
            s = float(scores[i])
            results.append({
                "score_semantico": round(s, 4),
                "es_relevante": s >= 0.5,
                "confianza": self._confidence_level(s),
                "modo": "zero_shot",
                "sim_relevante": round(float(sim_relevante[i]), 4),
                "sim_no_relevante": round(float(sim_no_relevante[i]), 4),
            })
        return results

    @staticmethod
    def _confidence_level(score: float) -> str:
        """Determina el nivel de confianza basado en la distancia al umbral."""
        distance = abs(score - 0.5)
        if distance > 0.3:
            return "alta"
        elif distance > 0.15:
            return "media"
        return "baja"

    # ── Fine-tuning ─────────────────────────────────────────

    def fine_tune(
        self,
        df: pd.DataFrame,
        text_col: str = "texto",
        label_col: str = "etiqueta",
        val_split: float = 0.2,
        epochs: int = NUM_EPOCHS,
        lr: float = LEARNING_RATE,
        early_stopping_patience: int = 2,
    ) -> dict:
        """
        Fine-tuning del clasificador BETO con Early Stopping basado en F1.

        Proceso:
          1. División train/validation estratificada
          2. Creación de DataLoaders
          3. Entrenamiento con AdamW + scheduler lineal con warmup
          4. Evaluación por época; guarda solo el mejor checkpoint (F1 val)
          5. Early stopping: detiene si F1 no mejora en `patience` épocas
          6. Recarga el mejor checkpoint al terminar

        Args:
            df: DataFrame con columnas de texto y etiquetas (0/1).
            text_col: Columna con el texto.
            label_col: Columna con etiquetas binarias.
            val_split: Fracción para validación.
            epochs: Número máximo de épocas.
            lr: Learning rate.
            early_stopping_patience: Épocas sin mejora antes de parar.
                Recomendado: 2 para datasets pequeños, 3 para medianos.

        Returns:
            dict con métricas de entrenamiento e historial por época.
        """
        from sklearn.model_selection import train_test_split
        from torch.optim import AdamW
        from torch.optim.lr_scheduler import LinearLR

        logger.info(f"Iniciando fine-tuning con {len(df)} muestras")

        # Preparar datos
        texts = df[text_col].tolist()
        labels = df[label_col].astype(int).tolist()

        X_train, X_val, y_train, y_val = train_test_split(
            texts, labels, test_size=val_split,
            stratify=labels, random_state=42,
        )

        train_dataset = NNANewsDataset(X_train, y_train, self.tokenizer)
        val_dataset = NNANewsDataset(X_val, y_val, self.tokenizer)

        train_loader = DataLoader(
            train_dataset, batch_size=BATCH_SIZE, shuffle=True
        )
        val_loader = DataLoader(
            val_dataset, batch_size=BATCH_SIZE, shuffle=False
        )

        # Modelo
        model = BETOClassifier(num_classes=2).to(self.device)

        # Optimizador AdamW con weight decay (evita sobre-ajuste)
        optimizer = AdamW(
            model.parameters(), lr=lr, weight_decay=0.01
        )

        total_steps = len(train_loader) * epochs
        scheduler = LinearLR(
            optimizer, start_factor=0.1, end_factor=1.0,
            total_iters=int(total_steps * WARMUP_RATIO),
        )

        # ── Entrenamiento con Early Stopping ─────────────────────
        best_f1 = 0.0
        epochs_no_improve = 0
        best_checkpoint_path = os.path.join(FINETUNED_DIR, "model.pt")
        history = {"train_loss": [], "val_f1": [], "val_precision": [], "val_recall": []}

        os.makedirs(FINETUNED_DIR, exist_ok=True)

        for epoch in range(epochs):
            # ── Train ──
            model.train()
            total_loss = 0.0
            for batch in train_loader:
                optimizer.zero_grad()
                outputs = model(
                    input_ids=batch["input_ids"].to(self.device),
                    attention_mask=batch["attention_mask"].to(self.device),
                    labels=batch["labels"].to(self.device),
                )
                loss = outputs["loss"]
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                total_loss += loss.item()

            avg_loss = total_loss / len(train_loader)
            history["train_loss"].append(avg_loss)

            # ── Validation ──
            model.eval()
            all_preds, all_labels = [], []
            with torch.no_grad():
                for batch in val_loader:
                    outputs = model(
                        input_ids=batch["input_ids"].to(self.device),
                        attention_mask=batch["attention_mask"].to(self.device),
                    )
                    preds = torch.argmax(outputs["logits"], dim=1)
                    all_preds.extend(preds.cpu().numpy())
                    all_labels.extend(batch["labels"].numpy())

            precision = precision_score(all_labels, all_preds, zero_division=0)
            recall = recall_score(all_labels, all_preds, zero_division=0)
            f1 = f1_score(all_labels, all_preds, zero_division=0)

            history["val_precision"].append(precision)
            history["val_recall"].append(recall)
            history["val_f1"].append(f1)

            logger.info(
                "Época %d/%d — Loss: %.4f | P: %.4f | R: %.4f | F1: %.4f",
                epoch + 1, epochs, avg_loss, precision, recall, f1,
            )

            # ── Early Stopping basado en F1 de validación ──
            if f1 > best_f1:
                best_f1 = f1
                epochs_no_improve = 0
                torch.save(model.state_dict(), best_checkpoint_path)
                logger.info(
                    "  → ✅ Mejor modelo guardado (F1=%.4f) en %s",
                    f1, best_checkpoint_path,
                )
            else:
                epochs_no_improve += 1
                logger.info(
                    "  → Sin mejora de F1 (%.4f ≤ %.4f). Paciencia: %d/%d",
                    f1, best_f1, epochs_no_improve, early_stopping_patience,
                )
                if epochs_no_improve >= early_stopping_patience:
                    logger.warning(
                        "[EarlyStopping] Deteniendo entrenamiento en época %d/%d. "
                        "F1 no mejoró en %d épocas consecutivas. Mejor F1: %.4f",
                        epoch + 1, epochs, early_stopping_patience, best_f1,
                    )
                    break

        # Recargar el mejor checkpoint (no la última época)
        self._load_finetuned()
        self.mode = "finetuned"
        logger.info("Modelo recargado desde el mejor checkpoint (F1=%.4f)", best_f1)

        # Reporte final
        report = classification_report(
            all_labels, all_preds,
            target_names=["No relevante", "Relevante"],
            output_dict=True,
        )

        metrics = {
            "best_f1": best_f1,
            "final_precision": precision,
            "final_recall": recall,
            "history": history,
            "classification_report": report,
            "confusion_matrix": confusion_matrix(
                all_labels, all_preds
            ).tolist(),
        }

        # Guardar métricas
        metrics_path = os.path.join(FINETUNED_DIR, "training_metrics.json")
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

        return metrics

    def prepare_training_data(
        self,
        df: pd.DataFrame,
        balance_ratio: float = 1.5,
    ) -> pd.DataFrame:
        """
        Prepara datos de entrenamiento desde el DataFrame histórico (v5.1).

        Reglas de etiquetado (estrictas para minimizar falsos positivos):
          Etiqueta 1 (Relevante):
            - clasificacion_final == 'Alta'  (señal fuerte del heurístico)
            - menores_identificados == 'Si'  (confirmación heurística NNA)
          Etiqueta 0 (No relevante):
            - Cualquier otro caso (Media, Baja, No relevante)
            - Media se descarta intencionalmente para que el modelo aprenda
              solo de los casos más claros y no propague ambigüedad.

        Balanceo de clases (ratio configurable):
          - Siempre se respeta la clase minoritaria completa.
          - La clase mayoritaria se submuestrea a min(n_min * balance_ratio, n_max).
          - Con replace=False para no repetir ejemplos reales.
          - El ratio 1.5 (default) permite clase mayoritaria 50% mayor.

        Args:
            df: DataFrame del histórico con columnas del pipeline.
            balance_ratio: Cuántas veces puede ser la clase mayoritaria
                respecto a la minoritaria. Default 1.5 → máx 3:2.

        Returns:
            DataFrame con columnas ['texto', 'etiqueta'] listo para fine_tune().
        """
        df_train = df.copy()

        # ── Texto combinado: título duplicado para darle más peso ──
        df_train["texto"] = (
            df_train["titulo"].fillna("") + " "
            + df_train["titulo"].fillna("") + " [SEP] "
            + df_train["contenido"].fillna("").str[:1500]
        )

        # ── Columnas de referencia (con fallbacks defensivos) ──
        clf_col = (
            "clasificacion_final" if "clasificacion_final" in df.columns
            else "clasificacion"
        )
        nna_col = "menores_identificados" if "menores_identificados" in df.columns else None

        # ── Función de etiquetado estricto ──
        def _label(row) -> int:
            clf = str(row.get(clf_col, "No relevante"))
            # Caso Alta: señal heurística fuerte
            if clf == "Alta":
                return 1
            # Refuerzo: NNA identificado explícitamente
            if nna_col and str(row.get(nna_col, "No")).strip().lower() == "si":
                return 1
            # Todo lo demás es negativo
            return 0

        df_train["etiqueta"] = df_train.apply(_label, axis=1)

        # ── Balance de clases ──
        pos = df_train[df_train["etiqueta"] == 1]
        neg = df_train[df_train["etiqueta"] == 0]
        n_pos, n_neg = len(pos), len(neg)

        if n_pos == 0 or n_neg == 0:
            logger.warning(
                "[prepare_training_data] Una clase está vacía "
                "(pos=%d, neg=%d). Revisa los datos de entrada.", n_pos, n_neg
            )
            return df_train[["texto", "etiqueta"]].reset_index(drop=True)

        n_minor = min(n_pos, n_neg)
        n_major_target = min(int(n_minor * balance_ratio), max(n_pos, n_neg))

        if n_pos >= n_neg:  # Submuestrear positivos
            pos = pos.sample(n=n_major_target, random_state=42, replace=False)
        else:               # Submuestrear negativos
            neg = neg.sample(n=n_major_target, random_state=42, replace=False)

        df_balanced = (
            pd.concat([pos, neg])
            .sample(frac=1, random_state=42)
            .reset_index(drop=True)
        )

        n_final_pos = int((df_balanced["etiqueta"] == 1).sum())
        n_final_neg = int((df_balanced["etiqueta"] == 0).sum())
        logger.info(
            "[prepare_training_data] %d muestras listas para entrenamiento "
            "(positivas=%d, negativas=%d, ratio=%.2f)",
            len(df_balanced), n_final_pos, n_final_neg,
            n_final_pos / max(n_final_neg, 1),
        )

        return df_balanced[["texto", "etiqueta"]]

    # ── Extracción de embeddings ────────────────────────────

    def get_embeddings(
        self, texts: list[str], batch_size: int = 32
    ) -> np.ndarray:
        """
        Extrae embeddings BETO para una lista de textos.

        Útil para:
          - Clustering semántico (OE-4)
          - Análisis de similitud
          - Visualización con UMAP/t-SNE

        Returns:
            Matriz numpy (n_texts, 768) con embeddings normalizados.
        """
        if self.mode == "finetuned" and isinstance(self.model, BETOClassifier):
            base_model = self.model.bert
        elif hasattr(self.model, "encoder"):
            base_model = self.model
        else:
            base_model = self.model

        base_model.eval()
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            inputs = self.tokenizer(
                batch_texts,
                max_length=MAX_SEQ_LENGTH,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = base_model(**inputs)
                cls_emb = outputs.last_hidden_state[:, 0, :]
                # Normalización L2
                norms = torch.norm(cls_emb, dim=1, keepdim=True)
                cls_emb = cls_emb / norms.clamp(min=1e-8)
                all_embeddings.append(cls_emb.cpu().numpy())

        return np.vstack(all_embeddings)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Scoring híbrido: Semántico + Heurístico
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class HybridScorer:
    """
    Combina el scoring heurístico (keywords) con el semántico (BETO).

    Fórmula de combinación:
      score_final = α × score_semantico + (1 - α) × score_heuristico

    Donde α se ajusta según la confianza del modelo semántico:
      - Confianza alta  → α = 0.7 (confiar más en semántico)
      - Confianza media → α = 0.5 (peso igual)
      - Confianza baja  → α = 0.3 (confiar más en heurístico)

    Esto permite una transición suave del sistema actual al nuevo
    clasificador semántico, manteniendo el rendimiento mientras
    el modelo se entrena con más datos.
    """

    # Pesos por nivel de confianza del modelo semántico
    ALPHA_HIGH = 0.70
    ALPHA_MEDIUM = 0.50
    ALPHA_LOW = 0.30

    def __init__(self, detector: Optional[SemanticDetector] = None):
        self.detector = detector
        self._enabled = detector is not None

    def score(
        self, title: str, content: str, heuristic_score: float
    ) -> dict:
        """
        Calcula score híbrido combinando ambos métodos.

        Args:
            title: Título de la noticia.
            content: Contenido de la noticia.
            heuristic_score: Score del sistema heurístico existente.

        Returns:
            dict con score_final, score_semantico, score_heuristico,
            clasificacion_hibrida, alpha usado.
        """
        if not self._enabled:
            return {
                "score_final": heuristic_score,
                "score_semantico": None,
                "score_heuristico": heuristic_score,
                "clasificacion_hibrida": self._classify(heuristic_score),
                "alpha": 0.0,
                "modo": "solo_heuristico",
            }

        try:
            sem_result = self.detector.predict(title, content)
            score_sem = sem_result["score_semantico"]
            confianza = sem_result["confianza"]

            # Seleccionar alpha según confianza
            if confianza == "alta":
                alpha = self.ALPHA_HIGH
            elif confianza == "media":
                alpha = self.ALPHA_MEDIUM
            else:
                alpha = self.ALPHA_LOW

            score_final = alpha * score_sem + (1 - alpha) * heuristic_score

            return {
                "score_final": round(score_final, 4),
                "score_semantico": score_sem,
                "score_heuristico": round(heuristic_score, 4),
                "clasificacion_hibrida": self._classify(score_final),
                "alpha": alpha,
                "modo": "hibrido",
                "confianza_semantica": confianza,
            }
        except Exception as e:
            logger.warning(f"Error en scoring semántico: {e}")
            return {
                "score_final": heuristic_score,
                "score_semantico": None,
                "score_heuristico": heuristic_score,
                "clasificacion_hibrida": self._classify(heuristic_score),
                "alpha": 0.0,
                "modo": "fallback_heuristico",
            }

    @staticmethod
    def _classify(score: float) -> str:
        """Clasifica por umbrales."""
        if score >= 0.45:
            return "Alta"
        elif score >= 0.30:
            return "Media"
        elif score >= 0.15:
            return "Baja"
        return "No relevante"
