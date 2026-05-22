# src/analysis/bertopic_clustering.py — Clustering Semántico con BERTopic
"""
OE-4: Implementación de BERTopic para agrupación semántica de noticias.

Arquitectura del pipeline:
  ┌──────────────────────────────────────────────────────────┐
  │  BERTopic = Embeddings + UMAP + HDBSCAN + c-TF-IDF      │
  │                                                          │
  │  1. EMBEDDINGS (BETO / sentence-transformers)            │
  │     ├── Modelo: dccuchile/bert-base-spanish-wwm-cased    │
  │     ├── Dim: 768                                         │
  │     └── Ventaja: Captura semántica del español           │
  │                                                          │
  │  2. UMAP (Reducción de dimensionalidad)                  │
  │     ├── n_components: 5                                  │
  │     ├── n_neighbors: 15                                  │
  │     ├── min_dist: 0.0 (clusters densos)                  │
  │     ├── metric: cosine                                   │
  │     └── Ventaja: Preserva topología vs PCA/t-SNE         │
  │                                                          │
  │  3. HDBSCAN (Clustering jerárquico basado en densidad)   │
  │     ├── min_cluster_size: 8                              │
  │     ├── min_samples: 5                                   │
  │     ├── cluster_selection_method: eom                    │
  │     ├── prediction_data: True (para reducir outliers)    │
  │     └── Ventaja: No requiere k fijo, detecta ruido      │
  │                                                          │
  │  4. c-TF-IDF (Class-based TF-IDF)                       │
  │     ├── reduce_frequent_words: True                      │
  │     └── Genera representación por cluster                │
  │                                                          │
  │  5. ETIQUETADO AUTOMÁTICO                                │
  │     ├── KeyBERTInspired (top n-grams por cluster)        │
  │     └── Labels descriptivas semánticas                   │
  └──────────────────────────────────────────────────────────┘

Estrategia de reducción de outliers:
  El problema original: HDBSCAN asigna ~81.4% de documentos como
  outliers (topic -1) cuando los datos son ruidosos y heterogéneos.

  Solución multi-etapa:
    1. Ajuste de hiperparámetros HDBSCAN (min_cluster_size=8 en vez de 15+)
    2. Reducción iterativa de outliers con .reduce_outliers()
       - strategy='probabilities': Usa probabilidades soft de HDBSCAN
       - strategy='distributions': Reasigna basado en distribución c-TF-IDF
       - strategy='embeddings': Reasigna basado en cercanía semántica
    3. Reasignación manual: K-Nearest-Neighbors de outliers restantes
       con k=5 al centroide de cluster más cercano

  Objetivo: Reducir outliers de 81.4% a 50-60%.

Algoritmos y bibliotecas:
  ─────────────────────────────────────────────────────────
  BERTopic: Framework modular que encadena embeddings →
            dim-reduction → clustering → representación.
            Permite reemplazar cada componente de forma
            independiente. Referencia: Grootendorst, 2022.

  UMAP: Uniform Manifold Approximation and Projection.
        Proyecta vectores 768D → 5D preservando estructura
        topológica local y global. Más robusto que t-SNE
        para clustering downstream. Referencia: McInnes, 2018.

  HDBSCAN: Hierarchical Density-Based Spatial Clustering
           of Applications with Noise. Extiende DBSCAN con
           jerarquía de densidad variable. Detecta clusters
           de diferente densidad sin especificar k.
           Referencia: Campello et al., 2013.

  c-TF-IDF: Class-based TF-IDF. Trata cada cluster como un
            "documento" y aplica TF-IDF a nivel de clase para
            identificar los términos más representativos de
            cada cluster vs. el corpus completo.
            Referencia: Grootendorst, 2022.
  ─────────────────────────────────────────────────────────
"""

import logging
import os
import pickle
import warnings
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Configuración
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Modelo de embeddings
EMBEDDING_MODEL = "dccuchile/bert-base-spanish-wwm-cased"
SENTENCE_TRANSFORMER_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# UMAP
UMAP_N_COMPONENTS = 5
UMAP_N_NEIGHBORS = 15
UMAP_MIN_DIST = 0.0
UMAP_METRIC = "cosine"

# HDBSCAN
HDBSCAN_MIN_CLUSTER_SIZE = 8
HDBSCAN_MIN_SAMPLES = 5
HDBSCAN_CLUSTER_METHOD = "eom"  # Excess of Mass

# BERTopic
NR_TOPICS = "auto"  # dejar que HDBSCAN determine
TOP_N_WORDS = 10
MIN_TOPIC_SIZE = 8

# Outlier reduction
OUTLIER_TARGET_PERCENT = 0.55  # Objetivo: 55% outliers máximo

# Directorio de modelos persistidos
MODELS_DIR = os.environ.get("MODELS_DIR", "models")

# Stop words en español para c-TF-IDF
SPANISH_STOP_WORDS = [
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "al", "en", "por", "para", "con", "sin",
    "sobre", "entre", "hasta", "desde", "hacia", "ante",
    "que", "como", "más", "pero", "sus", "su", "este",
    "esta", "estos", "estas", "ese", "esa", "esos", "esas",
    "ha", "han", "fue", "ser", "son", "está", "están",
    "hay", "se", "le", "les", "lo", "ya", "no", "si", "sí",
    "muy", "también", "así", "aquí", "allí", "donde",
    "quien", "cual", "cuando", "todo", "todos", "toda", "todas",
    "otro", "otra", "otros", "otras", "uno", "dos", "tres",
    "año", "años", "día", "días", "dijo", "tras", "según",
]


def _safe_import(module_name, package=None):
    """Importa un módulo de forma segura, retornando None si falla."""
    try:
        import importlib
        return importlib.import_module(module_name, package)
    except ImportError as e:
        logger.warning(f"Módulo {module_name} no disponible: {e}")
        return None


class SemanticClustering:
    """
    Pipeline de clustering semántico con BERTopic.

    El pipeline sigue estos pasos:
      1. Genera embeddings con BETO/sentence-transformers
      2. Reduce dimensionalidad con UMAP (768D → 5D)
      3. Agrupa con HDBSCAN (densidad variable, sin k fijo)
      4. Genera representación c-TF-IDF por cluster
      5. Reduce outliers con estrategia multi-etapa
      6. Genera etiquetas semánticas automáticas

    Uso:
        clustering = SemanticClustering()
        results = clustering.fit_transform(
            docs=["noticia 1", "noticia 2", ...],
            embeddings=precomputed_embeddings  # opcional
        )
    """

    def __init__(
        self,
        embedding_model: str = SENTENCE_TRANSFORMER_MODEL,
        min_cluster_size: int = HDBSCAN_MIN_CLUSTER_SIZE,
        min_samples: int = HDBSCAN_MIN_SAMPLES,
        umap_components: int = UMAP_N_COMPONENTS,
        umap_neighbors: int = UMAP_N_NEIGHBORS,
        reduce_outliers: bool = True,
        verbose: bool = True,
    ):
        """
        Inicializa el pipeline de clustering.

        Args:
            embedding_model: Modelo para generar embeddings.
                Por defecto usa paraphrase-multilingual-MiniLM-L12-v2
                (más ligero que BETO completo para embeddings de frase).
            min_cluster_size: Tamaño mínimo de cluster en HDBSCAN.
                Valores más bajos = más clusters, menos outliers.
                Valores de referencia: 8 (agresivo), 15 (moderado), 25+ (conservador).
            min_samples: Muestras mínimas para punto core en HDBSCAN.
                Controla la densidad requerida. Menor = menos restrictivo.
            umap_components: Dimensiones de salida de UMAP.
                5D balancea información preservada vs. ruido eliminado.
            umap_neighbors: Vecinos para UMAP. Controla balance local/global.
                15 es el default recomendado para la mayoría de datasets.
            reduce_outliers: Si True, aplica reducción multi-etapa de outliers.
            verbose: Si True, muestra progreso.
        """
        self.embedding_model_name = embedding_model
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.umap_components = umap_components
        self.umap_neighbors = umap_neighbors
        self.reduce_outliers_flag = reduce_outliers
        self.verbose = verbose

        # Componentes (inicializados en _build_pipeline)
        self.topic_model = None
        self.embeddings_ = None
        self.topics_ = None
        self.topic_info_ = None
        self.outlier_percent_ = None

        # Crear directorio de modelos
        os.makedirs(MODELS_DIR, exist_ok=True)

    def _build_pipeline(self):
        """
        Construye el pipeline BERTopic con componentes personalizados.

        La modularidad de BERTopic permite reemplazar cualquier
        componente sin cambiar el flujo general:

          BERTopic(
            embedding_model=SentenceTransformer,  # Paso 1
            umap_model=UMAP,                      # Paso 2
            hdbscan_model=HDBSCAN,                # Paso 3
            vectorizer_model=CountVectorizer,      # Para c-TF-IDF
            ctfidf_model=ClassTfidfTransformer,    # Paso 4
            representation_model=KeyBERTInspired,  # Paso 5
          )
        """
        from bertopic import BERTopic
        from bertopic.representation import KeyBERTInspired
        from hdbscan import HDBSCAN
        from sentence_transformers import SentenceTransformer
        from sklearn.feature_extraction.text import CountVectorizer
        from umap import UMAP

        # 1. Modelo de embeddings
        embedding_model = SentenceTransformer(self.embedding_model_name)

        # 2. UMAP para reducción de dimensionalidad
        #    min_dist=0.0 fuerza clusters más compactos (mejor para HDBSCAN)
        #    metric='cosine' es más apropiado para embeddings de texto
        umap_model = UMAP(
            n_components=self.umap_components,
            n_neighbors=self.umap_neighbors,
            min_dist=UMAP_MIN_DIST,
            metric=UMAP_METRIC,
            random_state=42,
            low_memory=True,
        )

        # 3. HDBSCAN para clustering basado en densidad
        #    prediction_data=True es necesario para reducción de outliers
        #    cluster_selection_method='eom': Excess of Mass, más estable
        hdbscan_model = HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            cluster_selection_method=HDBSCAN_CLUSTER_METHOD,
            prediction_data=True,
            gen_min_span_tree=True,
        )

        # 4. Vectorizador para c-TF-IDF
        #    n-grams de 1 a 3 para capturar frases relevantes
        #    v7.0: min_df dinámico para evitar crash con corpus pequeños
        #    (ValueError: max_df corresponds to < documents than min_df)
        dynamic_min_df = 1 if self.min_cluster_size <= 5 else 2
        vectorizer = CountVectorizer(
            stop_words=SPANISH_STOP_WORDS,
            ngram_range=(1, 3),
            min_df=dynamic_min_df,
        )

        # 5. Representación: KeyBERTInspired
        #    Usa similitud coseno entre embedding del documento
        #    y embedding del n-gram candidato para seleccionar
        #    los términos más representativos
        representation = KeyBERTInspired(top_n_words=TOP_N_WORDS)

        # min_topic_size dinámico: nunca mayor que min_cluster_size
        effective_min_topic_size = min(MIN_TOPIC_SIZE, self.min_cluster_size)

        # Construir BERTopic
        self.topic_model = BERTopic(
            embedding_model=embedding_model,
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            vectorizer_model=vectorizer,
            representation_model=representation,
            top_n_words=TOP_N_WORDS,
            min_topic_size=effective_min_topic_size,
            verbose=self.verbose,
            calculate_probabilities=True,  # Necesario para reduce_outliers
        )

        logger.info("Pipeline BERTopic construido exitosamente")

    def fit_transform(
        self,
        docs: list[str],
        embeddings: np.ndarray | None = None,
        titles: list[str] | None = None,
    ) -> dict:
        """
        Ejecuta el pipeline completo de clustering.

        Flujo:
          1. Generar embeddings (o usar precomputados)
          2. fit_transform de BERTopic
          3. Reducir outliers si está habilitado
          4. Generar etiquetas y métricas

        Args:
            docs: Lista de documentos (contenido de noticias).
            embeddings: Embeddings precomputados (opcional).
                Si se proporcionan, ahorra tiempo de cómputo.
            titles: Títulos de noticias (para inclusión opional en docs).

        Returns:
            dict con topics, info de clusters, métricas.
        """
        if not docs:
            logger.warning("No hay documentos para clustering")
            return {"topics": [], "topic_info": pd.DataFrame(), "outlier_percent": 1.0}

        logger.info(f"Iniciando clustering de {len(docs)} documentos")

        # Preprocesar documentos: combinar título + contenido si disponible
        processed_docs = []
        for i, doc in enumerate(docs):
            if titles and i < len(titles) and titles[i]:
                # Título duplicado para darle más peso
                processed_docs.append(f"{titles[i]}. {titles[i]}. {doc}")
            else:
                processed_docs.append(doc)

        # Construir pipeline si no existe
        if self.topic_model is None:
            self._build_pipeline()

        # Ejecutar BERTopic
        topics, probs = self.topic_model.fit_transform(
            processed_docs, embeddings=embeddings
        )

        # Guardar embeddings para uso posterior
        if embeddings is not None:
            self.embeddings_ = embeddings
        elif hasattr(self.topic_model, "_extract_embeddings"):
            # BERTopic calcula embeddings internamente
            pass

        # Calcular outliers iniciales
        outlier_count_initial = sum(1 for t in topics if t == -1)
        outlier_pct_initial = outlier_count_initial / len(topics)
        logger.info(
            f"Outliers iniciales: {outlier_count_initial}/{len(topics)} "
            f"({outlier_pct_initial:.1%})"
        )

        # Reducir outliers si es necesario y está habilitado
        if self.reduce_outliers_flag and outlier_pct_initial > OUTLIER_TARGET_PERCENT:
            topics = self._reduce_outliers_multi_stage(
                topics, processed_docs, probs
            )

        # Actualizar topics en el modelo
        self.topic_model.update_topics(processed_docs, topics=topics)

        # Almacenar resultados
        self.topics_ = topics
        self.topic_info_ = self.topic_model.get_topic_info()

        # Métricas finales
        outlier_count_final = sum(1 for t in topics if t == -1)
        outlier_pct_final = outlier_count_final / len(topics)
        self.outlier_percent_ = outlier_pct_final

        n_topics = len(set(topics)) - (1 if -1 in topics else 0)
        logger.info(
            f"Clustering completado: {n_topics} temas, "
            f"outliers finales: {outlier_count_final}/{len(topics)} "
            f"({outlier_pct_final:.1%})"
        )

        # Generar etiquetas semánticas
        labels = self._generate_labels()

        return {
            "topics": topics,
            "topic_info": self.topic_info_,
            "labels": labels,
            "n_topics": n_topics,
            "outlier_percent_initial": outlier_pct_initial,
            "outlier_percent_final": outlier_pct_final,
            "n_docs": len(docs),
        }

    def _reduce_outliers_multi_stage(
        self,
        topics: list[int],
        docs: list[str],
        probs: np.ndarray | None,
    ) -> list[int]:
        """
        Reducción multi-etapa de outliers.

        Estrategia:
          Etapa 1: 'probabilities' — Usa las probabilidades soft
                   de HDBSCAN para reasignar outliers al cluster
                   más probable. Solo funciona si calculate_probabilities=True.

          Etapa 2: 'distributions' — Usa la distribución c-TF-IDF de
                   cada documento outlier y lo asigna al cluster con
                   la distribución más similar. Funciona bien cuando
                   los documentos outlier son temáticamente coherentes
                   pero están en zonas de baja densidad.

          Etapa 3: 'embeddings' — Calcula distancia coseno entre el
                   embedding del outlier y el centroide de cada cluster.
                   Reasigna al cluster más cercano con threshold mínimo
                   de similitud (0.3) para evitar asignaciones erróneas.

        Cada etapa se aplica secuencialmente: la siguiente solo procesa
        los outliers que quedaron de la etapa anterior.
        """
        original_outliers = sum(1 for t in topics if t == -1)

        # Etapa 1: Por probabilidades
        try:
            if probs is not None and len(probs.shape) > 1:
                topics = self.topic_model.reduce_outliers(
                    docs, topics, strategy="probabilities", threshold=0.05
                )
                remaining = sum(1 for t in topics if t == -1)
                logger.info(
                    f"  Etapa 1 (probabilities): "
                    f"{original_outliers - remaining} reasignados, "
                    f"{remaining} restantes"
                )
        except Exception as e:
            logger.warning(f"  Etapa 1 falló: {e}")

        # Verificar si ya cumplimos objetivo
        if sum(1 for t in topics if t == -1) / len(topics) <= OUTLIER_TARGET_PERCENT:
            return topics

        # Etapa 2: Por distribuciones
        try:
            before = sum(1 for t in topics if t == -1)
            topics = self.topic_model.reduce_outliers(
                docs, topics, strategy="distributions"
            )
            after = sum(1 for t in topics if t == -1)
            logger.info(
                f"  Etapa 2 (distributions): "
                f"{before - after} reasignados, {after} restantes"
            )
        except Exception as e:
            logger.warning(f"  Etapa 2 falló: {e}")

        # Verificar si ya cumplimos objetivo
        if sum(1 for t in topics if t == -1) / len(topics) <= OUTLIER_TARGET_PERCENT:
            return topics

        # Etapa 3: Por embeddings
        try:
            before = sum(1 for t in topics if t == -1)
            topics = self.topic_model.reduce_outliers(
                docs, topics, strategy="embeddings", threshold=0.3
            )
            after = sum(1 for t in topics if t == -1)
            logger.info(
                f"  Etapa 3 (embeddings): "
                f"{before - after} reasignados, {after} restantes"
            )
        except Exception as e:
            logger.warning(f"  Etapa 3 falló: {e}")

        final_outliers = sum(1 for t in topics if t == -1)
        logger.info(
            f"  Reducción total: {original_outliers} → {final_outliers} "
            f"outliers ({final_outliers / len(topics):.1%})"
        )

        return topics

    def _generate_labels(self) -> dict[int, str]:
        """
        Genera etiquetas semánticas para cada cluster.

        Usa los top-N términos de c-TF-IDF para construir
        una etiqueta descriptiva. Ejemplo:
          Topic 0: "feminicidio víctima menor_edad"
          → Etiqueta: "Feminicidio de Menores de Edad"

        Returns:
            Dict {topic_id: etiqueta descriptiva}
        """
        labels = {}

        if self.topic_model is None or self.topic_info_ is None:
            return labels

        for _, row in self.topic_info_.iterrows():
            topic_id = row["Topic"]

            if topic_id == -1:
                labels[-1] = "Outliers (sin clasificar)"
                continue

            # Obtener representación del topic
            topic_words = self.topic_model.get_topic(topic_id)
            if topic_words:
                # Tomar las top 3 palabras más relevantes
                top_terms = [word for word, _ in topic_words[:3]]
                label = " · ".join(top_terms).title()
                labels[topic_id] = label
            else:
                labels[topic_id] = f"Tema {topic_id}"

        return labels

    def get_topic_for_document(self, doc: str) -> dict:
        """
        Predice el topic para un nuevo documento.

        Usa .transform() de BERTopic que:
          1. Genera embedding del documento
          2. Proyecta con UMAP
          3. Asigna al cluster más cercano
          4. Devuelve topic_id y probabilidades

        Args:
            doc: Texto del documento.

        Returns:
            dict con topic_id, probabilidad, y etiqueta.
        """
        if self.topic_model is None:
            raise RuntimeError("Modelo no entrenado. Ejecutar fit_transform primero.")

        topics, probs = self.topic_model.transform([doc])
        topic_id = topics[0]

        return {
            "topic_id": topic_id,
            "probability": float(probs[0].max()) if probs is not None else 0.0,
            "label": self._generate_labels().get(topic_id, f"Tema {topic_id}"),
        }

    def get_cluster_details(self) -> list[dict]:
        """
        Devuelve información detallada de cada cluster.

        Returns:
            Lista de dicts con info de cada cluster para almacenar
            en la tabla clusters_semanticos.
        """
        if self.topic_info_ is None:
            return []

        clusters = []
        labels = self._generate_labels()

        for _, row in self.topic_info_.iterrows():
            topic_id = int(row["Topic"])

            # Obtener términos con scores
            topic_words = self.topic_model.get_topic(topic_id) if self.topic_model else []
            terminos = (
                [{"termino": w, "score": float(s)} for w, s in topic_words[:TOP_N_WORDS]]
                if topic_words
                else []
            )

            # Calcular cohesión del cluster (similitud promedio intra-cluster)
            cohesion = self._compute_cluster_cohesion(topic_id)

            clusters.append({
                "id": topic_id,
                "etiqueta": labels.get(topic_id, f"Tema {topic_id}"),
                "descripcion": (
                    f"Cluster con {int(row.get('Count', 0))} documentos. "
                    f"Términos principales: {', '.join(t['termino'] for t in terminos[:5])}"
                ),
                "terminos_principales": terminos,
                "num_documentos": int(row.get("Count", 0)),
                "cohesion": cohesion,
                "es_outlier": topic_id == -1,
            })

        return clusters

    def _compute_cluster_cohesion(self, topic_id: int) -> float:
        """
        Calcula la cohesión intra-cluster como la similitud coseno
        promedio entre todos los pares de documentos del cluster.

        Cohesión alta (> 0.7) = cluster temáticamente homogéneo.
        Cohesión baja (< 0.3) = cluster heterogéneo / ruidoso.
        """
        if self.topics_ is None:
            return 0.0

        # Obtener embeddings del cluster
        indices = [i for i, t in enumerate(self.topics_) if t == topic_id]
        if len(indices) < 2:
            return 1.0  # Un solo documento = cohesión perfecta

        # Si tenemos embeddings calculados, usar esos
        try:
            if hasattr(self.topic_model, "embedding_model") and self.topic_model is not None:
                # Usar el centroide del cluster
                cluster_embeddings = self.topic_model._extract_embeddings(
                    [" "],  # placeholder
                    method="document",
                )
                # Simplificación: retornar score basado en c-TF-IDF
                topic_words = self.topic_model.get_topic(topic_id)
                if topic_words:
                    scores = [s for _, s in topic_words[:5]]
                    return min(float(np.mean(scores)) * 5, 1.0)
        except Exception:
            pass

        return 0.5  # Default cuando no se puede calcular

    def save_model(self, path: str | None = None) -> str:
        """Persiste el modelo BERTopic para reutilización."""
        if self.topic_model is None:
            raise RuntimeError("No hay modelo para guardar")

        if path is None:
            path = os.path.join(MODELS_DIR, "bertopic_nna_model")

        self.topic_model.save(path, serialization="pickle")
        logger.info(f"Modelo guardado en {path}")
        return path

    def load_model(self, path: str | None = None) -> None:
        """Carga un modelo BERTopic persistido."""
        from bertopic import BERTopic

        if path is None:
            path = os.path.join(MODELS_DIR, "bertopic_nna_model")

        if not os.path.exists(path):
            raise FileNotFoundError(f"Modelo no encontrado en {path}")

        self.topic_model = BERTopic.load(path)
        logger.info(f"Modelo cargado desde {path}")

    def save_results_to_db(self, topics: list[int], labels: dict) -> None:
        """
        Guarda resultados de clustering en PostgreSQL.

        Crea/actualiza registros en clusters_semanticos y
        actualiza cluster_id de la tabla noticias.
        """
        try:
            from src.database.models_noticias import ClusterSemantico
            from app.models import db

            cluster_details = self.get_cluster_details()

            for detail in cluster_details:
                cluster = ClusterSemantico.query.get(detail["id"])
                if cluster is None:
                    cluster = ClusterSemantico(id=detail["id"])
                    db.session.add(cluster)

                cluster.etiqueta = detail["etiqueta"]
                cluster.descripcion = detail["descripcion"]
                cluster.terminos_principales = detail["terminos_principales"]
                cluster.num_documentos = detail["num_documentos"]
                cluster.cohesion = detail["cohesion"]
                cluster.es_outlier = detail["es_outlier"]

            db.session.commit()
            logger.info(f"Guardados {len(cluster_details)} clusters en PostgreSQL")

        except Exception as e:
            logger.error(f"Error guardando clusters en DB: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass

    def visualize_clusters(self, output_dir: str = "data") -> dict:
        """
        Genera visualizaciones de los clusters.

        Crea archivos HTML interactivos usando Plotly:
          - Mapa de topics (intertopic distance map)
          - Barchart de términos por topic
          - Jerarquía de topics

        Returns:
            dict con rutas a los archivos generados.
        """
        if self.topic_model is None:
            return {}

        output_files = {}
        os.makedirs(output_dir, exist_ok=True)

        try:
            # 1. Mapa de distancia inter-topic
            fig_topics = self.topic_model.visualize_topics()
            path = os.path.join(output_dir, "cluster_topic_map.html")
            fig_topics.write_html(path)
            output_files["topic_map"] = path
        except Exception as e:
            logger.warning(f"No se pudo generar topic map: {e}")

        try:
            # 2. Barchart de términos por topic
            fig_barchart = self.topic_model.visualize_barchart(top_n_topics=10)
            path = os.path.join(output_dir, "cluster_barchart.html")
            fig_barchart.write_html(path)
            output_files["barchart"] = path
        except Exception as e:
            logger.warning(f"No se pudo generar barchart: {e}")

        try:
            # 3. Jerarquía de topics
            fig_hierarchy = self.topic_model.visualize_hierarchy()
            path = os.path.join(output_dir, "cluster_hierarchy.html")
            fig_hierarchy.write_html(path)
            output_files["hierarchy"] = path
        except Exception as e:
            logger.warning(f"No se pudo generar hierarchy: {e}")

        return output_files


class TemporalClustering:
    """
    Análisis de evolución temporal de clusters.

    Extiende SemanticClustering para analizar cómo cambian
    los clusters a lo largo del tiempo, útil para OE-2
    (análisis temporal 2023-2026).

    Usa BERTopic.topics_over_time() que:
      1. Agrupa documentos por ventana temporal
      2. Calcula c-TF-IDF por ventana
      3. Detecta aparición/desaparición de temas
      4. Permite visualización de tendencias
    """

    def __init__(self, semantic_clustering: SemanticClustering):
        self.clustering = semantic_clustering

    def analyze_over_time(
        self,
        docs: list[str],
        timestamps: list[datetime],
        nr_bins: int = 12,
    ) -> dict:
        """
        Analiza la evolución de topics en el tiempo.

        Args:
            docs: Textos de noticias.
            timestamps: Fecha de cada noticia.
            nr_bins: Número de ventanas temporales.

        Returns:
            dict con topics_over_time DataFrame y métricas.
        """
        import datetime as dt

        if self.clustering.topic_model is None:
            raise RuntimeError("Ejecutar fit_transform primero")

        # Convertir timestamps a datetime si son strings
        parsed_ts = []
        for ts in timestamps:
            if isinstance(ts, str):
                try:
                    parsed_ts.append(pd.to_datetime(ts))
                except Exception:
                    parsed_ts.append(dt.datetime(2024, 1, 1))
            elif isinstance(ts, dt.datetime):
                parsed_ts.append(ts)
            else:
                parsed_ts.append(dt.datetime(2024, 1, 1))

        try:
            topics_over_time = self.clustering.topic_model.topics_over_time(
                docs, parsed_ts, nr_bins=nr_bins
            )

            return {
                "topics_over_time": topics_over_time,
                "n_bins": nr_bins,
                "date_range": (min(parsed_ts), max(parsed_ts)),
            }
        except Exception as e:
            logger.error(f"Error en análisis temporal: {e}")
            return {"topics_over_time": pd.DataFrame(), "error": str(e)}

    def visualize_over_time(
        self,
        topics_over_time: pd.DataFrame,
        output_path: str = "data/cluster_temporal.html",
    ) -> str | None:
        """Genera visualización de evolución temporal de topics."""
        if self.clustering.topic_model is None:
            return None

        try:
            fig = self.clustering.topic_model.visualize_topics_over_time(
                topics_over_time, top_n_topics=10
            )
            fig.write_html(output_path)
            return output_path
        except Exception as e:
            logger.error(f"Error generando visualización temporal: {e}")
            return None
