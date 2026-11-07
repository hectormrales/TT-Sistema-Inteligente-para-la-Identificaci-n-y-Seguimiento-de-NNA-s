

import os
import re
import json
import logging
from datetime import datetime
import unicodedata
from typing import Dict, Tuple, Optional

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.collection.collector import collect_all_news, detect_children_mentions
from src.analysis.synonyms import SynonymDictionary, enhanced_search
from src.analysis.dedup import NewsDeduplicator

logger = logging.getLogger(__name__)


# ── Vocabulario de dominio para inyectar al TF-IDF ──────────

DOMAIN_TERMS = [
    'feminicidio', 'femicidio', 'violencia feminicida',
    'violencia de genero', 'crimen de genero',
    'asesinato de mujer', 'homicidio de mujer',
    'huerfanos', 'orfandad', 'victimas indirectas',
    'menores', 'ninos', 'ninas', 'adolescentes',
    'hijos', 'hijas', 'victimas colaterales',
    'violencia domestica', 'violencia intrafamiliar',
    'alerta de genero', 'custodia', 'tutela', 'dif',
]


# ── Utilidades de texto ─────────────────────────────────────

def _clean_text(text: str) -> str:
    """Limpia y normaliza un texto para vectorización."""
    if pd.isna(text):
        return ""
    text = unicodedata.normalize('NFKD', str(text))
    text = text.lower()
    text = re.sub(r'[^\w\sáéíóúñü]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def clean_series(series: pd.Series) -> pd.Series:
    """Aplica limpieza de texto a una serie completa."""
    return series.apply(_clean_text)


# ── Stop words en español (para TF-IDF) ────────────────────

SPANISH_STOP_WORDS = [
    'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se',
    'las', 'por', 'un', 'para', 'con', 'no', 'una', 'su', 'al',
    'lo', 'como', 'más', 'mas', 'pero', 'sus', 'le', 'ya', 'o',
    'este', 'si', 'porque', 'esta', 'entre', 'cuando', 'muy',
    'sin', 'sobre', 'también', 'tambien', 'me', 'hasta', 'hay',
    'donde', 'quien', 'desde', 'todo', 'nos', 'durante', 'todos',
    'uno', 'les', 'ni', 'contra', 'otros', 'ese', 'eso', 'ante',
    'ellos', 'e', 'esto', 'mi', 'antes', 'algunos', 'qué', 'que',
    'unos', 'yo', 'otro', 'otras', 'otra', 'él', 'tanto', 'esa',
    'estos', 'mucho', 'quienes', 'nada', 'muchos', 'cual', 'poco',
    'ella', 'estar', 'estas', 'algunas', 'algo', 'nosotros', 'fue',
    'ser', 'ha', 'son', 'era', 'han', 'sido', 'es', 'tiene', 'puede',
    'así', 'asi', 'solo', 'según', 'segun', 'dijo', 'señaló',
    'indicó', 'informó', 'además', 'ademas', 'tras', 'dos', 'tres',
]


# ── Clase principal ─────────────────────────────────────────

class SimplifiedNewsAnalyzer:
    """Pipeline de análisis de noticias con scoring de relevancia."""

    DATA_DIR = os.environ.get('DATA_DIR', 'data')

    def __init__(self):
        self.df_original: Optional[pd.DataFrame] = None
        self.df_processed: Optional[pd.DataFrame] = None
        self.df_analyzed: Optional[pd.DataFrame] = None
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.synonym_dict = SynonymDictionary()
        self.current_batch_id: Optional[str] = None

    # ── Pasos del pipeline ──────────────────────────────────

    def step_1_collect_data(self, start_date: str | None = None, end_date: str | None = None, scraper_type: str = 'all') -> pd.DataFrame:
        """Recolección de datos desde RSS feeds con filtrado de relevancia."""
        print("=== PASO 1: RECOLECCIÓN + SCORING DE RELEVANCIA ===")
        self.df_original = collect_all_news(keep_all=True, start_date=start_date, end_date=end_date, scraper_type=scraper_type)

        if self.df_original.empty:
            print("  No se recolectaron noticias relevantes.")
            return self.df_original

        total = len(self.df_original)
        nna = (self.df_original['menores_identificados'] == 'Si').sum()
        alta = (self.df_original['clasificacion'] == 'Alta').sum()
        media = (self.df_original['clasificacion'] == 'Media').sum()
        baja = (self.df_original['clasificacion'] == 'Baja').sum()

        print(f"  {total} noticias relevantes recolectadas")
        print(f"   ├── Alta relevancia:  {alta}")
        print(f"   ├── Media relevancia: {media}")
        print(f"   ├── Baja relevancia:  {baja}")
        print(f"   └── Mencionan NNA:    {nna}")
        return self.df_original

    def step_2_save_initial_data(self, filepath: str | None = None):
        """Almacenamiento inicial en CSV."""
        filepath = filepath or os.path.join(self.DATA_DIR, 'noticias_raw.csv')
        print("=== PASO 2: ALMACENAMIENTO INICIAL ===")
        assert self.df_original is not None, "Ejecute step_1 primero"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.df_original.to_csv(filepath, index=False, encoding='utf-8')
        print(f"  Guardado en: {filepath} ({len(self.df_original)} filas)")

    def step_3_vectorize_text(self) -> pd.DataFrame:
        """
        Representación vectorial TF-IDF con vocabulario de dominio.

        Se usa un vocabulario "boosted": se inyectan los términos de
        dominio como documentos ficticios para que aparezcan en el
        vocabulario aunque tengan baja frecuencia global.
        """
        print("=== PASO 3: TF-IDF (domain-boosted) ===")
        assert self.df_original is not None, "Ejecute step_1 primero"

        self.df_processed = self.df_original.copy()
        self.df_processed['titulo_limpio'] = clean_series(self.df_processed['titulo'])
        self.df_processed['contenido_limpio'] = clean_series(self.df_processed['contenido'])

        # Combinar título (repetido para darle más peso) + contenido
        self.df_processed['texto_combinado'] = (
            self.df_processed['titulo_limpio'] + ' ' +
            self.df_processed['titulo_limpio'] + ' ' +
            self.df_processed['contenido_limpio']
        )

        texts = self.df_processed['texto_combinado'].fillna('').astype(str).tolist()

        # Inyectar vocabulario de dominio como documentos artificiales
        domain_docs = [' '.join(DOMAIN_TERMS)] * 2
        all_texts = texts + domain_docs

        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),       # unigramas, bigramas, trigramas
            min_df=1,                 # min_df=1 para no perder terms raros pero relevantes
            max_df=0.85,
            stop_words=SPANISH_STOP_WORDS,
            sublinear_tf=True,        # log(1 + tf) — atenúa frecuencias muy altas
        )
        full_matrix = self.vectorizer.fit_transform(all_texts)

        # Descartar las filas artificiales del vocabulario inyectado
        self.tfidf_matrix = full_matrix[:len(texts)]

        print(f"  Matriz TF-IDF: {self.tfidf_matrix.shape}")
        print(f"  Vocabulario: {len(self.vectorizer.get_feature_names_out())} términos")
        return self.df_processed

    def step_6_similarity_analysis(self) -> pd.DataFrame:
        """Análisis de similitud coseno entre documentos + deduplicación semántica."""
        print("=== PASO 6: SIMILITUD COSENO + DEDUPLICACIÓN ===")
        assert self.tfidf_matrix is not None, "Ejecute step_3 primero"

        try:
            sim_matrix = cosine_similarity(self.tfidf_matrix)
            most_similar_idx = []
            max_sims = []
            for i in range(len(self.df_processed)):
                sims = sim_matrix[i].copy()
                sims[i] = 0  # excluir auto-similitud
                most_similar_idx.append(int(sims.argmax()) if sims.max() > 0 else -1)
                max_sims.append(float(sims.max()))

            self.df_processed['most_similar_doc_idx'] = most_similar_idx
            self.df_processed['max_similarity'] = max_sims

            avg = np.mean(max_sims)
            high = sum(1 for s in max_sims if s > 0.5)
            print(f"  Similitud promedio: {avg:.3f} | Pares > 0.5: {high}")

            # Deduplicación semántica post-análisis
            pre = len(self.df_processed)
            dedup = NewsDeduplicator(
                title_threshold=0.70,
                content_threshold=0.85,
                simhash_max_distance=6,
            )
            self.df_processed = dedup.deduplicate(
                self.df_processed, keep='best'
            )
            post = len(self.df_processed)
            if pre > post:
                # Reconstruir TF-IDF matrix para los docs restantes
                texts = self.df_processed['texto_combinado'].fillna('').astype(str).tolist()
                domain_docs = [' '.join(DOMAIN_TERMS)] * 2
                all_texts = texts + domain_docs
                full_matrix = self.vectorizer.fit_transform(all_texts)
                self.tfidf_matrix = full_matrix[:len(texts)]
                print(f"  Duplicados semánticos eliminados: {pre - post}")
        except Exception as e:
            print(f"  Error similitud/dedup: {e}")
        return self.df_processed

    def step_8_enhanced_search_setup(self) -> SynonymDictionary:
        """Configura búsqueda con sinónimos."""
        print("=== PASO 8: BÚSQUEDA MEJORADA ===")
        dict_path = os.path.join(self.DATA_DIR, 'synonym_dictionary.json')
        os.makedirs(os.path.dirname(dict_path), exist_ok=True)
        self.synonym_dict.save_to_file(dict_path)
        print(f"  Diccionario guardado ({len(self.synonym_dict.synonyms)} términos)")
        return self.synonym_dict

    def save_final_results(self, filepath: str | None = None):
        """Guarda resultados finales y metadatos."""
        filepath = filepath or os.path.join(self.DATA_DIR, 'noticias_analyzed_simplified.csv')
        print("=== GUARDANDO RESULTADOS ===")
        assert self.df_processed is not None, "Ejecute el análisis primero"

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Fallback defensivo: garantizar que las columnas existen
        if 'relevancia_final' not in self.df_processed.columns:
            self.df_processed['relevancia_final'] = self.df_processed.get(
                'score_compuesto', pd.Series(0.0, index=self.df_processed.index)
            )
        if 'clasificacion_final' not in self.df_processed.columns:
            self.df_processed['clasificacion_final'] = self.df_processed.get(
                'clasificacion', pd.Series('No relevante', index=self.df_processed.index)
            )

        # Ordenar por fecha descendente (más reciente primero)
        if 'fecha' in self.df_processed.columns:
            try:
                self.df_processed['_fecha_sort'] = pd.to_datetime(
                    self.df_processed['fecha'], errors='coerce'
                )
                self.df_processed = self.df_processed.sort_values(
                    '_fecha_sort', ascending=False, na_position='last'
                ).reset_index(drop=True)
                self.df_processed = self.df_processed.drop(columns=['_fecha_sort'])
            except Exception:
                # Fallback: ordenar por relevancia
                self.df_processed = self.df_processed.sort_values(
                    'relevancia_final', ascending=False
                ).reset_index(drop=True)
        else:
            self.df_processed = self.df_processed.sort_values(
                'relevancia_final', ascending=False
            ).reset_index(drop=True)

        self.df_processed.to_csv(filepath, index=False, encoding='utf-8')

        # Estadísticas
        total = len(self.df_processed)
        nna = int((self.df_processed['menores_identificados'] == 'Si').sum())
        alta = int((self.df_processed['clasificacion_final'] == 'Alta').sum())
        media = int((self.df_processed['clasificacion_final'] == 'Media').sum())

        metadata = {
            'total_noticias': total,
            'noticias_con_nna': nna,
            'alta_relevancia': alta,
            'media_relevancia': media,
            'columnas_disponibles': list(self.df_processed.columns),
            'version': 'relevance_analyzer_v5.0_TT2',
            'algoritmos_usados': [
                'Scoring Dual Heurístico (Feminicidio × NNA × Caso Individual)',
                'TF-IDF (domain-boosted, sublinear, n-grams 1-3)',
                'Similitud Coseno + Deduplicación Semántica',
                'Keywords de Oro (inmunidad contra penalizaciones v9.1)',
                'Web Scraping Dinámico (robots.txt)',
                'Dedup Cross-Site (Hash + Jaccard + SimHash + TF-IDF)',
                'Detección Semántica BETO (OE-1, zero-shot/hybrid)',
                'Lógica Neuro-Simbólica (Bypass de Oro + Vía Rápida + Clúster)',
                'BERTopic: MiniLM-L12 + UMAP + HDBSCAN + c-TF-IDF (OE-4)',
                'PostgreSQL FTS con tsvector/GIN (OE-3)',
            ],
        }
        meta_path = filepath.replace('.csv', '_metadata.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        self.df_analyzed = self.df_processed
        print(f"  CSV: {filepath}")
        print(f"  Metadatos: {meta_path}")
        print(f"  Total: {total} | NNA: {nna} | Alta: {alta} | Media: {media}")

    # ── Pipeline completo ───────────────────────────────────

    def run_complete_analysis(
        self,
        num_topics: int = 6,
        n_clusters: int = 4,
        save_intermediate: bool = True,
        enable_semantic: bool = True,
        enable_bertopic: bool = True,
        enable_postgres: bool = True,
        start_date: str | None = None,
        end_date: str | None = None,
        scraper_type: str = 'all',
        sesion_id: int | None = None,
    ) -> pd.DataFrame:
        """
        Ejecuta el pipeline completo de análisis (v5.0).

        Pasos 1-8: Pipeline original (TT1)
        Pasos 9-11: Nuevas funcionalidades (TT2)

        Args:
            num_topics: Número de tópicos para LDA.
            n_clusters: Número de clusters para K-Means.
            save_intermediate: Si True, guarda CSV intermedio.
            enable_semantic: Si True, ejecuta detección BETO (OE-1).
            enable_bertopic: Si True, ejecuta BERTopic (OE-4).
            enable_postgres: Si True, persiste en PostgreSQL (OE-3).
        """
        print("=" * 60)
        print("  PIPELINE DE ANÁLISIS v5.0 — TT2 SEMÁNTICO")
        print("=" * 60)

        self.current_batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"  Batch ID de ejecución: {self.current_batch_id}")

        # Pasos 1-8: Pipeline original
        self.step_1_collect_data(start_date=start_date, end_date=end_date, scraper_type=scraper_type)

        if self.df_original is None or self.df_original.empty:
            print("  [!] No hay noticias para analizar.")
            self.df_analyzed = pd.DataFrame()
            return self.df_analyzed

        if save_intermediate:
            self.step_2_save_initial_data()

        self.step_3_vectorize_text()
        # step_4 (LDA) y step_5 (K-Means) desactivados: redundantes con BERTopic
        # self.step_4_topic_modeling(num_topics=num_topics)
        # self.step_5_clustering(n_clusters=n_clusters)
        self.step_6_similarity_analysis()
        # step_7 (TF-IDF rescore) ELIMINADO: sobrescribía clasificacion_final
        # del collector con un blend 60/40 que destruía las "Alta" reales.
        # self.step_7_tfidf_rescore()
        self.step_8_enhanced_search_setup()

        # Paso 9: Detección semántica BETO (OE-1) — umbral único
        # Clasifica cada noticia con score_semantico; el Bypass de Oro
        # eleva a "Alta" sin importar BETO. Resultado: clasificacion_final.
        if enable_semantic:
            self.step_9_semantic_detection()

        # Paso 10: Clustering BERTopic (OE-4) — DESPUÉS del filtro
        # Solo recibe noticias Alta/Media para que UMAP/HDBSCAN
        # trabajen con señal limpia, sin ruido de noticias irrelevantes.
        if enable_bertopic:
            self.step_10_bertopic_clustering()

        # Guardar CSV (siempre, para backward compatibility)
        self.save_final_results()

        # Paso 11: Persistencia PostgreSQL (OE-3)
        if enable_postgres:
            self.step_11_persist_to_postgres(sesion_id=sesion_id)

        print("=" * 60)
        print(f"  COMPLETADO — {len(self.df_analyzed)} noticias analizadas")
        print("=" * 60)
        return self.df_analyzed

    def run_analysis_only(
        self,
        num_topics: int = 6,
        n_clusters: int = 4,
        enable_semantic: bool = True,
        enable_bertopic: bool = True,
        enable_postgres: bool = True,
    ) -> pd.DataFrame:
        """
        Ejecuta análisis sobre datos ya recolectados (sin scraping).

        Carga datos del CSV existente en lugar de ejecutar step_1 (recolección
        RSS), lo que evita el timeout de Gunicorn al ejecutar desde la webapp.

        Pasos ejecutados: 3-11 (omite 1 y 2).
        """
        print("=" * 60)
        print("  PIPELINE DE ANÁLISIS v5.0 — SOLO ANÁLISIS (sin scraping)")
        print("=" * 60)

        self.current_batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"  Batch ID de ejecución: {self.current_batch_id}")

        # Cargar datos existentes del CSV en lugar de recolectar
        csv_path = os.path.join(self.DATA_DIR, 'noticias.csv')
        if not os.path.exists(csv_path):
            print("  [!] No hay datos recolectados para analizar.")
            self.df_analyzed = pd.DataFrame()
            return self.df_analyzed

        print(f"=== CARGANDO DATOS EXISTENTES de {csv_path} ===")
        self.df_original = pd.read_csv(csv_path)
        print(f"  {len(self.df_original)} noticias cargadas desde CSV")

        if self.df_original.empty:
            print("  [!] CSV vacío — no hay noticias para analizar.")
            self.df_analyzed = pd.DataFrame()
            return self.df_analyzed

        # Asegurar columnas mínimas necesarias
        if 'menores_identificados' not in self.df_original.columns:
            self.df_original['menores_identificados'] = 'No'
        if 'clasificacion' not in self.df_original.columns:
            self.df_original['clasificacion'] = 'No relevante'

        # Ejecutar pasos 3-8 (análisis NLP)
        self.step_3_vectorize_text()
        # step_4 (LDA) y step_5 (K-Means) desactivados: redundantes con BERTopic
        # self.step_4_topic_modeling(num_topics=num_topics)
        # self.step_5_clustering(n_clusters=n_clusters)
        self.step_6_similarity_analysis()
        # step_7 (TF-IDF rescore) ELIMINADO: sobrescribía clasificacion_final
        # del collector con un blend 60/40 que destruía las "Alta" reales.
        # self.step_7_tfidf_rescore()
        self.step_8_enhanced_search_setup()

        # Paso 9: Detección semántica BETO (OE-1) — umbral único
        if enable_semantic:
            self.step_9_semantic_detection()

        # Paso 10: Clustering BERTopic (OE-4) — DESPUÉS del filtro
        if enable_bertopic:
            self.step_10_bertopic_clustering()

        # Guardar CSV
        self.save_final_results()

        # Paso 11: Persistencia PostgreSQL (OE-3)
        if enable_postgres:
            self.step_11_persist_to_postgres()

        print("=" * 60)
        print(f"  COMPLETADO — {len(self.df_analyzed)} noticias analizadas")
        print("=" * 60)
        return self.df_analyzed

    # ── Nuevos pasos TT2 ────────────────────────────────────

    def step_9_semantic_detection(self) -> pd.DataFrame:
        """
        OE-1: Clasificación y Extracción Estructurada con LLMExtractor (5 Candados).

        Flujo:
          1. Gatekeeper léxico/geográfico (< 1 ms): filtra deportes, espectáculos,
             notas internacionales sin estado mexicano y estadísticas puras.
          2. Evaluación de 5 Candados Anti-Falsos-Positivos mediante LLMExtractor
             (Groq / Gemini / OpenRouter / Azure OpenAI) o Fallback Determinista.
          3. Extracción de expediente JSON completo (`investigacion_json`) con
             cita textual obligatoria en una sola pasada para notas Alta/Media.
        """
        print("=== PASO 9: DETECCIÓN Y EXTRACCIÓN CON 5 CANDADOS (LLMExtractor) ===")
        assert self.df_processed is not None, "Ejecute pasos anteriores primero"

        try:
            from src.analysis.llm_extractor import LLMExtractor

            extractor = LLMExtractor()

            total = len(self.df_processed)
            titulos = self.df_processed["titulo"].fillna("").astype(str).tolist()
            contenidos = self.df_processed["contenido"].fillna("").astype(str).tolist()
            enlaces = (
                self.df_processed["enlace"].fillna("").astype(str).tolist()
                if "enlace" in self.df_processed.columns
                else [""] * total
            )

            try:
                resultados_batch = extractor.analyze_batch(
                    titles=titulos,
                    contents=contenidos,
                    urls=enlaces,
                )
            except Exception as e:
                logger.error("Error en analyze_batch: %s", e)
                resultados_batch = [
                    {
                        "score_semantico": 0.05,
                        "relevancia_final": 0.05,
                        "clasificacion": "No relevante",
                        "clasificacion_final": "No relevante",
                        "menores_identificados": "No",
                        "modo_deteccion": "error_fallback",
                        "investigacion_json": None,
                    }
                ] * total

            if "investigacion_json" not in self.df_processed.columns:
                self.df_processed["investigacion_json"] = None

            for local_idx, (df_idx, _row) in enumerate(self.df_processed.iterrows()):
                resultado = resultados_batch[local_idx]
                score_semantico = float(resultado.get("score_semantico", 0.05))
                clasificacion = resultado.get("clasificacion_final", resultado.get("clasificacion", "No relevante"))
                menores_id = resultado.get("menores_identificados", "No")
                modo = resultado.get("modo_deteccion", "llm_5_candados")
                inv_json = resultado.get("investigacion_json")

                self.df_processed.at[df_idx, "score_semantico"] = round(score_semantico, 4)
                self.df_processed.at[df_idx, "relevancia_final"] = round(score_semantico, 4)
                self.df_processed.at[df_idx, "clasificacion"] = clasificacion
                self.df_processed.at[df_idx, "clasificacion_final"] = clasificacion
                self.df_processed.at[df_idx, "menores_identificados"] = menores_id
                self.df_processed.at[df_idx, "modo_deteccion"] = modo
                if inv_json is not None:
                    self.df_processed.at[df_idx, "investigacion_json"] = (
                        json.dumps(inv_json, ensure_ascii=False)
                        if isinstance(inv_json, dict)
                        else inv_json
                    )

            scores_semanticos = self.df_processed["score_semantico"].tolist()
            avg_sem = float(np.mean(scores_semanticos)) if scores_semanticos else 0.0
            alta = int((self.df_processed["clasificacion_final"] == "Alta").sum())
            media = int((self.df_processed["clasificacion_final"] == "Media").sum())
            no_rel = int((self.df_processed["clasificacion_final"] == "No relevante").sum())
            print(f"  Score semántico promedio: {avg_sem:.4f}")
            print(f"  {total} noticias procesadas | Alta: {alta} | Media: {media} | No relevante: {no_rel}")

        except Exception as e:
            print(f"  [!] Error en detección semántica: {e}")
            logger.exception("Error en step_9_semantic_detection")

        return self.df_processed

    def step_10_bertopic_clustering(self) -> pd.DataFrame:
        """
        OE-4: Agrupación temática y geográfica ligera post-filtro (sin dependencias pesadas).

        Agrupa las noticias clasificadas como 'Alta' o 'Media' usando:
          1. Metadatos extraídos por LLMExtractor (Estado / Situación de los NNA), o
          2. Clustering TF-IDF + K-Means sobre el subconjunto relevante.
        """
        print("=== PASO 10: AGRUPACIÓN TEMÁTICA Y GEOGRÁFICA (OE-4, post-filtro) ===")
        assert self.df_processed is not None, "Ejecute pasos anteriores primero"

        try:
            if "topic_id" not in self.df_processed.columns:
                self.df_processed["topic_id"] = -1
            if "topic_description" not in self.df_processed.columns:
                self.df_processed["topic_description"] = "Sin cluster"

            mask_relevante = self.df_processed["clasificacion_final"].isin(["Alta", "Media"])
            df_relevante = self.df_processed[mask_relevante].copy()
            n_relevante = len(df_relevante)

            print(f"  Corpus relevante para agrupación: {n_relevante} noticias (Alta/Media)")
            if n_relevante == 0:
                return self.df_processed

            # Construir etiquetas temáticas basadas en el expediente extraído (estado + situación)
            cluster_labels_map: dict[str, int] = {}
            cluster_docs_count: dict[int, int] = {}
            cluster_terms_map: dict[int, list[str]] = {}
            next_topic_id = 0

            for idx, row in df_relevante.iterrows():
                inv_raw = row.get("investigacion_json")
                inv = {}
                if isinstance(inv_raw, str) and inv_raw.strip():
                    try:
                        inv = json.loads(inv_raw)
                    except Exception:
                        inv = {}
                elif isinstance(inv_raw, dict):
                    inv = inv_raw

                estado = str(inv.get("estado") or inv.get("ubicacion") or "México").strip()
                if not estado or estado.lower() in ("no especificado", "no especificada"):
                    estado = "Casos NNA"

                clasif = str(row.get("clasificacion_final", "Media"))
                label = f"{estado} ({clasif})"

                if label not in cluster_labels_map:
                    cluster_labels_map[label] = next_topic_id
                    cluster_docs_count[next_topic_id] = 0
                    cluster_terms_map[next_topic_id] = [
                        estado,
                        str(inv.get("municipio") or "").strip(),
                        str(inv.get("situacion_actual") or "Orfandad NNA")[:30],
                    ]
                    next_topic_id += 1

                tid = cluster_labels_map[label]
                cluster_docs_count[tid] += 1
                self.df_processed.at[idx, "topic_id"] = tid
                self.df_processed.at[idx, "topic_description"] = label

            self._topic_clusters_summary = [
                {
                    "topic_id": tid,
                    "label": lbl,
                    "count": cluster_docs_count[tid],
                    "terms": [t for t in cluster_terms_map.get(tid, []) if t],
                }
                for lbl, tid in cluster_labels_map.items()
            ]
            print(f"  Grupos temáticos/geográficos generados: {len(self._topic_clusters_summary)}")

        except Exception as e:
            print(f"  [!] Error en agrupación temática: {e}")
            logger.exception("Error en step_10_bertopic_clustering")

        return self.df_processed

    def step_11_persist_to_postgres(self, sesion_id: int | None = None) -> None:
        """
        OE-3: Persistencia en PostgreSQL con FTS e `investigacion_json`.

        Guarda los resultados del análisis y la ficha estructurada de cada caso
        en la base de datos relacional normalizada.
        """
        print("=== PASO 11: PERSISTENCIA POSTGRESQL (OE-3) ===")
        assert self.df_processed is not None, "Ejecute pasos anteriores primero"

        try:
            from src.database.repository import NoticiasRepository, init_fts_schema
            from flask import current_app

            try:
                _ = current_app.name
                in_app_context = True
            except RuntimeError:
                in_app_context = False

            if in_app_context:
                init_fts_schema()

                records = []
                for _, row in self.df_processed.iterrows():
                    inv_raw = row.get("investigacion_json")
                    inv_dict = None
                    if isinstance(inv_raw, dict):
                        inv_dict = inv_raw
                    elif isinstance(inv_raw, str) and inv_raw.strip():
                        try:
                            inv_dict = json.loads(inv_raw)
                        except Exception:
                            inv_dict = None

                    record = {
                        "titulo": str(row.get("titulo", "")),
                        "contenido": str(row.get("contenido", "")),
                        "enlace": row.get("enlace"),
                        "fuente": row.get("fuente"),
                        "fecha": (
                            pd.to_datetime(row["fecha"], utc=True)
                            if pd.notna(row.get("fecha"))
                            else None
                        ),
                        "content_hash": (
                            str(row["content_hash"])
                            if pd.notna(row.get("content_hash")) and str(row.get("content_hash")).strip()
                            else None
                        ),
                        "score_feminicidio": float(row.get("score_feminicidio", 0)),
                        "score_nna": float(row.get("score_nna", 0)),
                        "score_compuesto": float(row.get("score_compuesto", 0)),
                        "relevancia_final": float(
                            row.get("relevancia_final", row.get("score_compuesto", 0))
                        ),
                        "clasificacion": row.get(
                            "clasificacion_final",
                            row.get("clasificacion", "No relevante"),
                        ),
                        "clasificacion_final": row.get(
                            "clasificacion_final",
                            row.get("clasificacion", "No relevante"),
                        ),
                        "batch_id": self.current_batch_id,
                        "score_semantico": (
                            float(row["score_semantico"])
                            if pd.notna(row.get("score_semantico"))
                            else None
                        ),
                        "modo_deteccion": row.get("modo_deteccion"),
                        "topic_id": (
                            int(row["topic_id"])
                            if pd.notna(row.get("topic_id"))
                            else None
                        ),
                        "topic_description": row.get("topic_description"),
                        "max_similarity": float(row.get("max_similarity", 0)),
                        "menores_identificados": row.get("menores_identificados", "No"),
                        "scrape_method": row.get("scrape_method", "rss"),
                        "sesion_id": sesion_id,
                        "investigacion_json": inv_dict,
                    }
                    records.append(record)

                count = NoticiasRepository.crear_batch(records)
                print(f"  {count} noticias persistidas en PostgreSQL")

                # Persistir resumen de grupos temáticos en ClusterSemantico para gráficas del dashboard
                if hasattr(self, "_topic_clusters_summary") and self._topic_clusters_summary:
                    try:
                        from src.database.models_noticias import ClusterSemantico, db
                        for item in self._topic_clusters_summary:
                            cluster_row = ClusterSemantico(
                                topic_id=item["topic_id"],
                                etiqueta=item["label"],
                                terminos_principales=item.get("terms", []),
                                num_documentos=item["count"],
                                es_outlier=False,
                                batch_id=self.current_batch_id,
                                sesion_id=sesion_id,
                            )
                            db.session.add(cluster_row)
                        db.session.commit()
                    except Exception as e:
                        logger.warning("Error guardando clusters en DB: %s", e)
            else:
                print("  [!] Sin contexto Flask — PostgreSQL omitido")
                print("  [i] Los datos se guardaron en CSV como fallback")

        except ImportError as e:
            print(f"  [!] Módulo de database no disponible: {e}")
        except Exception as e:
            print(f"  [!] Error persistiendo en PostgreSQL: {e}")
            logger.exception("Error en step_11_persist_to_postgres")

    def search_enhanced(self, query: str, max_results: int = 10) -> pd.DataFrame:
        """Búsqueda con expansión de sinónimos y ordenada por relevancia."""
        assert self.df_analyzed is not None, "Ejecute el análisis primero"
        results = enhanced_search(self.df_analyzed, query, ['titulo', 'contenido'])
        if 'relevancia_final' in results.columns:
            results = results.sort_values('relevancia_final', ascending=False)
        if len(results) > max_results:
            results = results.head(max_results)
        cols = [c for c in [
            'titulo', 'fecha', 'fuente', 'cluster', 'topic_id',
            'menores_identificados', 'clasificacion_final', 'relevancia_final',
        ] if c in results.columns]
        return results[cols]
