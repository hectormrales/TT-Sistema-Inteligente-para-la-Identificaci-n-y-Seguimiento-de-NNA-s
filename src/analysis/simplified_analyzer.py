# src/analysis/simplified_analyzer.py
"""
Analizador simplificado que NO depende de gensim.
Implementa todos los pasos del análisis propuesto usando solo scikit-learn.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import os
import sys

# Agregar el directorio raíz al path para importaciones
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.collection.data_collector import collect_all_news, detect_children_mentions
from src.processing.text_processor import clean_and_lemmatize_series
from src.analysis.news_analyzer import cluster_dataframe
from src.analysis.synonym_dictionary import SynonymDictionary, enhanced_search

# Importaciones de ML que sí funcionan
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.cluster import KMeans

class SimplifiedNewsAnalyzer:
    """
    Clase principal que implementa análisis completo sin dependencias problemáticas.
    Usa scikit-learn para todo el análisis de ML.
    """
    
    def __init__(self):
        self.df_original = None
        self.df_processed = None
        self.df_analyzed = None
        self.vectorizer = None
        self.tfidf_matrix = None
        self.lda_model = None
        self.kmeans_model = None
        self.synonym_dict = SynonymDictionary()
        
    def step_1_collect_data(self) -> pd.DataFrame:
        """Paso 1: Recolección de datos desde RSS feeds."""
        print("=== PASO 1: RECOLECCIÓN DE DATOS ===")
        print("Recolectando noticias desde feeds RSS...")
        
        self.df_original = collect_all_news()
        
        if len(self.df_original) == 0:
            print("⚠️  No se recolectaron noticias. Verifique la configuración de RSS.")
            return self.df_original
        
        print(f"✅ {len(self.df_original)} noticias recolectadas")
        
        # Detectar menciones a NNA
        print("Detectando menciones a NNA...")
        self.df_original['menores_identificados'] = self.df_original['contenido'].apply(detect_children_mentions)
        nna_count = (self.df_original['menores_identificados'] == 'Si').sum()
        print(f"🎯 {nna_count} noticias con menciones a NNA detectadas")
        
        return self.df_original
    
    def step_2_save_initial_data(self, filepath: str = "data/noticias_raw.csv"):
        """Paso 2: Almacenamiento inicial en CSV."""
        print("=== PASO 2: ALMACENAMIENTO INICIAL ===")
        
        if self.df_original is None:
            raise ValueError("Debe ejecutar step_1_collect_data() primero")
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.df_original.to_csv(filepath, index=False, encoding='utf-8')
        print(f"✅ Datos guardados en: {filepath}")
        print(f"📊 Total de noticias: {len(self.df_original)}")
    
    def step_3_vectorize_text(self) -> pd.DataFrame:
        """Paso 3: Representación vectorial - TF-IDF."""
        print("=== PASO 3: REPRESENTACIÓN VECTORIAL (TF-IDF) ===")
        
        if self.df_original is None:
            raise ValueError("Debe ejecutar step_1_collect_data() primero")
        
        self.df_processed = self.df_original.copy()
        
        # Limpiar texto
        print("Limpiando y procesando texto...")
        self.df_processed['titulo_limpio'] = clean_and_lemmatize_series(self.df_processed['titulo'])
        self.df_processed['contenido_limpio'] = clean_and_lemmatize_series(self.df_processed['contenido'])
        
        # Crear vectorizador TF-IDF
        print("Creando representación vectorial TF-IDF...")
        texts = self.df_processed['contenido_limpio'].fillna('').astype(str).tolist()
        
        self.vectorizer = TfidfVectorizer(
            max_features=3000,
            stop_words=None,
            lowercase=True,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.8
        )
        
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        
        print(f"✅ Matriz TF-IDF creada: {self.tfidf_matrix.shape}")
        print(f"📊 {self.tfidf_matrix.shape[0]} documentos x {self.tfidf_matrix.shape[1]} características")
        
        return self.df_processed
    
    def step_4_topic_modeling(self, num_topics: int = 6) -> Tuple[pd.DataFrame, Dict]:
        """Paso 4: Modelado de tópicos usando LDA de scikit-learn."""
        print("=== PASO 4: MODELADO DE TÓPICOS (LDA) ===")
        
        if self.tfidf_matrix is None:
            raise ValueError("Debe ejecutar step_3_vectorize_text() primero")
        
        print(f"Entrenando modelo LDA con {num_topics} tópicos...")
        
        try:
            # Usar LDA de scikit-learn
            self.lda_model = LatentDirichletAllocation(
                n_components=num_topics,
                random_state=42,
                max_iter=20,
                learning_method='online',
                learning_offset=50.0
            )
            
            # Entrenar modelo
            doc_topic_matrix = self.lda_model.fit_transform(self.tfidf_matrix)
            
            # Asignar tópico dominante a cada documento
            dominant_topics = doc_topic_matrix.argmax(axis=1)
            topic_probabilities = doc_topic_matrix.max(axis=1)
            
            # Agregar al DataFrame
            self.df_processed['topic_id'] = dominant_topics
            self.df_processed['topic_probability'] = topic_probabilities
            
            # Crear información de tópicos
            feature_names = self.vectorizer.get_feature_names_out()
            topics_info = []
            
            for topic_idx, topic in enumerate(self.lda_model.components_):
                # Obtener palabras más importantes del tópico
                top_word_indices = topic.argsort()[::-1][:10]
                top_words = [feature_names[i] for i in top_word_indices]
                top_probs = [topic[i] for i in top_word_indices]
                
                topics_info.append({
                    'topic_id': topic_idx,
                    'words': top_words,
                    'probabilities': top_probs,
                    'description': ' '.join(top_words[:5])
                })
            
            # Agregar descripción del tópico al DataFrame
            topic_descriptions = {topic['topic_id']: topic['description'] 
                               for topic in topics_info}
            self.df_processed['topic_description'] = self.df_processed['topic_id'].map(topic_descriptions)
            
            # Información del modelo
            topic_info = {
                'topics': topics_info,
                'num_topics': num_topics,
                'perplexity': self.lda_model.perplexity(self.tfidf_matrix)
            }
            
            print("✅ Modelo LDA entrenado exitosamente")
            print(f"📈 Perplexity del modelo: {topic_info['perplexity']:.2f}")
            
            # Mostrar tópicos
            print("\n🔍 Tópicos descubiertos:")
            for topic in topics_info:
                print(f"  Tópico {topic['topic_id']}: {topic['description']}")
            
            return self.df_processed, topic_info
            
        except Exception as e:
            print(f"❌ Error en modelado de tópicos: {e}")
            return self.df_processed, None
    
    def step_5_clustering(self, n_clusters: int = 5) -> Tuple[pd.DataFrame, Dict]:
        """Paso 5: Agrupación usando K-Means."""
        print("=== PASO 5: AGRUPACIÓN (K-MEANS CLUSTERING) ===")
        
        if self.tfidf_matrix is None:
            raise ValueError("Debe ejecutar step_3_vectorize_text() primero")
        
        print(f"Aplicando K-Means con {n_clusters} clusters...")
        
        try:
            # Aplicar K-Means
            self.kmeans_model = KMeans(
                n_clusters=n_clusters,
                random_state=42,
                n_init=10
            )
            
            cluster_labels = self.kmeans_model.fit_predict(self.tfidf_matrix)
            
            # Agregar al DataFrame
            self.df_processed['cluster'] = cluster_labels
            
            # Calcular silhouette score
            from sklearn.metrics import silhouette_score
            if len(set(cluster_labels)) > 1:
                silhouette = silhouette_score(self.tfidf_matrix, cluster_labels)
            else:
                silhouette = 0.0
            
            # Obtener términos representativos por cluster
            feature_names = self.vectorizer.get_feature_names_out()
            cluster_terms = {}
            
            for cluster_id in range(n_clusters):
                # Obtener centroide del cluster
                centroid = self.kmeans_model.cluster_centers_[cluster_id]
                # Ordenar términos por importancia
                top_indices = centroid.argsort()[::-1][:12]
                cluster_terms[cluster_id] = [feature_names[i] for i in top_indices]
            
            cluster_info = {
                'silhouette': silhouette,
                'n_clusters': n_clusters,
                'top_terms': cluster_terms
            }
            
            print("✅ Clustering completado")
            print(f"📈 Silhouette score: {silhouette:.3f}")
            
            # Mostrar distribución
            cluster_counts = self.df_processed['cluster'].value_counts().sort_index()
            print("🔍 Distribución de clusters:")
            for cluster_id, count in cluster_counts.items():
                terms = ', '.join(cluster_terms[cluster_id][:5])
                print(f"  Cluster {cluster_id} ({count} noticias): {terms}")
            
            return self.df_processed, cluster_info
            
        except Exception as e:
            print(f"❌ Error en clustering: {e}")
            return self.df_processed, None
    
    def step_6_similarity_analysis(self) -> pd.DataFrame:
        """Paso 6: Análisis de similitud coseno."""
        print("=== PASO 6: ANÁLISIS DE SIMILITUD ===")
        
        if self.tfidf_matrix is None:
            raise ValueError("Debe ejecutar step_3_vectorize_text() primero")
        
        print("Calculando similitudes entre documentos...")
        
        try:
            # Calcular matriz de similitud coseno
            similarity_matrix = cosine_similarity(self.tfidf_matrix)
            
            # Para cada documento, encontrar el más similar
            for i in range(len(self.df_processed)):
                similarities = similarity_matrix[i]
                # Excluir el mismo documento
                similarities[i] = 0
                
                if similarities.max() > 0:
                    most_similar_idx = similarities.argmax()
                    max_similarity = similarities[most_similar_idx]
                else:
                    most_similar_idx = -1
                    max_similarity = 0.0
                
                self.df_processed.loc[i, 'most_similar_doc_idx'] = most_similar_idx
                self.df_processed.loc[i, 'max_similarity'] = max_similarity
            
            print("✅ Análisis de similitud completado")
            
            # Estadísticas
            avg_similarity = self.df_processed['max_similarity'].mean()
            high_similarity_count = (self.df_processed['max_similarity'] > 0.5).sum()
            
            print(f"📊 Similitud promedio: {avg_similarity:.3f}")
            print(f"📊 Pares con alta similitud (>0.5): {high_similarity_count}")
            
        except Exception as e:
            print(f"❌ Error en análisis de similitud: {e}")
        
        return self.df_processed
    
    def step_7_enhanced_search_setup(self) -> SynonymDictionary:
        """Paso 7: Configuración de búsqueda mejorada."""
        print("=== PASO 7: BÚSQUEDA MEJORADA ===")
        
        print("Configurando diccionario de sinónimos...")
        
        sample_terms = list(self.synonym_dict.synonyms.keys())[:10]
        print(f"✅ Diccionario cargado con {len(self.synonym_dict.synonyms)} términos")
        print(f"🔤 Términos de ejemplo: {', '.join(sample_terms)}")
        
        # Guardar diccionario
        dict_path = "data/synonym_dictionary.json"
        os.makedirs(os.path.dirname(dict_path), exist_ok=True)
        self.synonym_dict.save_to_file(dict_path)
        print(f"💾 Diccionario guardado en: {dict_path}")
        
        return self.synonym_dict
    
    def save_final_results(self, filepath: str = "data/noticias_analyzed_simplified.csv"):
        """Guarda los resultados finales."""
        print("=== GUARDANDO RESULTADOS FINALES ===")
        
        if self.df_processed is None:
            raise ValueError("Debe completar el análisis primero")
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.df_processed.to_csv(filepath, index=False, encoding='utf-8')
        print(f"✅ Resultados guardados en: {filepath}")
        
        # Guardar metadatos
        metadata = {
            'total_noticias': len(self.df_processed),
            'noticias_con_nna': int((self.df_processed['menores_identificados'] == 'Si').sum()),
            'columnas_disponibles': list(self.df_processed.columns),
            'version': 'simplified_analyzer_v1.0',
            'algoritmos_usados': ['TF-IDF', 'LDA (scikit-learn)', 'K-Means', 'Similitud Coseno']
        }
        
        import json
        metadata_path = filepath.replace('.csv', '_metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"📋 Metadatos guardados en: {metadata_path}")
        self.df_analyzed = self.df_processed
    
    def run_complete_analysis(self, 
                            num_topics: int = 6,
                            n_clusters: int = 4,
                            save_intermediate: bool = True) -> pd.DataFrame:
        """Ejecuta el pipeline completo de análisis."""
        print("🚀 INICIANDO ANÁLISIS COMPLETO SIMPLIFICADO")
        print("=" * 60)
        
        try:
            # Ejecutar todos los pasos
            self.step_1_collect_data()
            if save_intermediate:
                self.step_2_save_initial_data()
            
            self.step_3_vectorize_text()
            self.step_4_topic_modeling(num_topics=num_topics)
            self.step_5_clustering(n_clusters=n_clusters)
            self.step_6_similarity_analysis()
            self.step_7_enhanced_search_setup()
            
            # Guardar resultados finales
            self.save_final_results()
            
            print("\n" + "=" * 60)
            print("🎉 ANÁLISIS COMPLETADO EXITOSAMENTE")
            print(f"📊 {len(self.df_analyzed)} noticias analizadas")
            print("✨ Todos los métodos implementados sin dependencias problemáticas")
            
            return self.df_analyzed
            
        except Exception as e:
            print(f"\n❌ ERROR EN ANÁLISIS: {e}")
            print("💡 Revise la configuración y vuelva a intentar")
            raise
    
    def search_enhanced(self, query: str, max_results: int = 10) -> pd.DataFrame:
        """Búsqueda mejorada usando sinónimos."""
        if self.df_analyzed is None:
            raise ValueError("Debe completar el análisis primero")
        
        print(f"🔍 Búsqueda: '{query}'")
        
        # Realizar búsqueda
        results = enhanced_search(self.df_analyzed, query, ['titulo', 'contenido'])
        
        if len(results) > max_results:
            results = results.head(max_results)
        
        print(f"📋 {len(results)} resultados encontrados")
        
        return results[['titulo', 'fecha', 'fuente', 'cluster', 'topic_id', 'menores_identificados']]

# Función de conveniencia
def run_quick_analysis_simplified():
    """Función para ejecutar análisis rápido simplificado."""
    analyzer = SimplifiedNewsAnalyzer()
    return analyzer.run_complete_analysis()

if __name__ == "__main__":
    run_quick_analysis_simplified()