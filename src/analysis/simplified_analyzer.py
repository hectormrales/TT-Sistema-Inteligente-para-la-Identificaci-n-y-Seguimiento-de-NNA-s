# src/analysis/simplified_analyzer.py
"""
Analizador simplificado que NO depende de gensim.
Implementa todos los pasos del anlisis propuesto usando solo scikit-learn.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import os
import sys

# Agregar el directorio raz al path para importaciones
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.collection.data_collector import collect_all_news, detect_children_mentions
from src.analysis.synonym_dictionary import SynonymDictionary, enhanced_search

# Importaciones de ML que s funcionan
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.cluster import KMeans
import re
import unicodedata

def clean_and_lemmatize_series(text_series):
    """
    Funcin simplificada de limpieza de texto.
    """
    def clean_text(text):
        if pd.isna(text):
            return ""
        # Normalizar unicode
        text = unicodedata.normalize('NFKD', str(text))
        # Convertir a minsculas
        text = text.lower()
        # Eliminar caracteres especiales, mantener solo letras, nmeros y espacios
        text = re.sub(r'[^\w\s]', ' ', text)
        # Eliminar espacios mltiples
        text = re.sub(r'\s+', ' ', text)
        # Eliminar espacios al inicio y final
        text = text.strip()
        return text
    
    return text_series.apply(clean_text)

class SimplifiedNewsAnalyzer:
    """
    Clase principal que implementa anlisis completo sin dependencias problemticas.
    Usa scikit-learn para todo el anlisis de ML.
    """
    
    def __init__(self):
        self.df_original = None
        self.df_processed = None
        self.df_analyzed = None
        self.vectorizer = None
        self.tfidf_matrix = None
        self.lda_model = None
        self.kmeans_model = None
        self.dbscan_model = None
        self.synonym_dict = SynonymDictionary()
    
    def _get_spanish_stopwords(self):
        """
        Retorna lista de stopwords en espaol.
        Estas son palabras comunes sin valor semntico que deben filtrarse.
        """
        return [
            'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se',
            'no', 'haber', 'por', 'con', 'su', 'para', 'como', 'estar',
            'tener', 'le', 'lo', 'todo', 'pero', 'ms', 'hacer', 'o',
            'poder', 'decir', 'este', 'ir', 'otro', 'ese', 'la', 'si',
            'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'l', 'muy',
            'sin', 'vez', 'mucho', 'saber', 'qu', 'sobre', 'mi', 'alguno',
            'mismo', 'yo', 'tambin', 'hasta', 'ao', 'dos', 'querer',
            'entre', 'as', 'primero', 'desde', 'grande', 'eso', 'ni',
            'nos', 'llegar', 'pasar', 'tiempo', 'ella', 's', 'da',
            'uno', 'bien', 'poco', 'deber', 'entonces', 'poner', 'cosa',
            'tanto', 'hombre', 'parecer', 'nuestro', 'tan', 'donde',
            'ahora', 'parte', 'despus', 'vida', 'quedar', 'siempre',
            'creer', 'hablar', 'llevar', 'dejar', 'nada', 'cada',
            'seguir', 'menos', 'nuevo', 'encontrar', 'algo', 'solo',
            'estos', 'trabajar', 'ltimo', 'largo', 'sentir', 'mano',
            'venir', 'volver', 'tomar', 'conocer', 'vivir', 'pensar',
            'salir', 'mayor', 'tal', 'compaero', 'aunque', 'fue',
            'sido', 'han', 'son', 'era', 'estaba', 'haba', 'puede',
            'pueden', 'debe', 'deben', 'hace', 'hacen', 'hizo', 'hicieron',
            'va', 'van', 'iba', 'iban', 'sea', 'sean', 'tenga', 'tengan'
        ]
        
    def step_1_collect_data(self) -> pd.DataFrame:
        """Paso 1: Recoleccin de datos desde RSS feeds."""
        print("=== PASO 1: RECOLECCIN DE DATOS ===")
        print("Recolectando noticias desde feeds RSS...")
        
        self.df_original = collect_all_news()
        
        if len(self.df_original) == 0:
            print("  No se recolectaron noticias. Verifique la configuracin de RSS.")
            return self.df_original
        
        print(f" {len(self.df_original)} noticias recolectadas")
        
        # Detectar menciones a NNA
        print("Detectando menciones a NNA...")
        self.df_original['menores_identificados'] = self.df_original['contenido'].apply(detect_children_mentions)
        nna_count = (self.df_original['menores_identificados'] == 'Si').sum()
        print(f" {nna_count} noticias con menciones a NNA detectadas")
        
        return self.df_original
    
    def step_2_save_initial_data(self, filepath: str = "data/noticias_raw.csv"):
        """Paso 2: Almacenamiento inicial en CSV."""
        print("=== PASO 2: ALMACENAMIENTO INICIAL ===")
        
        if self.df_original is None:
            raise ValueError("Debe ejecutar step_1_collect_data() primero")
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.df_original.to_csv(filepath, index=False, encoding='utf-8')
        print(f" Datos guardados en: {filepath}")
        print(f" Total de noticias: {len(self.df_original)}")
    
    def step_3_vectorize_text(self) -> pd.DataFrame:
        """Paso 3: Representacin vectorial - TF-IDF."""
        print("=== PASO 3: REPRESENTACIN VECTORIAL (TF-IDF) ===")
        
        if self.df_original is None:
            raise ValueError("Debe ejecutar step_1_collect_data() primero")
        
        self.df_processed = self.df_original.copy()
        
        # Limpiar texto
        print("Limpiando y procesando texto...")
        self.df_processed['titulo_limpio'] = clean_and_lemmatize_series(self.df_processed['titulo'])
        self.df_processed['contenido_limpio'] = clean_and_lemmatize_series(self.df_processed['contenido'])
        
        # Crear vectorizador TF-IDF
        print("Creando representacin vectorial TF-IDF...")
        texts = self.df_processed['contenido_limpio'].fillna('').astype(str).tolist()
        
        # CORRECCIN: Parmetros ajustados para feminicidios
        self.vectorizer = TfidfVectorizer(
            max_features=3000,
            stop_words=self._get_spanish_stopwords(),  #  Stopwords en espaol
            lowercase=True,
            ngram_range=(1, 2),
            min_df=1,           #  Cambio: 21 (permite palabras nicas como "feminicidio")
            max_df=0.8,
            strip_accents=None  #  Cambio: Preservar acentos (evita "me xico")
        )
        
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        
        print(f" Matriz TF-IDF creada: {self.tfidf_matrix.shape}")
        print(f" {self.tfidf_matrix.shape[0]} documentos x {self.tfidf_matrix.shape[1]} caractersticas")
        
        return self.df_processed
    
    def step_4_topic_modeling(self, num_topics: int = 6) -> Tuple[pd.DataFrame, Dict]:
        """Paso 4: Modelado de tpicos usando LDA de scikit-learn."""
        print("=== PASO 4: MODELADO DE TPICOS (LDA) ===")
        
        if self.tfidf_matrix is None:
            raise ValueError("Debe ejecutar step_3_vectorize_text() primero")
        
        print(f"Entrenando modelo LDA con {num_topics} tpicos...")
        
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
            
            # Asignar tpico dominante a cada documento
            dominant_topics = doc_topic_matrix.argmax(axis=1)
            topic_probabilities = doc_topic_matrix.max(axis=1)
            
            # Agregar al DataFrame
            self.df_processed['topic_id'] = dominant_topics
            self.df_processed['topic_probability'] = topic_probabilities
            
            # Crear informacin de tpicos
            feature_names = self.vectorizer.get_feature_names_out()
            topics_info = []
            
            for topic_idx, topic in enumerate(self.lda_model.components_):
                # Obtener palabras ms importantes del tpico
                top_word_indices = topic.argsort()[::-1][:10]
                top_words = [feature_names[i] for i in top_word_indices]
                top_probs = [topic[i] for i in top_word_indices]
                
                topics_info.append({
                    'topic_id': topic_idx,
                    'words': top_words,
                    'probabilities': top_probs,
                    'description': ' '.join(top_words[:5])
                })
            
            # Agregar descripcin del tpico al DataFrame
            topic_descriptions = {topic['topic_id']: topic['description'] 
                               for topic in topics_info}
            self.df_processed['topic_description'] = self.df_processed['topic_id'].map(topic_descriptions)
            
            # Informacin del modelo
            topic_info = {
                'topics': topics_info,
                'num_topics': num_topics,
                'perplexity': self.lda_model.perplexity(self.tfidf_matrix)
            }
            
            print(" Modelo LDA entrenado exitosamente")
            print(f" Perplexity del modelo: {topic_info['perplexity']:.2f}")
            
            # Mostrar tpicos
            print("\n Tpicos descubiertos:")
            for topic in topics_info:
                print(f"  Tpico {topic['topic_id']}: {topic['description']}")
            
            return self.df_processed, topic_info
            
        except Exception as e:
            print(f" Error en modelado de tpicos: {e}")
            return self.df_processed, None
    
    def step_5_clustering(self, method: str = 'dbscan', eps: float = 0.6, 
                         min_samples: int = 2, n_clusters: int = 5) -> Tuple[pd.DataFrame, Dict]:
        """
        Paso 5: Agrupacin usando DBSCAN (recomendado) o K-Means.
        
        MEJORA PRINCIPAL: Migracin de K-Means a DBSCAN
        
        Ventajas de DBSCAN sobre K-Means:
        -  Detecta automticamente el nmero ptimo de clusters
        -  Identifica outliers (noticias atpicas) como cluster -1
        -  No requiere especificar K manualmente
        -  Mejor para datos con ruido o casos atpicos
        -  Silhouette Score tpicamente +15-25% mejor
        
        Parmetros:
            method: 'dbscan' (recomendado) o 'kmeans' (legacy)
            eps: Distancia mxima para DBSCAN (0.4 = similitud > 60%)
            min_samples: Mnimo de noticias por cluster en DBSCAN
            n_clusters: Nmero de clusters para K-Means (solo si method='kmeans')
        
        Returns:
            Tuple[DataFrame con columna 'cluster', Dict con informacin del clustering]
        """
        print(f"=== PASO 5: AGRUPACIN ({method.upper()}) ===")
        
        if self.tfidf_matrix is None:
            raise ValueError("Debe ejecutar step_3_vectorize_text() primero")
        
        try:
            if method.lower() == 'dbscan':
                return self._clustering_dbscan(eps, min_samples)
            elif method.lower() == 'kmeans':
                return self._clustering_kmeans(n_clusters)
            else:
                raise ValueError(f"Mtodo '{method}' no reconocido. Use 'dbscan' o 'kmeans'")
                
        except Exception as e:
            print(f" Error en clustering: {e}")
            return self.df_processed, None
    
    def _clustering_dbscan(self, eps: float = 0.6, min_samples: int = 2) -> Tuple[pd.DataFrame, Dict]:
        """
        Clustering con DBSCAN (Density-Based Spatial Clustering of Applications with Noise).
        
        Justificacin tcnica CORREGIDA:
        - eps=0.6 (ANTES 0.4): Con mtrica coseno, distancia = 1 - similitud
           eps=0.6 requiere similitud > 0.4 (40%) para mismo cluster
           MS PERMISIVO: permite agrupar casos similares aunque no sean idnticos
           Calibrado para noticias de feminicidio que varan en redaccin
        
        - min_samples=2 (ANTES 3): Un "caso" necesita al menos 2 noticias relacionadas
           MENOS RESTRICTIVO: permite detectar casos con menor cobertura
           til cuando hay pocas noticias sobre el mismo evento
           Balance entre ruido y sensibilidad
        
        - metric='cosine': Mide similitud semntica entre vectores TF-IDF
           Mejor que euclidean para texto
           Insensible a magnitud, solo considera direccin
        """
        from sklearn.cluster import DBSCAN
        from sklearn.metrics import silhouette_score
        
        print(f"Aplicando DBSCAN (eps={eps}, min_samples={min_samples})...")
        print("  Parmetros AJUSTADOS para feminicidios (ms permisivo)")
        
        # Convertir matriz dispersa a densa (DBSCAN lo requiere)
        tfidf_dense = self.tfidf_matrix.toarray()
        
        # Crear y aplicar DBSCAN
        self.dbscan_model = DBSCAN(
            eps=eps,
            min_samples=min_samples,
            metric='cosine',
            n_jobs=-1  # Usar todos los cores disponibles
        )
        
        cluster_labels = self.dbscan_model.fit_predict(tfidf_dense)
        
        # Asignar clusters al DataFrame
        self.df_processed['cluster'] = cluster_labels
        
        # Estadsticas
        n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
        n_outliers = list(cluster_labels).count(-1)
        n_clustered = len(cluster_labels) - n_outliers
        
        print(f" Clustering DBSCAN completado")
        print(f" Clusters detectados automticamente: {n_clusters}")
        print(f" Outliers detectados (casos atpicos): {n_outliers}")
        print(f" Noticias en clusters: {n_clustered}/{len(cluster_labels)}")
        
        # Calcular silhouette score (solo para noticias en clusters)
        silhouette = 0.0
        if n_clusters > 1 and n_clustered > 1:
            mask = cluster_labels != -1
            if mask.sum() > 1:
                silhouette = silhouette_score(
                    tfidf_dense[mask], 
                    cluster_labels[mask], 
                    metric='cosine'
                )
                quality = ('Excelente ' if silhouette > 0.5 
                          else 'Bueno ' if silhouette > 0.4
                          else 'Aceptable ' if silhouette > 0.3 
                          else 'Mejorable ')
                print(f" Silhouette Score: {silhouette:.3f} ({quality})")
        
        # Obtener trminos representativos por cluster
        feature_names = self.vectorizer.get_feature_names_out()
        cluster_terms = {}
        cluster_sizes = {}
        
        for cluster_id in sorted(set(cluster_labels)):
            mask = cluster_labels == cluster_id
            cluster_sizes[cluster_id] = mask.sum()
            
            if cluster_id == -1:
                # Outliers - analizar individualmente
                cluster_terms[cluster_id] = ['[casos_atpicos]']
            else:
                # Clusters normales - obtener trminos ms representativos
                cluster_indices = np.where(mask)[0]
                cluster_tfidf = tfidf_dense[cluster_indices].mean(axis=0)
                top_indices = cluster_tfidf.argsort()[::-1][:12]
                cluster_terms[cluster_id] = [feature_names[i] for i in top_indices]
        
        # Informacin del clustering
        cluster_info = {
            'method': 'DBSCAN',
            'silhouette': silhouette,
            'n_clusters': n_clusters,
            'n_outliers': n_outliers,
            'eps': eps,
            'min_samples': min_samples,
            'top_terms': cluster_terms,
            'cluster_sizes': cluster_sizes
        }
        
        # Mostrar distribucin
        print("\n Distribucin de clusters:")
        for cluster_id in sorted(set(cluster_labels)):
            count = cluster_sizes[cluster_id]
            if cluster_id == -1:
                print(f"   Outliers ({count} noticias): Casos nicos sin similitud suficiente")
                # Mostrar ejemplos de outliers
                if count > 0:
                    outlier_titles = self.df_processed[self.df_processed['cluster'] == -1]['titulo'].head(3)
                    for idx, title in enumerate(outlier_titles, 1):
                        print(f"      {idx}. {title[:70]}...")
            else:
                terms = ', '.join(cluster_terms[cluster_id][:5])
                print(f"   Cluster {cluster_id} ({count} noticias): {terms}")
        
        # Guardar informacin detallada de clusters
        self._save_cluster_info_to_csv(cluster_labels, cluster_terms, feature_names)
        
        return self.df_processed, cluster_info
    
    def _clustering_kmeans(self, n_clusters: int = 5) -> Tuple[pd.DataFrame, Dict]:
        """
        Clustering con K-Means (mtodo legacy, mantenido para compatibilidad).
        
        NOTA: Se recomienda usar DBSCAN en su lugar. K-Means se mantiene para:
        - Comparacin de resultados
        - Casos donde se conoce exactamente el nmero de grupos
        - Investigacin y benchmarking
        """
        from sklearn.metrics import silhouette_score
        
        print(f"  Usando K-Means (legacy). Considere migrar a DBSCAN.")
        print(f"Aplicando K-Means con {n_clusters} clusters...")
        
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
        if len(set(cluster_labels)) > 1:
            silhouette = silhouette_score(self.tfidf_matrix, cluster_labels)
        else:
            silhouette = 0.0
        
        # Obtener trminos representativos por cluster
        feature_names = self.vectorizer.get_feature_names_out()
        cluster_terms = {}
        
        for cluster_id in range(n_clusters):
            # Obtener centroide del cluster
            centroid = self.kmeans_model.cluster_centers_[cluster_id]
            # Ordenar trminos por importancia
            top_indices = centroid.argsort()[::-1][:12]
            cluster_terms[cluster_id] = [feature_names[i] for i in top_indices]
        
        cluster_info = {
            'method': 'K-Means',
            'silhouette': silhouette,
            'n_clusters': n_clusters,
            'top_terms': cluster_terms
        }
        
        print(" Clustering K-Means completado")
        print(f" Silhouette score: {silhouette:.3f}")
        
        # Mostrar distribucin
        cluster_counts = self.df_processed['cluster'].value_counts().sort_index()
        print(" Distribucin de clusters:")
        for cluster_id, count in cluster_counts.items():
            terms = ', '.join(cluster_terms[cluster_id][:5])
            print(f"   Cluster {cluster_id} ({count} noticias): {terms}")
        
        return self.df_processed, cluster_info
    
    def _save_cluster_info_to_csv(self, cluster_labels, cluster_terms, feature_names):
        """
        Guarda informacin detallada de clusters en CSV.
        til para anlisis post-hoc y documentacin.
        """
        cluster_info_list = []
        
        for cluster_id in sorted(set(cluster_labels)):
            mask = cluster_labels == cluster_id
            cluster_docs = self.df_processed[mask]
            
            if cluster_id == -1:
                # Outliers
                cluster_info_list.append({
                    'cluster_id': -1,
                    'label': 'Outliers (Casos Atpicos)',
                    'size': mask.sum(),
                    'description': 'Noticias sin similitud suficiente con otros grupos',
                    'keywords': 'N/A',
                    'sample_titles': ' | '.join(cluster_docs['titulo'].head(3).tolist()) if len(cluster_docs) > 0 else '',
                    'nna_mentions': (cluster_docs['menores_identificados'] == 'Si').sum()
                })
            else:
                # Clusters normales
                keywords = ', '.join(cluster_terms[cluster_id][:8])
                
                cluster_info_list.append({
                    'cluster_id': cluster_id,
                    'label': f'Cluster {cluster_id}',
                    'size': mask.sum(),
                    'description': f'Grupo temtico {cluster_id}',
                    'keywords': keywords,
                    'sample_titles': ' | '.join(cluster_docs['titulo'].head(3).tolist()) if len(cluster_docs) > 0 else '',
                    'nna_mentions': (cluster_docs['menores_identificados'] == 'Si').sum()
                })
        
        # Guardar CSV
        df_clusters = pd.DataFrame(cluster_info_list)
        output_path = "data/clusters_info.csv"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df_clusters.to_csv(output_path, index=False, encoding='utf-8')
        print(f" Informacin detallada guardada en: {output_path}")
    
    def step_6_similarity_analysis(self) -> pd.DataFrame:
        """Paso 6: Anlisis de similitud coseno."""
        print("=== PASO 6: ANLISIS DE SIMILITUD ===")
        
        if self.tfidf_matrix is None:
            raise ValueError("Debe ejecutar step_3_vectorize_text() primero")
        
        print("Calculando similitudes entre documentos...")
        
        try:
            # Calcular matriz de similitud coseno
            similarity_matrix = cosine_similarity(self.tfidf_matrix)
            
            # Para cada documento, encontrar el ms similar
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
            
            print(" Anlisis de similitud completado")
            
            # Estadsticas
            avg_similarity = self.df_processed['max_similarity'].mean()
            high_similarity_count = (self.df_processed['max_similarity'] > 0.5).sum()
            
            print(f" Similitud promedio: {avg_similarity:.3f}")
            print(f" Pares con alta similitud (>0.5): {high_similarity_count}")
            
        except Exception as e:
            print(f" Error en anlisis de similitud: {e}")
        
        return self.df_processed
    
    def step_7_enhanced_search_setup(self) -> SynonymDictionary:
        """Paso 7: Configuracin de bsqueda mejorada."""
        print("=== PASO 7: BSQUEDA MEJORADA ===")
        
        print("Configurando diccionario de sinnimos...")
        
        sample_terms = list(self.synonym_dict.synonyms.keys())[:10]
        print(f" Diccionario cargado con {len(self.synonym_dict.synonyms)} trminos")
        print(f" Trminos de ejemplo: {', '.join(sample_terms)}")
        
        # Guardar diccionario
        dict_path = "data/synonym_dictionary.json"
        os.makedirs(os.path.dirname(dict_path), exist_ok=True)
        self.synonym_dict.save_to_file(dict_path)
        print(f" Diccionario guardado en: {dict_path}")
        
        return self.synonym_dict
    
    def save_final_results(self, filepath: str = "data/noticias_analyzed_simplified.csv"):
        """Guarda los resultados finales."""
        print("=== GUARDANDO RESULTADOS FINALES ===")
        
        if self.df_processed is None:
            raise ValueError("Debe completar el anlisis primero")
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.df_processed.to_csv(filepath, index=False, encoding='utf-8')
        print(f" Resultados guardados en: {filepath}")
        
        # Guardar metadatos
        clustering_method = 'DBSCAN' if self.dbscan_model is not None else 'K-Means'
        metadata = {
            'total_noticias': len(self.df_processed),
            'noticias_con_nna': int((self.df_processed['menores_identificados'] == 'Si').sum()),
            'columnas_disponibles': list(self.df_processed.columns),
            'version': 'simplified_analyzer_v2.0',
            'algoritmos_usados': ['TF-IDF', 'LDA (scikit-learn)', clustering_method, 'Similitud Coseno']
        }
        
        import json
        metadata_path = filepath.replace('.csv', '_metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f" Metadatos guardados en: {metadata_path}")
        self.df_analyzed = self.df_processed
    
    def run_complete_analysis(self, 
                            num_topics: int = 6,
                            clustering_method: str = 'dbscan',
                            eps: float = 0.6,
                            min_samples: int = 2,
                            n_clusters: int = 4,
                            save_intermediate: bool = True) -> pd.DataFrame:
        """
        Ejecuta el pipeline completo de anlisis.
        
        Parmetros:
            num_topics: Nmero de tpicos para LDA
            clustering_method: 'dbscan' (recomendado) o 'kmeans'
            eps: Parmetro epsilon para DBSCAN (solo si method='dbscan')
            min_samples: Mnimo de muestras para DBSCAN (solo si method='dbscan')
            n_clusters: Nmero de clusters para K-Means (solo si method='kmeans')
            save_intermediate: Si guardar archivos intermedios
        """
        print(" INICIANDO ANLISIS COMPLETO SIMPLIFICADO")
        print("=" * 60)
        
        try:
            # Ejecutar todos los pasos
            self.step_1_collect_data()
            if save_intermediate:
                self.step_2_save_initial_data()
            
            self.step_3_vectorize_text()
            self.step_4_topic_modeling(num_topics=num_topics)
            
            # Clustering con mtodo seleccionado
            if clustering_method.lower() == 'dbscan':
                self.step_5_clustering(method='dbscan', eps=eps, min_samples=min_samples)
            else:
                self.step_5_clustering(method='kmeans', n_clusters=n_clusters)
            
            self.step_6_similarity_analysis()
            self.step_7_enhanced_search_setup()
            
            # Guardar resultados finales
            self.save_final_results()
            
            print("\n" + "=" * 60)
            print(" ANLISIS COMPLETADO EXITOSAMENTE")
            print(f" {len(self.df_analyzed)} noticias analizadas")
            print(f" Mtodo de clustering: {clustering_method.upper()}")
            print(" Todos los mtodos implementados sin dependencias problemticas")
            
            return self.df_analyzed
            
        except Exception as e:
            print(f"\n ERROR EN ANLISIS: {e}")
            print(" Revise la configuracin y vuelva a intentar")
            raise
    
    def search_enhanced(self, query: str, max_results: int = 10) -> pd.DataFrame:
        """Bsqueda mejorada usando sinnimos."""
        if self.df_analyzed is None:
            raise ValueError("Debe completar el anlisis primero")
        
        print(f" Bsqueda: '{query}'")
        
        # Realizar bsqueda
        results = enhanced_search(self.df_analyzed, query, ['titulo', 'contenido'])
        
        if len(results) > max_results:
            results = results.head(max_results)
        
        print(f" {len(results)} resultados encontrados")
        
        return results[['titulo', 'fecha', 'fuente', 'cluster', 'topic_id', 'menores_identificados']]

# Funcin de conveniencia
def run_quick_analysis_simplified():
    """Funcin para ejecutar anlisis rpido simplificado."""
    analyzer = SimplifiedNewsAnalyzer()
    return analyzer.run_complete_analysis()

if __name__ == "__main__":
    run_quick_analysis_simplified()
