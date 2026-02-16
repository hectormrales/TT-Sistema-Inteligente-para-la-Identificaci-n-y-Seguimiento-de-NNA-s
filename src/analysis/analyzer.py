# src/analysis/analyzer.py — Analizador de noticias con scoring de relevancia
"""
Pipeline de análisis NLP con filtrado inteligente:
  1. Recolección RSS con scoring dual (feminicidio + NNA)
  2. Filtrado por relevancia (descarta no-relevantes)
  3. TF-IDF con vocabulario domain-boosted
  4. LDA (modelado de tópicos)
  5. K-Means (clustering temático)
  6. Similitud coseno (detección de duplicados / noticias relacionadas)
  7. Reclasificación TF-IDF: re-score usando los vectores aprendidos
  8. Búsqueda con sinónimos

El cambio principal respecto a la versión anterior es que ahora:
  • Se filtran noticias irrelevantes ANTES del análisis.
  • Se usa un scoring dual ponderado (feminicidio × NNA).
  • Los clusters se enriquecen con etiquetas de relevancia.
  • Se genera una columna 'relevancia_final' que combina el scoring
    heurístico (keywords) con el scoring estadístico (TF-IDF).
"""

import os
import re
import json
import unicodedata
from typing import Dict, Tuple, Optional

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from src.collection.collector import collect_all_news, detect_children_mentions
from src.analysis.synonyms import SynonymDictionary, enhanced_search


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
        self.lda_model: Optional[LatentDirichletAllocation] = None
        self.kmeans_model: Optional[KMeans] = None
        self.synonym_dict = SynonymDictionary()

    # ── Pasos del pipeline ──────────────────────────────────

    def step_1_collect_data(self) -> pd.DataFrame:
        """Recolección de datos desde RSS feeds con filtrado de relevancia."""
        print("=== PASO 1: RECOLECCIÓN + SCORING DE RELEVANCIA ===")
        self.df_original = collect_all_news(keep_all=False)

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

    def step_4_topic_modeling(self, num_topics: int = 6) -> Tuple[pd.DataFrame, dict | None]:
        """Modelado de tópicos con LDA (scikit-learn)."""
        print(f"=== PASO 4: LDA ({num_topics} tópicos) ===")
        assert self.tfidf_matrix is not None, "Ejecute step_3 primero"

        try:
            self.lda_model = LatentDirichletAllocation(
                n_components=num_topics, random_state=42,
                max_iter=30, learning_method='online', learning_offset=50.0,
            )
            doc_topics = self.lda_model.fit_transform(self.tfidf_matrix)

            self.df_processed['topic_id'] = doc_topics.argmax(axis=1)
            self.df_processed['topic_probability'] = doc_topics.max(axis=1)

            feature_names = self.vectorizer.get_feature_names_out()
            topics_info = []
            for tid, topic in enumerate(self.lda_model.components_):
                top_idx = topic.argsort()[::-1][:10]
                words = [feature_names[i] for i in top_idx]
                topics_info.append({
                    'topic_id': tid,
                    'words': words,
                    'description': ' '.join(words[:5]),
                })
                print(f"  Tópico {tid}: {', '.join(words[:6])}")

            desc_map = {t['topic_id']: t['description'] for t in topics_info}
            self.df_processed['topic_description'] = self.df_processed['topic_id'].map(desc_map)

            info = {
                'topics': topics_info,
                'num_topics': num_topics,
                'perplexity': self.lda_model.perplexity(self.tfidf_matrix),
            }
            print(f"  Perplexity: {info['perplexity']:.2f}")
            return self.df_processed, info
        except Exception as e:
            print(f"  Error LDA: {e}")
            return self.df_processed, None

    def step_5_clustering(self, n_clusters: int = 5) -> Tuple[pd.DataFrame, dict | None]:
        """Agrupación con K-Means."""
        print(f"=== PASO 5: K-MEANS ({n_clusters} clusters) ===")
        assert self.tfidf_matrix is not None, "Ejecute step_3 primero"

        try:
            # Auto-ajustar n_clusters si hay pocas noticias
            n_rows = self.tfidf_matrix.shape[0]
            n_clusters = min(n_clusters, max(2, n_rows // 3))

            self.kmeans_model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = self.kmeans_model.fit_predict(self.tfidf_matrix)
            self.df_processed['cluster'] = labels

            sil = (
                silhouette_score(self.tfidf_matrix, labels)
                if len(set(labels)) > 1 else 0.0
            )

            feature_names = self.vectorizer.get_feature_names_out()
            cluster_terms = {}
            for cid in range(n_clusters):
                centroid = self.kmeans_model.cluster_centers_[cid]
                top_idx = centroid.argsort()[::-1][:12]
                terms = [feature_names[i] for i in top_idx]
                cluster_terms[cid] = terms
                print(f"  Cluster {cid}: {', '.join(terms[:6])}")

            print(f"  Silhouette score: {sil:.3f}")
            return self.df_processed, {
                'silhouette': sil,
                'n_clusters': n_clusters,
                'top_terms': cluster_terms,
            }
        except Exception as e:
            print(f"  Error clustering: {e}")
            return self.df_processed, None

    def step_6_similarity_analysis(self) -> pd.DataFrame:
        """Análisis de similitud coseno entre documentos."""
        print("=== PASO 6: SIMILITUD COSENO ===")
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
        except Exception as e:
            print(f"  Error similitud: {e}")
        return self.df_processed

    def step_7_tfidf_rescore(self) -> pd.DataFrame:
        """
        Reclasificación TF-IDF: usa los vectores aprendidos para calcular
        un score de similitud contra un "documento ideal" construido con
        los términos de dominio.
        """
        print("=== PASO 7: RECLASIFICACIÓN TF-IDF ===")
        assert self.tfidf_matrix is not None, "Ejecute step_3 primero"

        try:
            # Crear un documento "ideal" con los términos de dominio
            ideal_doc = ' '.join(DOMAIN_TERMS * 3)
            ideal_vec = self.vectorizer.transform([ideal_doc])

            # Similitud coseno de cada noticia contra el doc ideal
            sims = cosine_similarity(self.tfidf_matrix, ideal_vec).flatten()
            self.df_processed['tfidf_relevance'] = sims

            # Combinar scoring heurístico con TF-IDF
            heuristic = self.df_processed['score_compuesto'].values
            tfidf_rel = sims

            # Promedio ponderado: 60% heurístico + 40% TF-IDF
            combined = 0.60 * heuristic + 0.40 * tfidf_rel
            self.df_processed['relevancia_final'] = np.round(combined, 4)

            # Re-clasificar con el score combinado
            def _classify(score):
                if score >= 0.50:
                    return 'Alta'
                elif score >= 0.30:
                    return 'Media'
                elif score >= 0.15:
                    return 'Baja'
                return 'No relevante'

            self.df_processed['clasificacion_final'] = (
                self.df_processed['relevancia_final'].apply(_classify)
            )

            alta = (self.df_processed['clasificacion_final'] == 'Alta').sum()
            media = (self.df_processed['clasificacion_final'] == 'Media').sum()
            print(f"  Alta relevancia (combinado): {alta}")
            print(f"  Media relevancia (combinado): {media}")
        except Exception as e:
            print(f"  Error reclasificación: {e}")
            self.df_processed['relevancia_final'] = self.df_processed.get(
                'score_compuesto', 0
            )
            self.df_processed['clasificacion_final'] = self.df_processed.get(
                'clasificacion', 'No relevante'
            )
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

        # Ordenar por relevancia final descendente
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
            'version': 'relevance_analyzer_v3.0',
            'algoritmos_usados': [
                'Scoring Dual Heurístico (Feminicidio × NNA)',
                'TF-IDF (domain-boosted, sublinear, n-grams 1-3)',
                'LDA (topic modeling)',
                'K-Means (clustering)',
                'Similitud Coseno',
                'Reclasificación TF-IDF (doc ideal)',
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
    ) -> pd.DataFrame:
        """Ejecuta los 8 pasos del pipeline de análisis."""
        print("=" * 60)
        print("  PIPELINE DE ANÁLISIS v3.0 — RELEVANCIA DUAL")
        print("=" * 60)

        self.step_1_collect_data()

        if self.df_original is None or self.df_original.empty:
            print("  [!] No hay noticias para analizar.")
            self.df_analyzed = pd.DataFrame()
            return self.df_analyzed

        if save_intermediate:
            self.step_2_save_initial_data()

        self.step_3_vectorize_text()
        self.step_4_topic_modeling(num_topics=num_topics)
        self.step_5_clustering(n_clusters=n_clusters)
        self.step_6_similarity_analysis()
        self.step_7_tfidf_rescore()
        self.step_8_enhanced_search_setup()
        self.save_final_results()

        print("=" * 60)
        print(f"  COMPLETADO — {len(self.df_analyzed)} noticias analizadas")
        print("=" * 60)
        return self.df_analyzed

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
