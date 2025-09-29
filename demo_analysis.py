# demo_analysis.py
"""
Script de demostración del análisis completo de noticias.
Ejecuta todos los pasos propuestos en el proceso de análisis.
"""

import os
import sys

# Agregar el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Función principal de demostración."""
    print("🚀 DEMO: Sistema Inteligente para Identificación y Seguimiento de NNA")
    print("=" * 80)
    
    try:
        # Importar el analizador completo
        from src.analysis.complete_analyzer import CompleteNewsAnalyzer
        
        # Crear instancia del analizador
        analyzer = CompleteNewsAnalyzer()
        
        print("📋 Este demo ejecutará los 7 pasos del análisis propuesto:")
        print("   1. Recolección de Datos (RSS)")
        print("   2. Almacenamiento Inicial (CSV)")
        print("   3. Representación Vectorial (TF-IDF)")
        print("   4. Modelado de Tópicos (LDA)")
        print("   5. Agrupación (K-Means)")
        print("   6. Análisis de Similitud (Coseno)")
        print("   7. Búsqueda Mejorada (Sinónimos)")
        print()
        
        input("Presione Enter para continuar...")
        
        # Ejecutar análisis completo
        df_results = analyzer.run_complete_analysis(
            num_topics=6,      # Número de tópicos para LDA
            n_clusters=4,      # Número de clusters para K-Means
            save_intermediate=True
        )
        
        print("\n" + "=" * 80)
        print("📊 RESUMEN DE RESULTADOS")
        print("=" * 80)
        
        if df_results is not None and len(df_results) > 0:
            # Mostrar estadísticas generales
            print(f"📰 Total de noticias analizadas: {len(df_results)}")
            
            # Estadísticas de NNA
            nna_count = (df_results['menores_identificados'] == 'Si').sum()
            print(f"🎯 Noticias con menciones a NNA: {nna_count} ({nna_count/len(df_results)*100:.1f}%)")
            
            # Estadísticas de clustering
            if 'cluster' in df_results.columns:
                n_clusters = df_results['cluster'].nunique()
                print(f"🔗 Clusters identificados: {n_clusters}")
                
                print("\n📋 Distribución por cluster:")
                cluster_counts = df_results['cluster'].value_counts().sort_index()
                for cluster_id, count in cluster_counts.items():
                    print(f"   Cluster {cluster_id}: {count} noticias")
            
            # Estadísticas de tópicos
            if 'topic_id' in df_results.columns:
                valid_topics = df_results[df_results['topic_id'] >= 0]
                if len(valid_topics) > 0:
                    n_topics = valid_topics['topic_id'].nunique()
                    print(f"📚 Tópicos identificados: {n_topics}")
                    
                    print("\n📋 Distribución por tópico:")
                    topic_counts = valid_topics['topic_id'].value_counts().sort_index()
                    for topic_id, count in topic_counts.items():
                        topic_desc = valid_topics[valid_topics['topic_id'] == topic_id]['topic_description'].iloc[0]
                        print(f"   Tópico {topic_id} ({topic_desc}): {count} noticias")
            
            # Mostrar algunas noticias de ejemplo
            print("\n📰 EJEMPLOS DE NOTICIAS ANALIZADAS")
            print("-" * 60)
            
            # Noticias con NNA
            nna_news = df_results[df_results['menores_identificados'] == 'Si'].head(3)
            if len(nna_news) > 0:
                print("🎯 Noticias con menciones a NNA:")
                for idx, row in nna_news.iterrows():
                    title = row['titulo'][:60] + "..." if len(row['titulo']) > 60 else row['titulo']
                    cluster = row.get('cluster', 'N/A')
                    topic = row.get('topic_id', 'N/A')
                    print(f"   • {title}")
                    print(f"     Cluster: {cluster} | Tópico: {topic}")
                print()
            
            # Demostrar búsqueda mejorada
            print("🔍 DEMOSTRACIÓN DE BÚSQUEDA MEJORADA")
            print("-" * 60)
            
            search_queries = ["feminicidio", "niños", "violencia", "justicia"]
            
            for query in search_queries:
                try:
                    results = analyzer.search_enhanced(query, max_results=3)
                    if len(results) > 0:
                        print(f"\n🔍 Búsqueda: '{query}'")
                        for idx, row in results.iterrows():
                            title = row['titulo'][:50] + "..." if len(row['titulo']) > 50 else row['titulo']
                            print(f"   • {title}")
                    else:
                        print(f"\n🔍 '{query}': Sin resultados")
                except Exception as e:
                    print(f"\n❌ Error en búsqueda '{query}': {e}")
        
        else:
            print("⚠️  No se pudieron analizar noticias. Verifique la configuración RSS.")
        
        print("\n" + "=" * 80)
        print("✅ DEMO COMPLETADO")
        print("📁 Los archivos de resultados se guardaron en el directorio 'data/'")
        print("💡 Puede usar estos resultados para desarrollo posterior")
        print("=" * 80)
        
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        print("\n💡 Soluciones sugeridas:")
        print("   1. Instale las dependencias: pip install -r requirements.txt")
        print("   2. Active su entorno virtual si está usando uno")
        print("   3. Verifique que está ejecutando desde el directorio correcto")
        
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        print(f"📍 Tipo de error: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        
        print("\n💡 Pasos para solucionar:")
        print("   1. Verifique la configuración en config.py")
        print("   2. Asegúrese de que los RSS feeds sean accesibles")
        print("   3. Revise que todas las dependencias estén instaladas")

def test_imports():
    """Función para probar las importaciones antes del demo completo."""
    print("🔧 VERIFICANDO DEPENDENCIAS...")
    
    missing_packages = []
    
    # Probar importaciones básicas
    try:
        import pandas
        print("✅ pandas")
    except ImportError:
        missing_packages.append("pandas")
        print("❌ pandas")
    
    try:
        import numpy
        print("✅ numpy")
    except ImportError:
        missing_packages.append("numpy")
        print("❌ numpy")
    
    try:
        import sklearn
        print("✅ scikit-learn")
    except ImportError:
        missing_packages.append("scikit-learn")
        print("❌ scikit-learn")
    
    try:
        import gensim
        print("✅ gensim")
    except ImportError:
        missing_packages.append("gensim")
        print("❌ gensim")
    
    try:
        import requests
        print("✅ requests")
    except ImportError:
        missing_packages.append("requests")
        print("❌ requests")
    
    try:
        from bs4 import BeautifulSoup
        print("✅ beautifulsoup4")
    except ImportError:
        missing_packages.append("beautifulsoup4")
        print("❌ beautifulsoup4")
    
    if missing_packages:
        print(f"\n⚠️  Paquetes faltantes: {', '.join(missing_packages)}")
        print("🔧 Instale con: pip install " + " ".join(missing_packages))
        return False
    else:
        print("\n✅ Todas las dependencias están disponibles")
        return True

if __name__ == "__main__":
    print("Sistema Inteligente para la Identificación y Seguimiento de NNA")
    print("Prototipo de Análisis de Datos - Demo")
    print()
    
    # Verificar dependencias primero
    if test_imports():
        print()
        main()
    else:
        print("\n❌ No se puede ejecutar el demo debido a dependencias faltantes")
        print("💡 Ejecute: pip install -r requirements.txt")