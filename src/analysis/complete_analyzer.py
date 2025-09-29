# src/analysis/complete_analyzer.py
"""
Analizador completo que integra todos los métodos propuestos:
1. Recolección RSS
2. Almacenamiento CSV  
3. Representación vectorial (TF-IDF)
4. Modelado de tópicos (LDA)
5. Clustering (K-Means)
6. Análisis de similitud (Similitud coseno)
7. Búsqueda mejorada (Diccionario de sinónimos)
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
from src.analysis.topic_analyzer import analyze_topics_in_dataframe, calculate_document_similarities
from src.analysis.synonym_dictionary import SynonymDictionary, enhanced_search

class CompleteNewsAnalyzer:
    """
    Clase principal que orquesta todo el análisis de noticias.
    Implementa el pipeline completo propuesto.
    """
    
    def __init__(self):
        self.df_original = None
        self.df_processed = None
        self.df_analyzed = None
        self.cluster_info = None
        self.topic_info = None
        self.synonym_dict = SynonymDictionary()
        
    def step_1_collect_data(self) -> pd.DataFrame:
        """
        Paso 1: Recolección de datos desde RSS feeds.
        
        Returns:
            DataFrame con noticias recolectadas
        """
        print("=== PASO 1: RECOLECCIÓN DE DATOS ===")
        print("Recolectando noticias desde feeds RSS...")
        
        self.df_original = collect_all_news()
        
        if len(self.df_original) == 0:
            print("⚠️  No se recolectaron noticias. Verifique la configuración de RSS.")
            return self.df_original
        
        print(f"✅ {len(self.df_original)} noticias recolectadas")
        print(f"📊 Columnas disponibles: {list(self.df_original.columns)}")
        
        # Detectar menciones a NNA
        print("Detectando menciones a NNA...")
        self.df_original['menores_identificados'] = self.df_original['contenido'].apply(detect_children_mentions)
        nna_count = (self.df_original['menores_identificados'] == 'Si').sum()
        print(f"🎯 {nna_count} noticias con menciones a NNA detectadas")
        
        return self.df_original
    
    def step_2_save_initial_data(self, filepath: str = "data/noticias_raw.csv"):
        """
        Paso 2: Almacenamiento inicial en CSV.
        
        Args:
            filepath: Ruta donde guardar el CSV
        """
        print("=== PASO 2: ALMACENAMIENTO INICIAL ===")
        
        if self.df_original is None:
            raise ValueError("Debe ejecutar step_1_collect_data() primero")
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Guardar datos raw
        self.df_original.to_csv(filepath, index=False, encoding='utf-8')
        print(f"✅ Datos guardados en: {filepath}")
        
        # Mostrar estadísticas básicas
        print(f"📊 Total de noticias: {len(self.df_original)}")
        print(f"🎯 Con menciones a NNA: {(self.df_original['menores_identificados'] == 'Si').sum()}")
        print(f"📅 Rango de fechas: {self.df_original['fecha'].min()} a {self.df_original['fecha'].max()}")
    
    def step_3_vectorize_text(self) -> pd.DataFrame:
        """
        Paso 3: Representación vectorial - Convertir texto a matriz TF-IDF.
        
        Returns:
            DataFrame con texto limpio y procesado
        """
        print("=== PASO 3: REPRESENTACIÓN VECTORIAL ===")
        
        if self.df_original is None:
            raise ValueError("Debe ejecutar step_1_collect_data() primero")
        
        self.df_processed = self.df_original.copy()
        
        # Limpiar y procesar texto
        print("Limpiando y procesando texto...")
        self.df_processed['titulo_limpio'] = clean_and_lemmatize_series(self.df_processed['titulo'])
        self.df_processed['contenido_limpio'] = clean_and_lemmatize_series(self.df_processed['contenido'])
        
        print("✅ Texto limpio y normalizado")
        print("🔤 Vectorización TF-IDF será aplicada en los siguientes pasos")
        
        return self.df_processed
    
    def step_4_topic_modeling(self, num_topics: int = 8) -> Tuple[pd.DataFrame, Dict]:
        """
        Paso 4: Modelado de tópicos usando LDA.
        
        Args:
            num_topics: Número de tópicos a descubrir
            
        Returns:
            Tupla con DataFrame actualizado e información de tópicos
        """
        print("=== PASO 4: MODELADO DE TÓPICOS (LDA) ===")
        
        if self.df_processed is None:
            raise ValueError("Debe ejecutar step_3_vectorize_text() primero")
        
        print(f"Entrenando modelo LDA con {num_topics} tópicos...")
        
        try:
            self.df_processed, self.topic_info = analyze_topics_in_dataframe(
                self.df_processed, 
                text_column='contenido_limpio',
                num_topics=num_topics
            )
            
            print("✅ Modelo LDA entrenado exitosamente")
            print(f"📈 Coherencia del modelo: {self.topic_info['coherence']:.3f}")
            
            # Mostrar tópicos descubiertos
            print("\n🔍 Tópicos descubiertos:")
            for topic in self.topic_info['topics']:
                print(f"  Tópico {topic['topic_id']}: {topic['description']}")
            
            # Estadísticas de distribución de tópicos
            topic_counts = self.df_processed['topic_id'].value_counts().sort_index()
            print(f"\n📊 Distribución de noticias por tópico:")
            for topic_id, count in topic_counts.items():
                if topic_id >= 0:  # Excluir tópicos no asignados (-1)
                    topic_desc = self.topic_info['topics'][topic_id]['description']
                    print(f"  Tópico {topic_id} ({topic_desc}): {count} noticias")
            
        except Exception as e:
            print(f"❌ Error en modelado de tópicos: {e}")
            print("⚠️  Continuando sin análisis de tópicos...")
            self.topic_info = None
        
        return self.df_processed, self.topic_info
    
    def step_5_clustering(self, n_clusters: int = 5) -> Tuple[pd.DataFrame, Dict]:
        """
        Paso 5: Agrupación usando K-Means clustering.
        
        Args:
            n_clusters: Número de clusters
            
        Returns:
            Tupla con DataFrame actualizado e información de clusters
        """
        print("=== PASO 5: AGRUPACIÓN (K-MEANS CLUSTERING) ===")
        
        if self.df_processed is None:
            raise ValueError("Debe ejecutar pasos anteriores primero")
        
        print(f"Aplicando K-Means con {n_clusters} clusters...")
        
        self.df_processed, self.cluster_info = cluster_dataframe(
            self.df_processed,
            n_clusters=n_clusters,
            max_features=3000
        )
        
        print("✅ Clustering completado")
        print(f"📈 Silhouette score: {self.cluster_info['silhouette']:.3f}")
        
        # Mostrar información de clusters
        print(f"\n🔍 Términos principales por cluster:")
        for cluster_id, terms in self.cluster_info['top_terms'].items():
            count = (self.df_processed['cluster'] == cluster_id).sum()
            print(f"  Cluster {cluster_id} ({count} noticias): {', '.join(terms[:5])}")
        
        return self.df_processed, self.cluster_info
    
    def step_6_similarity_analysis(self) -> pd.DataFrame:
        """
        Paso 6: Análisis de similitud usando similitud coseno.
        
        Returns:
            DataFrame con información de similitud
        """
        print("=== PASO 6: ANÁLISIS DE SIMILITUD ===")
        
        if self.df_processed is None:
            raise ValueError("Debe ejecutar pasos anteriores primero")
        
        print("Calculando similitudes entre documentos...")
        
        try:
            self.df_processed = calculate_document_similarities(
                self.df_processed, 
                text_column='contenido_limpio'
            )
            
            print("✅ Análisis de similitud completado")
            
            # Estadísticas de similitud
            avg_similarity = self.df_processed['max_similarity'].mean()
            max_similarity = self.df_processed['max_similarity'].max()
            high_similarity_count = (self.df_processed['max_similarity'] > 0.5).sum()
            
            print(f"📊 Similitud promedio: {avg_similarity:.3f}")
            print(f"📊 Similitud máxima: {max_similarity:.3f}")
            print(f"📊 Pares con alta similitud (>0.5): {high_similarity_count}")
            
        except Exception as e:
            print(f"❌ Error en análisis de similitud: {e}")
            print("⚠️  Continuando sin análisis de similitud...")
        
        return self.df_processed
    
    def step_7_enhanced_search_setup(self) -> SynonymDictionary:
        """
        Paso 7: Configuración de búsqueda mejorada con sinónimos.
        
        Returns:
            Diccionario de sinónimos configurado
        """
        print("=== PASO 7: BÚSQUEDA MEJORADA ===")
        
        print("Configurando diccionario de sinónimos...")
        
        # El diccionario ya viene pre-cargado con términos especializados
        sample_terms = list(self.synonym_dict.synonyms.keys())[:10]
        print(f"✅ Diccionario cargado con {len(self.synonym_dict.synonyms)} términos")
        print(f"🔤 Términos de ejemplo: {', '.join(sample_terms)}")
        
        # Guardar diccionario para uso futuro
        dict_path = "data/synonym_dictionary.json"
        os.makedirs(os.path.dirname(dict_path), exist_ok=True)
        self.synonym_dict.save_to_file(dict_path)
        print(f"💾 Diccionario guardado en: {dict_path}")
        
        return self.synonym_dict
    
    def save_final_results(self, filepath: str = "data/noticias_analyzed.csv"):
        """
        Guarda los resultados finales del análisis completo.
        
        Args:
            filepath: Ruta donde guardar el archivo final
        """
        print("=== GUARDANDO RESULTADOS FINALES ===")
        
        if self.df_processed is None:
            raise ValueError("Debe completar el análisis primero")
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Guardar DataFrame con todos los análisis
        self.df_processed.to_csv(filepath, index=False, encoding='utf-8')
        print(f"✅ Resultados guardados en: {filepath}")
        
        # Guardar metadatos del análisis
        metadata_path = filepath.replace('.csv', '_metadata.json')
        metadata = {
            'total_noticias': len(self.df_processed),
            'noticias_con_nna': int((self.df_processed['menores_identificados'] == 'Si').sum()),
            'num_clusters': self.cluster_info['n_clusters'] if self.cluster_info else 0,
            'silhouette_score': self.cluster_info['silhouette'] if self.cluster_info else 0,
            'num_topics': self.topic_info['num_topics'] if self.topic_info else 0,
            'topic_coherence': self.topic_info['coherence'] if self.topic_info else 0,
            'columnas_disponibles': list(self.df_processed.columns)
        }
        
        import json
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"📋 Metadatos guardados en: {metadata_path}")
        
        self.df_analyzed = self.df_processed
    
    def run_complete_analysis(self, 
                            num_topics: int = 8,
                            n_clusters: int = 5,
                            save_intermediate: bool = True) -> pd.DataFrame:
        """
        Ejecuta el pipeline completo de análisis.
        
        Args:
            num_topics: Número de tópicos para LDA
            n_clusters: Número de clusters para K-Means
            save_intermediate: Si guardar resultados intermedios
            
        Returns:
            DataFrame con todos los análisis aplicados
        """
        print("🚀 INICIANDO ANÁLISIS COMPLETO DE NOTICIAS")
        print("=" * 60)
        
        try:
            # Paso 1: Recolección
            self.step_1_collect_data()
            if save_intermediate:
                self.step_2_save_initial_data()
            
            # Paso 3: Procesamiento
            self.step_3_vectorize_text()
            
            # Paso 4: Tópicos
            self.step_4_topic_modeling(num_topics=num_topics)
            
            # Paso 5: Clustering  
            self.step_5_clustering(n_clusters=n_clusters)
            
            # Paso 6: Similitud
            self.step_6_similarity_analysis()
            
            # Paso 7: Sinónimos
            self.step_7_enhanced_search_setup()
            
            # Guardar resultados finales
            self.save_final_results()
            
            print("\n" + "=" * 60)
            print("🎉 ANÁLISIS COMPLETADO EXITOSAMENTE")
            print(f"📊 {len(self.df_analyzed)} noticias analizadas")
            print("✨ Todos los métodos propuestos han sido aplicados")
            
            return self.df_analyzed
            
        except Exception as e:
            print(f"\n❌ ERROR EN ANÁLISIS: {e}")
            print("💡 Revise la configuración y vuelva a intentar")
            raise
    
    def search_enhanced(self, query: str, max_results: int = 10) -> pd.DataFrame:
        """
        Búsqueda mejorada usando sinónimos.
        
        Args:
            query: Consulta de búsqueda
            max_results: Máximo número de resultados
            
        Returns:
            DataFrame con resultados de búsqueda
        """
        if self.df_analyzed is None:
            raise ValueError("Debe completar el análisis primero")
        
        print(f"🔍 Búsqueda: '{query}'")
        
        # Expandir consulta con sinónimos
        expanded_query = self.synonym_dict.expand_search_query(query)
        print(f"🔍 Expandida: '{expanded_query}'")
        
        # Realizar búsqueda
        results = enhanced_search(self.df_analyzed, query, ['titulo', 'contenido'])
        
        if len(results) > max_results:
            results = results.head(max_results)
        
        print(f"📋 {len(results)} resultados encontrados")
        
        return results[['titulo', 'fecha', 'fuente', 'cluster', 'topic_id', 'menores_identificados']]

# Función de conveniencia para uso rápido
def run_quick_analysis():
    """Función de conveniencia para ejecutar análisis rápido."""
    analyzer = CompleteNewsAnalyzer()
    return analyzer.run_complete_analysis()

if __name__ == "__main__":
    # Ejecutar análisis completo si se ejecuta directamente
    run_quick_analysis()