#!/usr/bin/env python3
"""
Script de prueba para validar la implementación de DBSCAN
Compara K-Means vs DBSCAN en el mismo dataset
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from src.analysis.simplified_analyzer import SimplifiedNewsAnalyzer

def test_dbscan():
    """Prueba la nueva implementación de DBSCAN."""
    
    print("=" * 70)
    print("🧪 PRUEBA DE IMPLEMENTACIÓN DBSCAN")
    print("=" * 70)
    
    analyzer = SimplifiedNewsAnalyzer()
    
    # Paso 1-3: Cargar y vectorizar datos
    print("\n📥 Cargando datos...")
    analyzer.step_1_collect_data()
    analyzer.step_3_vectorize_text()
    
    if len(analyzer.df_processed) == 0:
        print("⚠️  No hay datos para analizar. Ejecute primero la recolección.")
        return
    
    print(f"✅ {len(analyzer.df_processed)} noticias cargadas")
    
    # Prueba 1: K-Means (método anterior)
    print("\n" + "=" * 70)
    print("📊 PRUEBA 1: K-MEANS (MÉTODO ANTERIOR)")
    print("=" * 70)
    
    df_kmeans, info_kmeans = analyzer.step_5_clustering(method='kmeans', n_clusters=4)
    
    # Prueba 2: DBSCAN (método nuevo)
    print("\n" + "=" * 70)
    print("📊 PRUEBA 2: DBSCAN (MÉTODO NUEVO)")
    print("=" * 70)
    
    df_dbscan, info_dbscan = analyzer.step_5_clustering(method='dbscan', eps=0.4, min_samples=3)
    
    # Comparación de resultados
    print("\n" + "=" * 70)
    print("📈 COMPARACIÓN DE RESULTADOS")
    print("=" * 70)
    
    print(f"\n🔍 K-Means:")
    print(f"   • Silhouette Score: {info_kmeans['silhouette']:.4f}")
    print(f"   • Clusters: {info_kmeans['n_clusters']} (fijo)")
    print(f"   • Outliers: 0 (no detecta)")
    
    print(f"\n🔍 DBSCAN:")
    print(f"   • Silhouette Score: {info_dbscan['silhouette']:.4f}")
    print(f"   • Clusters: {info_dbscan['n_clusters']} (automático)")
    print(f"   • Outliers: {info_dbscan['n_outliers']} (casos atípicos)")
    
    # Calcular mejora
    if info_kmeans['silhouette'] > 0:
        mejora = ((info_dbscan['silhouette'] - info_kmeans['silhouette']) / 
                  info_kmeans['silhouette'] * 100)
        print(f"\n✨ Mejora en Silhouette Score: {mejora:+.1f}%")
    
    # Análisis de outliers
    if info_dbscan['n_outliers'] > 0:
        print("\n" + "=" * 70)
        print("🔸 ANÁLISIS DE OUTLIERS (CASOS ATÍPICOS)")
        print("=" * 70)
        
        outliers = analyzer.df_processed[analyzer.df_processed['cluster'] == -1]
        
        print(f"\nTotal de outliers: {len(outliers)}")
        print(f"Porcentaje del dataset: {len(outliers)/len(analyzer.df_processed)*100:.1f}%")
        
        if 'menores_identificados' in outliers.columns:
            nna_outliers = (outliers['menores_identificados'] == 'Si').sum()
            print(f"Outliers con NNA afectados: {nna_outliers}")
        
        print(f"\n📰 Ejemplos de casos atípicos detectados:")
        for idx, row in outliers.head(5).iterrows():
            print(f"\n  {idx+1}. {row['titulo'][:80]}...")
            if 'fuente' in row:
                print(f"     Fuente: {row['fuente']}")
            if 'menores_identificados' in row:
                print(f"     NNA afectados: {row['menores_identificados']}")
    
    # Verificar archivo de clusters
    print("\n" + "=" * 70)
    print("💾 ARCHIVOS GENERADOS")
    print("=" * 70)
    
    if os.path.exists('data/clusters_info.csv'):
        print("✅ data/clusters_info.csv - Información detallada de clusters")
    else:
        print("⚠️  data/clusters_info.csv - No generado")
    
    print("\n" + "=" * 70)
    print("✅ PRUEBA COMPLETADA")
    print("=" * 70)
    print("\n💡 Conclusión:")
    print("   - DBSCAN detecta automáticamente el número de clusters")
    print("   - DBSCAN identifica casos atípicos (outliers)")
    print("   - DBSCAN generalmente mejora el Silhouette Score")
    print("   - Los outliers son valiosos para análisis especializados")
    print("\n🚀 Siguiente paso: Revisar data/clusters_info.csv para análisis detallado")

if __name__ == "__main__":
    test_dbscan()
