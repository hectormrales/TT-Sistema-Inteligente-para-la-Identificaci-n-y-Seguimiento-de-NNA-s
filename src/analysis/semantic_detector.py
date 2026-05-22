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
import re
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
        El argumento `mode` es ignorado. El modo SIEMPRE se lee de la
        variable de entorno DETECTOR_MODE (default: "fine-tuned").
        Esto garantiza que la configuración de Docker/docker-compose
        sea la única fuente de verdad, sin importar cómo se instancia
        la clase desde el código.

        DETECTOR_MODE válidos: 'fine-tuned' | 'finetuned' | 'zero_shot' | 'hybrid'
        """
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        logger.info(f"SemanticDetector usando dispositivo: {self.device}")

        self.tokenizer = None
        self.model = None
        self.zero_shot_pipeline = None
        self._embeddings_cache: dict[str, np.ndarray] = {}

        # Pre-filtro sintáctico (spaCy) — carga lazy
        self._spacy_nlp = None
        self._prefiltro_habilitado = _POC_DISPONIBLE

        # ── Resolución del modo: SIEMPRE desde el entorno ─────────────────
        # El parámetro `mode` se ignora deliberadamente para que DETECTOR_MODE
        # sea la única fuente de verdad (comportamiento requerido en Docker).
        env_mode = os.environ.get("DETECTOR_MODE", "fine-tuned").strip().lower()

        if env_mode in ("fine-tuned", "finetuned"):
            self.mode = "finetuned"
        elif env_mode == "zero_shot":
            self.mode = "zero_shot"
        elif env_mode == "hybrid":
            self.mode = "hybrid"
        else:
            logger.warning(
                "[SemanticDetector] Valor desconocido en DETECTOR_MODE='%s'. "
                "Usando 'finetuned' por defecto.", env_mode
            )
            self.mode = "finetuned"

        logger.info(
            "[SemanticDetector] Modo resuelto desde DETECTOR_MODE='%s' → '%s'",
            env_mode, self.mode,
        )

        # Si el modo resuelto es finetuned, verificar existencia del archivo
        # ANTES de comprometerse con él; si no existe, caer en zero_shot.
        if self.mode == "finetuned":
            self.mode = self._detect_mode()

        self._initialize()

    def _detect_mode(self) -> str:
        """
        Detecta el mejor modo disponible (v5.2).

        Prioridad estricta:
          1. finetuned — si model.pt existe en FINETUNED_DIR (ruta absoluta)
          2. zero_shot — ÚLTIMO RECURSO con advertencia explícita

        Nota: FINETUNED_DIR se resuelve como ruta absoluta para garantizar
        que funcione independientemente del CWD del proceso (crítico en Docker).
        """
        # Resolver siempre como ruta absoluta para evitar dependencia del CWD
        finetuned_dir_abs = os.path.abspath(FINETUNED_DIR)
        finetuned_path = os.path.join(finetuned_dir_abs, "model.pt")

        if os.path.exists(finetuned_path):
            logger.info(
                "[SemanticDetector] Modelo fine-tuned encontrado en: %s",
                finetuned_path,
            )
            return "finetuned"

        logger.warning(
            "[SemanticDetector] ⚠️  MODELO FINE-TUNED NO ENCONTRADO en '%s'. "
            "Cayendo en zero_shot como último recurso. "
            "Este modo genera falsos positivos en contextos relacionales. "
            "Ejecute fine_tune() con datos etiquetados antes de usar en producción.",
            finetuned_path,
        )
        return "zero_shot"

    def _initialize(self):
        """
        Inicializa tokenizer y modelo según el modo (v5.2).

        Para 'finetuned': intenta cargar model.pt desde FINETUNED_DIR.
                          Si falla, emite warning y cae en zero_shot.
        Para 'zero_shot': advierte del riesgo y carga BETO base.
        Para 'hybrid':    intenta finetuned; si falla, cae en zero_shot con warnings.
        """
        logger.info(f"Inicializando SemanticDetector en modo: {self.mode}")

        os.makedirs(CACHE_DIR, exist_ok=True)

        # Tokenizer siempre necesario
        self.tokenizer = AutoTokenizer.from_pretrained(
            BETO_MODEL_NAME, cache_dir=CACHE_DIR
        )

        if self.mode == "finetuned":
            try:
                self._load_finetuned()
            except FileNotFoundError as exc:
                logger.warning(
                    "[SemanticDetector] ⚠️  No se pudo cargar el modelo fine-tuned: %s. "
                    "Degradando automáticamente a zero_shot. "
                    "Verifique que FINETUNED_MODEL_DIR apunte a la ruta correcta "
                    "y que model.pt tenga permisos de lectura.",
                    exc,
                )
                self.mode = "zero_shot"
                self._init_zero_shot()

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

    def _load_finetuned(self):
        """Carga modelo fine-tuned desde disco con ruta absoluta resuelta."""
        # Resolución absoluta: garantiza funcionamiento correcto en Docker
        # independientemente del CWD del proceso (CRÍTICO).
        finetuned_dir_abs = os.path.abspath(FINETUNED_DIR)
        finetuned_path = os.path.join(finetuned_dir_abs, "model.pt")

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
        logger.info("[INFO] Modelo fine-tuned cargado exitosamente.")  # ← log exacto requerido


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

    # ── Escudo Léxico (Blacklist) ─────────────────────────────
    #
    # Palabras que señalan dominios COMPLETAMENTE AJENOS al caso de uso
    # (feminicidio → orfandad NNA). Su presencia indica FP estructural.
    #
    # Criterio: término que NUNCA aparece en noticias genuinas del corpus
    # objetivo pero SÍ en noticias que BETO califica como "Alta" por tono
    # periodístico/institucional compartido.
    # ─────────────────────────────────────────────────────────────────────
    _ESCUDO_LEXICO: frozenset = frozenset({
        # Macroeconomía / Finanzas públicas
        "hacienda", "moody's", "moodys", "fitch", "s&p", "inflación",
        "inflacion", "deflación", "deflacion", "peso", "dólar", "dolar",
        "tipo de cambio", "divisa", "divisas", "pib", "producto interno bruto",
        "deuda pública", "deuda publica", "déficit", "deficit", "superávit",
        "superavit", "presupuesto", "erario", "recaudación", "recaudacion",
        "impuesto", "impuestos", "iva", "isr", "sat", "contribuyentes",
        "contribuyente", "austeridad", "reservas internacionales",
        "banco de méxico", "banco de mexico", "banxico", "tasa de interés",
        "tasa de interes", "remesas", "balanza comercial", "exportaciones",
        "importaciones", "aranceles", "arancel", "nearshoring",
        # Energía / Combustibles / Infraestructura
        "pemex", "cfe", "pipas", "gasolina", "gasolinazo", "litro de gasolina",
        "combustible", "energía eléctrica", "energia electrica", "electricidad",
        "apagón", "apagon", "planta eléctrica", "planta electrica", "refinería",
        "refineria", "ducto", "oleoducto", "gasoducto", "megaobra", "tren maya",
        "aeropuerto", "naicm", "aifa", "autopista", "carretera", "puente",
        "viaducto", "metro cdmx", "metrobús", "metrobus", "trolebús", "trolebus",
        # Clima / Medioambiente / Desastres naturales
        "sequía", "sequia", "lluvia", "lluvias", "inundación", "inundacion",
        "ciclón", "ciclon", "huracán", "huracan", "terremoto", "sismo",
        "temblor", "erupción", "erupcion", "volcán", "volcan", "granizo",
        "tormenta", "helada", "frente frío", "frente frio", "ola de calor",
        "cambio climático", "cambio climatico", "emisiones de co2", "co2",
        "deforestación", "deforestacion", "biodiversidad", "ecosistema",
        "contaminación del agua", "contaminacion del agua",
        "contaminación del aire", "contaminacion del aire",
        # Espectáculos / Entretenimiento / Cultura
        "concierto", "netflix", "amazon prime", "disney plus", "hbo max",
        "spotify", "tiktok", "youtuber", "influencer", "reality show",
        "premiación", "premiacion", "oscar", "grammy", "emmy", "cannes",
        "festival de cine", "blockbuster", "taquilla", "estreno",
        "videojuego", "esports", "twitch", "videoclip", "álbum", "album",
        "gira musical", "tour", "opening act", "sold out",
        # Política / Gobierno (temas no relacionados con NNA)
        "elecciones", "elección", "eleccion", "candidato", "candidatura",
        "partido político", "partido politico", "morena", "pan ", "pri ",
        "prd ", "movimiento ciudadano", "ine ", "tribunal electoral",
        "diputados", "senadores", "congreso de la unión", "congreso de la union",
        "cámara de diputados", "camara de diputados", "reforma constitucional",
        "plan de nación", "plan de nacion", "conferencia mañanera",
        "conferencia maňanera", "mañanera", "manañera",
        # Deportes
        "futbol", "fútbol", "liga mx", "premier league", "champions league",
        "mundial", "copa del mundo", "selección nacional", "seleccion nacional",
        "olimpiadas", "paralímpicos", "paralimpicos", "maratón", "maraton",
        "nfl", "nba", "mlb", "box", "boxeo", "lucha libre", "ciclismo",
        "fórmula 1", "formula 1", "gp de mexico", "gp de méxico",
        # Salud pública (epidemias/pandemia — no violencia de género)
        "covid", "pandemia", "vacuna", "vacunación", "vacunacion",
        "imss", "issste", "salud pública", "salud publica", "epidemia",
        "brote", "variante", "ómicron", "omicron", "dengue", "cólera", "colera",
        # Ciencia / Tecnología (no relacionados con NNA)
        "inteligencia artificial", "chatgpt", "openai", "google bard",
        "criptomoneda", "bitcoin", "ethereum", "blockchain", "nft",
        "startup", "unicornio tecnológico", "unicornio tecnologico",
        # Fenómenos sociales irrelevantes / Nota roja urbana
        "osamentas", "fosa clandestina",
        "jornada electoral", "bono", "bonos del tesoro",
        # ── NUEVO v5.4: Anti-Leyes / Marco Teórico / Estadística ──────────
        # Descarta notas legislativas, estadísticas y artículos de opinión
        # que comparten vocabulario ("feminicidio", "menores") pero NO
        # reportan un evento fáctico individual (quién, cuándo, dónde).
        "iniciativa de ley", "iniciativa de reforma", "propuesta de ley",
        "propone ", "proponen ", "propuso ", "propuesta legislativa",
        "ley monzón", "ley general", "ley de acceso",
        "reforma al código", "reforma penal", "código nacional",
        "aprobó la ley", "aprueban la ley", "aprobaron la ley",
        "senado aprobó", "cámara aprobó", "congreso aprobó",
        "dictamen", "decreto presidencial", "punto de acuerdo",
        "redim", "unicef", "onu mujeres", "inmujeres",
        "estadística", "estadisticas", "estadísticas",
        "tasa de feminicidio", "tasa de homicidio", "incidencia delictiva",
        "informe anual", "reporte anual", "reporte trimestral",
        "cifras de", "datos de violencia", "datos del snsp",
        "secretariado ejecutivo", "snsp",
        "alerta de género", "alerta de violencia de género",
        "protocolo de actuación", "mecanismo de protección",
        "columna de opinión", "artículo de opinión", "articulo de opinion",
        "editorial ", "columnista", "opinión de", "opinion de",
        "expertos señalan", "especialistas advierten", "académicos",
        "estudio revela", "investigación revela", "encuesta ",
        # ── NUEVO v5.4: Localidad / Extranjero ────────────────────────────
        # Descarta noticias sobre feminicidios ocurridos fuera de México.
        # Scope EXCLUSIVAMENTE nacional (territorio mexicano).
        # Formas con y sin tilde para máxima cobertura.
        "en colombia", "colombia ", "bogotá", "bogota", "medellín", "medellin",
        "en argentina", "argentina ", "buenos aires", "córdoba argentina",
        "en españa", "españa ", "madrid ", "barcelona ", "sevilla ",
        "en chile", "chile ", "santiago de chile",
        "en perú", "peru ", "lima perú", "lima peru",
        "en venezuela", "venezuela ", "caracas ",
        "en bolivia", "bolivia ", "la paz bolivia",
        "en ecuador", "ecuador ", "quito ",
        "en guatemala", "guatemala ", "ciudad de guatemala",
        "en honduras", "honduras ", "tegucigalpa",
        "en el salvador", "el salvador ", "san salvador",
        "en nicaragua", "nicaragua ", "managua ",
        "en costa rica", "costa rica ", "san josé costa",
        "en panamá", "panama ", "ciudad de panamá",
        "en cuba", "cuba ", "la habana",
        "en república dominicana", "república dominicana", "republica dominicana",
        "en paraguay", "paraguay ", "asunción",
        "en uruguay", "uruguay ", "montevideo",
        "en puerto rico", "puerto rico ",
    })

    # ── Post-Filtro de Validación Semántica v6.0 ────────────────
    #
    # Se ejecuta DESPUÉS de BETO cuando el score >= 0.85 ("Alta").
    # Valida que el contenido realmente describe un evento fáctico
    # donde NNA quedan huérfanos/sobrevivientes por feminicidio.
    #
    # Problema raíz: BETO asigna score > 0.90 a CUALQUIER texto con
    # vocabulario {feminicidio, hijo, menor, mujer, asesinada} sin
    # distinguir el ROL del menor (huérfano vs víctima vs agresor).
    # ─────────────────────────────────────────────────────────────

    # Patrones que CONFIRMAN que es un verdadero positivo (VP)
    _PATRONES_VP: tuple = (
        # NNA queda huérfano/desamparado
        r"(?:quedaron?|quedan)\s+(?:en\s+)?(?:orfandad|huérfan|desamp)",
        r"deja(?:ndo|ron|\s)\s*(?:a\s+)?(?:sus\s+)?(?:\d+\s+)?hijos?",
        r"era\s+madre\s+de\s+\d+",
        r"madre\s+de\s+(?:dos|tres|cuatro|cinco|seis|siete|familia)",
        # NNA presencia el crimen
        r"(?:frente|delante)\s+(?:a|de)\s+(?:sus?\s+)?hijos?",
        r"hijos?\s+(?:estaban?|quedaron?)\s+presentes?",
        r"(?:menor|niño|niña|hijo|hija)\s+(?:presenció|presenciaron|vio|atestiguó)",
        r"(?:menor|niño|niña)\s+(?:que\s+)?presenció",
        # NNA bajo resguardo institucional
        r"(?:menores?|hijos?|niños?)\s+(?:bajo|en)\s+(?:resguardo|custodia|protección)",
        r"(?:DIF|SNDIF|procuraduría)\s+(?:resguard|custodi|proteg)",
        r"resguardo\s+del\s+DIF",
        # Sustracción/desaparición de menor tras feminicidio (AMPLIADO v6.1)
        r"(?:sustra|rapt|secuestr|desaparec)\w+\s+(?:a\s+)?(?:su\s+)?(?:menor|hija|hijo|niña|niño)",
        r"(?:menor|hija|hijo|niña)\s+(?:reportada?|desaparecida?)\s+(?:como|tras|luego|después)",
        r"doble\s+feminicidio.*(?:menor|hija|hijo)",
        r"menor\s+s[ií]\s+fue\s+sustra[ií]d[ao]",
        r"(?:menor|niñ[ao]|hija|hijo)\s+(?:fue\s+)?sustra[ií]d[ao]",
        r"(?:halla|hallan|encuentran|localizan)\s+(?:a\s+)?(?:menor|niñ[ao])\s+(?:con\s+vida|sano|sana|ileso)",
        # Orfandad fáctica explícita
        r"(?:dos|tres|cuatro|\d+)\s+menores\s+(?:quedan|quedaron)\s+(?:en\s+)?orfandad",
        r"hijos?\s+(?:quedaron?|quedan)\s+solos?",
        r"(?:tragedia|feminicidio).*(?:deja|dejó).*(?:menor|huérfan|orfandad)",
        # Hijo cuenta / testimonio de menor
        r"(?:hijo|hija|menor|niño|niña)\s+(?:que\s+)?(?:relat|narr|cont|dijo|revel)",
        r"testimonio\s+(?:del?\s+)?(?:menor|niño|niña|hijo)",
        # Menor solo / abandonado tras el crimen
        r"(?:menor|niñ[ao]|bebé)\s+(?:fue\s+)?(?:encontrad[oa]\s+solo|hall[ao]\s+solo|abandon[ao]\s+(?:en|junto))",
        r"se\s+quedó\s+(?:solo|sola|sin\s+madre|sin\s+padres?|huérfan)",
    )

    # Patrones que señalan FP (NO es un caso de orfandad por feminicidio)
    _PATRONES_FP: tuple = (
        # ── ROLES INVERTIDOS: hijo/hija mata a madre/padre ──
        r"hijo\w*\s+(?:la\s+)?(?:mat[óoaé]|asesin[óoaé]|habría\s+(?:matado|asesinado))",
        r"hijo\w*\s+(?:presuntamente\s+)?(?:mata|asesina|habría)",
        r"(?:su\s+)?hijo\w*\s+(?:la|lo|le)\s+(?:mat|asesin|apuñal|dispar)",
        r"(?:hija|yerno)\s+(?:fueron?|fue)\s+detenid[oa]s?",
        r"(?:hija|hijo).*(?:detenid[oa]|arrest[oa]d[oa])\s+(?:por|como)",
        # ── MENOR como víctima DIRECTA del asesinato ──
        r"(?:feminicidio|asesinato)\s+(?:de\s+)?(?:una\s+)?(?:menor|jovencita|niña|adolescente)\b",
        r"(?:menor|niña|adolescente)\s+(?:de\s+\d+\s+años\s+)?(?:asesinada|encontrada\s+sin\s+vida)",
        r"(?:mujer\s+)?(?:asesina|mata)\s+a\s+su\s+(?:hijo|hija)\b",
        r"(?:homicidio|muerte)\s+de\s+su\s+hijo",
        r"(?:olvidarlo|dejarlo|dejándolo)\s+(?:\d+\s+)?horas?\s+(?:en\s+)?(?:el\s+)?auto",
        r"menor\s+cayó\s+de\s+un",
        # ── MENOR como AGRESOR (perpetrador) ──
        r"(?:detienen|arrestan|capturan)\s+a\s+(?:un\s+)?menor\s+(?:por|como|de)",
        r"(?:adolescente|menor)\s+(?:es\s+)?(?:imputad[oa]|acusad[oa]|detenid[oa]|vinculad[oa])",
        r"formulan\s+imputación\s+a\s+(?:un\s+)?adolescente",
        r"menor\s+de\s+\d+\s+años\s+(?:por\s+)?(?:asesinato|feminicidio|homicidio)",
        # ── NOTICIA POLICIAL/JUDICIAL sin nexo NNA-huérfano (NUEVO v6.1) ──
        # Captura/detención del feminicida sin mención de hijos que quedaron solos.
        r"capturan\s+(?:al\s+)?(?:presunto\s+)?feminicida\s+de",
        r"detienen\s+(?:al\s+)?(?:presunto\s+)?feminicida\s+de",
        r"arrestan\s+(?:al\s+)?(?:presunto\s+)?feminicida\s+de",
        r"(?:capturan|detienen|arrestan|aprehenden)\s+(?:a\s+)?(?:al\s+)?(?:presunto\s+)?(?:homicida|asesino|feminicida)",
        r"fue\s+(?:detenid[oa]|capturad[oa]|arrestad[oa])\s+el\s+(?:presunto\s+)?feminicida",
        r"(?:vinculan|presentan|imputan)\s+a\s+proceso\s+(?:al\s+)?(?:presunto\s+)?(?:feminicida|asesino|homicida)",
        r"(?:girar[ao]n|librar[ao]n)\s+(?:orden\s+de\s+)?aprehens[oi][oó]n",
        r"senten(?:ci[ao]|cia)\s+(?:a\s+)?\d+\s+años\s+(?:de\s+)?(?:prisión|cárcel)",
        r"proceso\s+(?:legal|penal|judicial)\s+(?:contra|por|al)",
        r"vinculado\s+a\s+proceso",
        r"carpeta\s+de\s+investigación",
        # ── TEMÁTICO: orfandad como tema genérico, NO caso fáctico ──
        r"(?:visibilizar|dimensionar|atender|documentar)\s+(?:la\s+)?orfandad",
        r"orfandad\s+por\s+feminicidio\s*:\s*\d+\s+años",
        r"(?:deuda|crisis|problema|reto)\s+(?:que|de).*orfandad",
        r"podcast|editorial|opinión|columna",
        # ── ESTADÍSTICAS / RANKINGS ──
        r"(?:primer|segund|tercer|cuart|quint|sext|séptim|octav|noven|décim)\w*\s+lugar",
        r"\d+\s+de\s+cada\s+\d+\s+(?:menor|niñ|mujer)",
        r"\d+\s+(?:niñas|menores|mujeres)\s+(?:asesinadas|desaparecidas)\s+en\s+(?:una\s+)?década",
        r"se\s+(?:disparó|incrementó|registró)\s+\d+%",
        r"(?:cifras?|datos?)\s+(?:del?\s+)?(?:SNSP|INEGI|SESNSP)",
        # ── LEGISLATIVO / INSTITUCIONAL (que evadió el escudo léxico) ──
        r"(?:sentencia|fallo|resolución)\s+(?:de\s+)?(?:la\s+)?(?:CoIDH|Corte\s+IDH|CIDH)",
        r"(?:congreso|senado|cámara)\s+(?:obligará|aprobó|aprueba)",
        r"(?:obligará?|obliga)\s+al\s+Estado\s+a\s+(?:proteger|atender)",
        r"(?:incrementa|aumenta|destina)\s+recursos\s+(?:para|a)",
        r"beca\s+(?:rita|benito|bienestar)",
        # ── ABUSO SEXUAL / EXPLOTACIÓN (no feminicidio) ──
        r"abuso\s+sexual\s+(?:contra|de|a)\s+(?:un[oa]?\s+)?menor",
        r"(?:corrupción|explotación|trata)\s+de\s+menores",
        r"(?:extorsión|secuestro)\s+a\s+mujeres",
        # ── VIOLENCIA GENÉRICA sin nexo NNA-huérfano ──
        r"(?:matan|asesinan|ejecutan)\s+a\s+(?:un\s+)?(?:hombre|mesero|pareja)",
        r"(?:matan|asesinan)\s+a\s+(?:madre\s+e\s+hijo|pareja)\s+(?:cuando|mientras)\s+(?:intentaban|iban)",
        r"ataque\s+armado\s+en\s+(?:parque|calle|bar|restaurante)",
    )

    @classmethod
    def _post_filtro_validacion(cls, texto: str) -> dict:
        """
        Post-filtro de Validación Semántica v6.0.

        Se ejecuta DESPUÉS de BETO cuando el score >= 0.85 para
        verificar que el texto realmente describe un caso fáctico de
        NNA que queda huérfano/sobreviviente por feminicidio.

        Estrategia:
          1. Buscar patrones FP → si match, degradar a "No relevante".
          2. Buscar patrones VP → si match, confirmar como "Alta".
          3. Sin match claro → degradar a "Media" (requiere revisión).

        Args:
            texto: Texto completo (título + contenido).

        Returns:
            dict con:
              - validado (bool): True si el texto pasa la validación.
              - accion (str): "confirmar", "degradar" o "revisar".
              - razon (str): Explicación legible.
              - patron (str): Patrón que activó la decisión.
        """
        texto_lower = texto.lower()

        # ── Paso 1: Buscar patrones FP (señales de falso positivo) ──
        for patron in cls._PATRONES_FP:
            match = re.search(patron, texto_lower)
            if match:
                return {
                    "validado": False,
                    "accion": "degradar",
                    "razon": f"PostFiltro FP: '{match.group()}'",
                    "patron": patron,
                }

        # ── Paso 2: Buscar patrones VP (señales de verdadero positivo) ──
        for patron in cls._PATRONES_VP:
            match = re.search(patron, texto_lower)
            if match:
                return {
                    "validado": True,
                    "accion": "confirmar",
                    "razon": f"PostFiltro VP confirmado: '{match.group()}'",
                    "patron": patron,
                }

        # ── Paso 3: Sin evidencia clara → degradar a Media para revisión ──
        return {
            "validado": False,
            "accion": "revisar",
            "razon": "PostFiltro: sin patrón VP/FP claro, requiere revisión humana",
            "patron": "",
        }

    def _escudo_lexico(self, texto: str) -> tuple[bool, str]:
        """
        Comprueba si el texto contiene alguna stop-keyword del Escudo Léxico.

        Búsqueda case-insensitive sobre el texto completo.
        frozenset garantiza búsqueda O(1) por keyword.

        Returns:
            (bloqueado: bool, keyword_encontrada: str)
              - bloqueado=True  → keyword_encontrada es la primera coincidencia.
              - bloqueado=False → keyword_encontrada es "".
        """
        texto_lower = texto.lower()
        for kw in self._ESCUDO_LEXICO:
            if kw in texto_lower:
                return True, kw
        return False, ""

    def pre_filtro_sintactico(self, texto: str) -> dict:
        """
        Ejecuta el Escudo Léxico y la PoC de roles víctima/agresor ANTES de BETO.

        Etapas (en orden de prioridad / menor costo computacional primero):

          0. ESCUDO LÉXICO (nueva capa v5.3 — O(n_keywords) sobre texto plano):
             Bloqueo inmediato si el texto contiene una stop-keyword de dominio
             ajeno (macroeconomía, espectáculos, clima, política, etc.).
             → Retorna bloquear=True, score_semantico=0.0 SIN invocar spaCy/BETO.

          1. BLOQUEO sintáctico (PoC spaCy — ~50-150 ms):
             Si la PoC detecta que el menor es víctima directa de violencia
             (FP sintáctico confirmado), retorna score=0.0 sin invocar BETO.

          2. ACELERACIÓN positiva: si la PoC confirma el patrón
             (mujer víctima + menor superviviente), añade la señal al
             dict de retorno para que predict() pueda usarla como boost
             en versiones futuras.

        Args:
            texto: Texto completo de la noticia (título + contenido).

        Returns:
            dict con claves:
              - habilitado (bool): Si el pre-filtro pudo ejecutarse.
              - bloquear (bool): True ⇒ FP confirmado, NO pasar a BETO.
              - score_semantico (float): 0.0 si bloqueado por Escudo Léxico.
              - caso_valido (bool): True ⇒ PoC detectó patrón positivo.
              - roles (dict): Detalle de roles extraídos por la PoC.
              - razon (str): Descripción legible del resultado.
        """
        # ── ETAPA 0: Escudo Léxico (Blacklist) ──────────────────────────────
        # Costo: O(n_keywords × len(texto)) — operación de cadena pura, sin ML.
        # Se ejecuta PRIMERO para ahorrar spaCy + BETO (~200-800 ms por noticia).
        bloqueado_lexico, kw_encontrada = self._escudo_lexico(texto)
        if bloqueado_lexico:
            razon = f"FP bloqueado por Escudo Léxico: {kw_encontrada}"
            logger.info("[PreFiltro/EscudoLexico] BLOQUEO → '%s'", kw_encontrada)
            return {
                "habilitado": True,
                "bloquear": True,
                "score_semantico": 0.0,
                "caso_valido": False,
                "roles": {},
                "razon": razon,
            }

        # ── ETAPA 1 y 2: Pre-filtro sintáctico con spaCy ────────────────────
        if not self._prefiltro_habilitado:
            return {
                "habilitado": False, "bloquear": False, "score_semantico": None,
                "caso_valido": False, "roles": {}, "razon": "pre-filtro no disponible",
            }

        self._cargar_spacy()
        if not self._prefiltro_habilitado:  # carga falló
            return {
                "habilitado": False, "bloquear": False, "score_semantico": None,
                "caso_valido": False, "roles": {}, "razon": "spaCy no disponible",
            }

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
                    "score_semantico": 0.0,
                    "caso_valido": False, "roles": roles, "razon": razon,
                }

            razon = "caso_valido" if caso_valido else "sin_evidencia_suficiente"
            return {
                "habilitado": True, "bloquear": False, "score_semantico": None,
                "caso_valido": caso_valido, "roles": roles, "razon": razon,
            }

        except Exception as exc:
            logger.warning("[PreFiltro] Error en análisis sintáctico: %s", exc)
            return {
                "habilitado": False, "bloquear": False, "score_semantico": None,
                "caso_valido": False, "roles": {}, "razon": str(exc),
            }

    # ── Clasificación ───────────────────────────────────────

    def predict(self, title: str, content: str) -> dict:
        """
        Clasifica una noticia como relevante o no relevante.

        Flujo v6.0 (3 capas de filtrado):
          1. pre_filtro_sintactico(): Escudo Léxico + spaCy.
             • Si FP confirmado → retorna score=0.0 SIN invocar BETO.
          2. BETO (finetuned o zero_shot).
          3. Post-filtro de Validación Semántica (NUEVO v6.0):
             • Si BETO da "Alta" (>= 0.85), valida con regex que el
               texto realmente describe NNA huérfano por feminicidio.
             • Puede degradar a "No relevante" o "Media".

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
              - postfiltro (dict): resultado del post-filtro v6.0
        """
        texto_completo = f"{title} {content[:1500]}"

        # ── Capa 1: Pre-filtro sintáctico ────────────────────────────────
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

        # ── Capa 2: Inferencia BETO ──────────────────────────────────────
        text = f"{title} [SEP] {content[:1500]}"
        if self.mode == "finetuned":
            resultado = self._predict_finetuned(text)
        else:
            resultado = self._predict_zero_shot(text)

        resultado["prefiltro"] = prefiltro

        # ── Capa 3: Post-filtro de Validación Semántica v6.0 ─────────────
        resultado = self._aplicar_post_filtro(resultado, texto_completo)

        return resultado

    def _aplicar_post_filtro(self, resultado: dict, texto: str) -> dict:
        """
        Aplica el post-filtro de validación semántica v6.1.

        Se ejecuta para noticias "Alta" (≥0.85) Y "Media" (0.50-0.84).
        Acciones posibles según clasificacion:

          Para "Alta":
            - "confirmar": VP confirmado, mantiene "Alta".
            - "degradar":  FP detectado → "No relevante" (score → 0.0).
            - "revisar":   Sin patrón claro → "Media" (revisión humana).

          Para "Media":
            - "confirmar": VP confirmado, mantiene "Media".
            - "degradar":  FP detectado → "No relevante" (score → 0.0).
            - "revisar":   Sin patrón claro → "No relevante" (score insuficiente
              sin evidencia fáctica; descarte conservador para reducir FP).
        """
        clasificacion = resultado.get("clasificacion", "")

        # Solo aplicar a Alta y Media; ignorar No relevante
        if clasificacion not in ("Alta", "Media"):
            resultado["postfiltro"] = {
                "validado": None,
                "accion": "skip",
                "razon": f"PostFiltro no aplicado (clasificacion={clasificacion})",
                "patron": "",
            }
            return resultado

        postfiltro = self._post_filtro_validacion(texto)
        resultado["postfiltro"] = postfiltro

        if postfiltro["accion"] == "degradar":
            # FP confirmado por post-filtro → bloquear siempre (Alta o Media)
            logger.info(
                "[PostFiltro] DEGRADAR %s→No relevante: %s",
                clasificacion, postfiltro["razon"],
            )
            resultado["score_semantico"] = 0.0
            resultado["es_relevante"] = False
            resultado["clasificacion"] = "No relevante"
            resultado["confianza"] = "alta"
            resultado["modo"] = resultado.get("modo", "") + "+postfiltro_degradado"

        elif postfiltro["accion"] == "revisar":
            if clasificacion == "Alta":
                # Ambiguo en Alta → degradar a Media para revisión humana
                logger.info(
                    "[PostFiltro] REVISAR Alta→Media: %s",
                    postfiltro["razon"],
                )
                resultado["clasificacion"] = "Media"
                resultado["confianza"] = "media"
                resultado["modo"] = resultado.get("modo", "") + "+postfiltro_revision"
                # Mantiene es_relevante=True para que no se pierda
            else:
                # Ambiguo en Media (0.50-0.84) sin evidencia VP → descartar
                # Sin patrón fáctico claro, el score medio no es suficiente.
                logger.info(
                    "[PostFiltro] REVISAR Media→No relevante (sin evidencia VP): %s",
                    postfiltro["razon"],
                )
                resultado["score_semantico"] = 0.0
                resultado["es_relevante"] = False
                resultado["clasificacion"] = "No relevante"
                resultado["confianza"] = "alta"
                resultado["modo"] = resultado.get("modo", "") + "+postfiltro_media_descartada"

        else:
            # VP confirmado → mantener clasificación
            logger.info(
                "[PostFiltro] CONFIRMADO %s: %s",
                clasificacion, postfiltro["razon"],
            )

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

        s = float(score)
        clasificacion = self._classify_score(s)
        return {
            "score_semantico": round(s, 4),
            "es_relevante": clasificacion in ("Alta", "Media"),
            "clasificacion": clasificacion,
            "confianza": self._confidence_level(s),
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

        clasificacion = self._classify_score(score)
        return {
            "score_semantico": round(score, 4),
            "es_relevante": clasificacion in ("Alta", "Media"),
            "clasificacion": clasificacion,
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

        # Guardar textos completos para el post-filtro
        textos_completos_beto = [
            f"{titles[i]} {contents[i][:1500]}" for i in indices_beto
        ]

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
                            clasificacion = self._classify_score(s)
                            beto_results.append({
                                "score_semantico": round(s, 4),
                                "es_relevante": clasificacion in ("Alta", "Media"),
                                "clasificacion": clasificacion,
                                "confianza": self._confidence_level(s),
                                "modo": "finetuned",
                            })
            else:
                beto_results = self._predict_zero_shot_batch(texts_beto)

            # Aplicar post-filtro v6.0 a cada resultado BETO
            for local_idx in range(len(beto_results)):
                beto_results[local_idx] = self._aplicar_post_filtro(
                    beto_results[local_idx],
                    textos_completos_beto[local_idx],
                )

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
            clasificacion = self._classify_score(s)
            results.append({
                "score_semantico": round(s, 4),
                "es_relevante": clasificacion in ("Alta", "Media"),
                "clasificacion": clasificacion,
                "confianza": self._confidence_level(s),
                "modo": "zero_shot",
                "sim_relevante": round(float(sim_relevante[i]), 4),
                "sim_no_relevante": round(float(sim_no_relevante[i]), 4),
            })
        return results

    @staticmethod
    def _classify_score(score: float) -> str:
        """
        Clasifica el score en tres niveles con umbrales estrictos (v5.3).

        Umbrales:
          score >= 0.85  → "Alta"         (certeza alta, caso genuino)
          0.50 <= s < 0.85 → "Media"      (posible, requiere revisión humana)
          score < 0.50   → "No relevante" (descartado)

        Nota: tanto "Alta" como "Media" producen es_relevante=True para
        no perder casos reales en la fase de captura; la distinción sirve
        para priorizar la revisión humana en el dashboard.
        """
        if score >= 0.85:
            return "Alta"
        elif score >= 0.50:
            return "Media"
        return "No relevante"

    @staticmethod
    def _confidence_level(score: float) -> str:
        """
        Nivel de confianza alineado con los umbrales v5.3.

        Bandas:
          score >= 0.85          → "alta"   (zona Alta confirmada)
          0.65 <= score < 0.85   → "media"  (zona Media con buena señal)
          0.50 <= score < 0.65   → "baja"   (zona Media limítrofe)
          score < 0.50           → "alta"   (descarte con alta certeza)
        """
        if score >= 0.85:
            return "alta"
        elif score >= 0.65:
            return "media"
        elif score >= 0.50:
            return "baja"
        # score < 0.50: el descarte también es confiable
        return "alta"

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
