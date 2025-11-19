# tests/test_analyzer.py
# -*- coding: utf-8 -*-
"""
Tests para el módulo de análisis simplificado.
"""

import sys
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analysis.simplified_analyzer import SimplifiedNewsAnalyzer
import pandas as pd


def test_vectorization():
    """Prueba la vectorización TF-IDF."""
    print("\n" + "="*80)
    print("TEST: Vectorización TF-IDF")
    print("="*80)
    
    analyzer = SimplifiedNewsAnalyzer()
    
    # Recolectar datos
    print("\nRecolectando datos...")
    analyzer.step_1_collect_data()
    
    if analyzer.df_original is None or len(analyzer.df_original) == 0:
        print("⚠️  No hay datos para analizar")
        return
    
    # Vectorizar
    print("\nVectorizando texto...")
    analyzer.step_3_vectorize_text()
    
    print(f"\n✓ Vectorización exitosa")
    print(f"  Matriz TF-IDF: {analyzer.tfidf_matrix.shape}")
    print(f"  Documentos: {analyzer.tfidf_matrix.shape[0]}")
    print(f"  Features: {analyzer.tfidf_matrix.shape[1]}")


def test_topic_modeling():
    """Prueba el modelado de tópicos LDA."""
    print("\n" + "="*80)
    print("TEST: Modelado de Tópicos (LDA)")
    print("="*80)
    
    analyzer = SimplifiedNewsAnalyzer()
    
    # Pipeline hasta tópicos
    analyzer.step_1_collect_data()
    if analyzer.df_original is None or len(analyzer.df_original) == 0:
        print("⚠️  No hay datos para analizar")
        return
    
    analyzer.step_3_vectorize_text()
    
    print("\nEntrenando modelo LDA...")
    df_processed, topic_info = analyzer.step_4_topic_modeling(num_topics=6)
    
    if topic_info:
        print(f"\n✓ LDA exitoso")
        print(f"  Número de tópicos: {topic_info['num_topics']}")
        print(f"  Perplexity: {topic_info['perplexity']:.2f}")
        
        print("\nTópicos descubiertos:")
        for topic in topic_info['topics'][:3]:  # Mostrar solo 3
            print(f"  Tópico {topic['topic_id']}: {topic['description']}")


def test_clustering_dbscan():
    """Prueba clustering con DBSCAN."""
    print("\n" + "="*80)
    print("TEST: Clustering DBSCAN")
    print("="*80)
    
    analyzer = SimplifiedNewsAnalyzer()
    
    # Pipeline hasta clustering
    analyzer.step_1_collect_data()
    if analyzer.df_original is None or len(analyzer.df_original) == 0:
        print("⚠️  No hay datos para analizar")
        return
    
    analyzer.step_3_vectorize_text()
    
    print("\nAplicando DBSCAN...")
    df_processed, cluster_info = analyzer.step_5_clustering(
        method='dbscan',
        eps=0.6,
        min_samples=2
    )
    
    if cluster_info:
        print(f"\n✓ DBSCAN exitoso")
        print(f"  Método: {cluster_info['method']}")
        print(f"  Clusters detectados: {cluster_info['n_clusters']}")
        print(f"  Outliers: {cluster_info['n_outliers']}")
        print(f"  Silhouette Score: {cluster_info['silhouette']:.3f}")
        
        # Mostrar distribución
        print("\nDistribución de clusters:")
        for cluster_id, size in sorted(cluster_info['cluster_sizes'].items())[:5]:
            if cluster_id == -1:
                print(f"  Outliers: {size} noticias")
            else:
                terms = ', '.join(cluster_info['top_terms'][cluster_id][:3])
                print(f"  Cluster {cluster_id}: {size} noticias ({terms}...)")


def test_complete_analysis():
    """Prueba el análisis completo."""
    print("\n" + "="*80)
    print("TEST: Análisis Completo")
    print("="*80)
    
    analyzer = SimplifiedNewsAnalyzer()
    
    print("\nEjecutando pipeline completo...")
    df_analyzed = analyzer.run_complete_analysis(
        num_topics=6,
        clustering_method='dbscan',
        eps=0.6,
        min_samples=2,
        save_intermediate=False
    )
    
    if df_analyzed is not None and len(df_analyzed) > 0:
        print(f"\n✓ Análisis completo exitoso")
        print(f"  Total de noticias: {len(df_analyzed)}")
        
        # Estadísticas
        nna_count = (df_analyzed['menores_identificados'] == 'Si').sum()
        clusters = df_analyzed['cluster'].nunique()
        topics = df_analyzed['topic_id'].nunique()
        avg_similarity = df_analyzed['max_similarity'].mean()
        
        print(f"\nResultados:")
        print(f"  Noticias con NNA: {nna_count} ({nna_count/len(df_analyzed)*100:.1f}%)")
        print(f"  Clusters: {clusters}")
        print(f"  Tópicos: {topics}")
        print(f"  Similitud promedio: {avg_similarity:.3f}")
        
        # Mostrar ejemplo de noticia de alta similitud
        high_sim = df_analyzed[df_analyzed['max_similarity'] > 0.5]
        if len(high_sim) > 0:
            print(f"\nNoticias con alta similitud (>0.5): {len(high_sim)}")
    else:
        print("⚠️  El análisis no produjo resultados")


def main():
    """Ejecuta todos los tests de análisis."""
    print("\n" + "="*80)
    print(" SUITE DE PRUEBAS - ANÁLISIS ML")
    print(" Trabajo Terminal 1 - ESIME Zacatenco")
    print("="*80)
    
    try:
        test_vectorization()
        test_topic_modeling()
        test_clustering_dbscan()
        test_complete_analysis()
        
        print("\n" + "="*80)
        print("✓ TODOS LOS TESTS DE ANÁLISIS COMPLETADOS")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n✗ ERROR EN TESTS: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
