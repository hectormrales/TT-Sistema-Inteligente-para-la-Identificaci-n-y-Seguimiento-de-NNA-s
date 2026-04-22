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

Modos de operación:
  1. Zero-shot: Usa BETO pre-entrenado con clasificación por similitud
     coseno contra descripciones de categorías (sin fine-tuning).
  2. Fine-tuned: Entrena el clasificador binario con datos etiquetados
     recogidos por el sistema heurístico existente.
  3. Híbrido: Combina score semántico con score heurístico para
     maximizar precisión y recall.

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

# ── Configuración del modelo ────────────────────────────────

BETO_MODEL_NAME = "dccuchile/bert-base-spanish-wwm-cased"
MAX_SEQ_LENGTH = 512
BATCH_SIZE = 16
LEARNING_RATE = 2e-5
NUM_EPOCHS = 4
WARMUP_RATIO = 0.1
CACHE_DIR = os.environ.get("MODEL_CACHE_DIR", "models/cache")
FINETUNED_DIR = os.environ.get("FINETUNED_MODEL_DIR", "models/finetuned")

# Descripciones de categorías para zero-shot classification
# v2.0: Descripciones mucho más específicas para el caso de uso exacto.
CATEGORY_DESCRIPTIONS = {
    "relevante": (
        "Caso individual de feminicidio en México donde una mujer fue asesinada "
        "y sus hijos menores de edad quedaron huérfanos, desamparados o en orfandad. "
        "Noticia que describe un evento específico: la víctima fue encontrada sin vida, "
        "el agresor fue detenido, los niños quedaron solos, "
        "menores de edad que perdieron a su madre por violencia feminicida, "
        "DIF resguarda a los hijos de la víctima de feminicidio."
    ),
    "no_relevante": (
        "Noticia general sin relación con feminicidio ni menores huérfanos. "
        "Estadísticas y cifras de feminicidio sin caso concreto. "
        "Política pública, leyes, reformas, programas de apoyo, becas. "
        "Columna de opinión, editorial, marcha, conmemoración. "
        "Deportes, entretenimiento, economía, clima, tecnología, "
        "política internacional, cultura, espectáculos."
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

        if mode == "auto":
            self.mode = self._detect_mode()

        self._initialize()

    def _detect_mode(self) -> str:
        """Detecta el mejor modo disponible."""
        finetuned_path = os.path.join(FINETUNED_DIR, "model.pt")
        if os.path.exists(finetuned_path):
            return "finetuned"
        return "zero_shot"

    def _initialize(self):
        """Inicializa tokenizer y modelo según el modo."""
        logger.info(f"Inicializando SemanticDetector en modo: {self.mode}")

        os.makedirs(CACHE_DIR, exist_ok=True)

        # Tokenizer siempre necesario
        self.tokenizer = AutoTokenizer.from_pretrained(
            BETO_MODEL_NAME, cache_dir=CACHE_DIR
        )

        if self.mode == "finetuned":
            self._load_finetuned()
        elif self.mode == "zero_shot":
            self._init_zero_shot()
        elif self.mode == "hybrid":
            # Intentar cargar fine-tuned, fallback a zero-shot
            try:
                self._load_finetuned()
            except Exception:
                logger.warning("Modelo fine-tuned no disponible, usando zero-shot")
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
            torch.load(finetuned_path, map_location=self.device)
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

    # ── Clasificación ───────────────────────────────────────

    def predict(self, title: str, content: str) -> dict:
        """
        Clasifica una noticia como relevante o no relevante.

        Args:
            title: Título de la noticia.
            content: Contenido/cuerpo de la noticia.

        Returns:
            dict con:
              - score_semantico (float): Probabilidad de relevancia [0, 1]
              - es_relevante (bool): True si score >= 0.5
              - confianza (str): 'alta', 'media', 'baja'
              - modo (str): modo de clasificación usado
        """
        text = f"{title} [SEP] {content[:1500]}"

        if self.mode == "finetuned":
            return self._predict_finetuned(text)
        else:
            return self._predict_zero_shot(text)

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

        Procesa múltiples noticias en lotes de BATCH_SIZE,
        aprovechando paralelismo de GPU si está disponible.
        """
        results = []
        texts = [
            f"{t} [SEP] {c[:1500]}" for t, c in zip(titles, contents)
        ]

        if self.mode == "finetuned":
            # Batch inference con DataLoader
            dataset = NNANewsDataset(
                texts, [0] * len(texts), self.tokenizer
            )
            loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=False)

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
                        results.append({
                            "score_semantico": round(s, 4),
                            "es_relevante": s >= 0.5,
                            "confianza": self._confidence_level(s),
                            "modo": "finetuned",
                        })
        else:
            # Zero-shot: uno por uno (embeddings con cache)
            for text in texts:
                results.append(self._predict_zero_shot(text))

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
    ) -> dict:
        """
        Fine-tuning del clasificador BETO con datos etiquetados.

        Proceso:
          1. División train/validation estratificada
          2. Creación de DataLoaders
          3. Entrenamiento con AdamW + scheduler lineal
          4. Evaluación por época con early stopping
          5. Guardado del mejor modelo

        Args:
            df: DataFrame con columnas de texto y etiquetas (0/1).
            text_col: Columna con el texto.
            label_col: Columna con etiquetas binarias.
            val_split: Fracción para validación.
            epochs: Número de épocas.
            lr: Learning rate.

        Returns:
            dict con métricas de entrenamiento.
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

        # Entrenamiento
        best_f1 = 0.0
        history = {"train_loss": [], "val_f1": [], "val_precision": [], "val_recall": []}

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
                f"Época {epoch+1}/{epochs} — "
                f"Loss: {avg_loss:.4f} | "
                f"P: {precision:.4f} | R: {recall:.4f} | F1: {f1:.4f}"
            )

            # Guardar mejor modelo
            if f1 > best_f1:
                best_f1 = f1
                os.makedirs(FINETUNED_DIR, exist_ok=True)
                torch.save(
                    model.state_dict(),
                    os.path.join(FINETUNED_DIR, "model.pt"),
                )
                logger.info(f"  → Mejor modelo guardado (F1={f1:.4f})")

        # Recargar mejor modelo
        self.model = model
        self._load_finetuned()
        self.mode = "finetuned"

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

    def prepare_training_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepara datos de entrenamiento desde el output del sistema heurístico.

        Usa las clasificaciones heurísticas existentes como etiquetas
        pseudo-supervisadas:
          - 'Alta' o 'Media' → etiqueta 1 (relevante)
          - 'No relevante' o 'Baja' con score < 0.15 → etiqueta 0

        Esto permite bootstrap del clasificador semántico usando
        los datos ya recolectados por el sistema actual.
        """
        df_train = df.copy()

        # Crear texto combinado
        df_train["texto"] = (
            df_train["titulo"].fillna("") + " [SEP] " +
            df_train["contenido"].fillna("").str[:1500]
        )

        # Generar etiquetas desde clasificación heurística
        clf_col = "clasificacion_final" if "clasificacion_final" in df.columns else "clasificacion"
        score_col = "relevancia_final" if "relevancia_final" in df.columns else "score_compuesto"

        def _label(row):
            clf = row.get(clf_col, "No relevante")
            score = row.get(score_col, 0)
            if clf in ("Alta", "Media"):
                return 1
            if clf == "Baja" and score >= 0.20:
                return 1
            return 0

        df_train["etiqueta"] = df_train.apply(_label, axis=1)

        # Balance de clases: submuestreo de la clase mayoritaria
        pos = df_train[df_train["etiqueta"] == 1]
        neg = df_train[df_train["etiqueta"] == 0]

        if len(pos) > 0 and len(neg) > 0:
            min_count = min(len(pos), len(neg))
            max_count = min(min_count * 2, max(len(pos), len(neg)))
            if len(pos) > len(neg):
                pos = pos.sample(n=max_count, random_state=42, replace=True)
            else:
                neg = neg.sample(n=max_count, random_state=42, replace=True)
            df_train = pd.concat([pos, neg]).sample(frac=1, random_state=42)

        logger.info(
            f"Datos de entrenamiento: {len(df_train)} muestras "
            f"({(df_train['etiqueta'] == 1).sum()} positivas, "
            f"{(df_train['etiqueta'] == 0).sum()} negativas)"
        )

        return df_train[["texto", "etiqueta"]].reset_index(drop=True)

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
