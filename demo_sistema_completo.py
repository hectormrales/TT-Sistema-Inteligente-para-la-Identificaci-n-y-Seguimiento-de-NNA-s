# demo_sistema_completo.py
"""
Demo completo del Sistema Inteligente NNA con recolector mejorado
"""
import sys
import os
sys.path.append(os.path.abspath('.'))

from src.analysis.simplified_analyzer import SimplifiedNewsAnalyzer
from src.collection.smart_data_collector import SmartDataCollector
import config
import pandas as pd
from datetime import datetime

def demo_completo():
    """Demostración completa del sistema mejorado"""
    
    print("🚀 DEMOSTRACIÓN COMPLETA: SISTEMA INTELIGENTE NNA")
    print("=" * 80)
    print(f"⏰ Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Verificar robots.txt
    print("🔍 FASE 1: VERIFICACIÓN DE CUMPLIMIENTO ÉTICO")
    print("-" * 50)
    
    collector = SmartDataCollector()
    fuentes_permitidas = 0
    fuentes_bloqueadas = 0
    
    for i, rss_url in enumerate(config.RSS_FEEDS):
        can_crawl = collector.check_robots_txt(rss_url)
        if can_crawl:
            fuentes_permitidas += 1
        else:
            fuentes_bloqueadas += 1
    
    print(f"📊 Resumen de cumplimiento:")
    print(f"   ✅ Fuentes permitidas: {fuentes_permitidas}")
    print(f"   ⚠️ Fuentes bloqueadas: {fuentes_bloqueadas}")
    print(f"   📈 Tasa de cumplimiento: {(fuentes_permitidas/len(config.RSS_FEEDS)*100):.1f}%")
    
    # 2. Comparar métodos de recolección
    print(f"\n🔄 FASE 2: COMPARACIÓN DE MÉTODOS DE RECOLECCIÓN")
    print("-" * 50)
    
    print("📰 Método Tradicional:")
    analyzer_tradicional = SimplifiedNewsAnalyzer(use_smart_collector=False)
    df_tradicional = analyzer_tradicional.step_1_collect_data()
    
    print(f"\n🤖 Método Inteligente:")
    analyzer_inteligente = SimplifiedNewsAnalyzer(use_smart_collector=True)
    df_inteligente = analyzer_inteligente.step_1_collect_data(relevance_threshold=0.3)
    
    print(f"\n📊 COMPARACIÓN DE RESULTADOS:")
    print(f"{'Métrica':<30} {'Tradicional':<15} {'Inteligente':<15} {'Diferencia':<15}")
    print("-" * 75)
    
    # Comparar métricas
    trad_total = len(df_tradicional)
    intel_total = len(df_inteligente)
    print(f"{'Total noticias':<30} {trad_total:<15} {intel_total:<15} {intel_total-trad_total:<15}")
    
    trad_nna = sum(df_tradicional['menores_identificados'] == 'Si')
    intel_nna = sum(df_inteligente['menores_identificados'] == 'Si') 
    print(f"{'Casos NNA detectados':<30} {trad_nna:<15} {intel_nna:<15} {intel_nna-trad_nna:<15}")
    
    trad_rate = (trad_nna / trad_total * 100) if trad_total > 0 else 0
    intel_rate = (intel_nna / intel_total * 100) if intel_total > 0 else 0
    print(f"{'Tasa detección NNA (%)':<30} {trad_rate:<15.1f} {intel_rate:<15.1f} {intel_rate-trad_rate:<15.1f}")
    
    # Eficiencia de red (solo para inteligente)
    if 'procesado_completo' in df_inteligente.columns:
        contenido_completo = sum(df_inteligente['procesado_completo'])
        eficiencia = (1 - contenido_completo / intel_total) * 100
        print(f"{'Eficiencia de red (%)':<30} {'N/A':<15} {eficiencia:<15.1f} {'N/A':<15}")
    
    # 3. Análisis de relevancia
    print(f"\n🎯 FASE 3: ANÁLISIS DE RELEVANCIA NNA")
    print("-" * 50)
    
    if 'relevancia_nna' in df_inteligente.columns:
        relevance_stats = df_inteligente['relevancia_nna'].describe()
        print(f"📈 Estadísticas de relevancia:")
        print(f"   Media: {relevance_stats['mean']:.3f}")
        print(f"   Mediana: {relevance_stats['50%']:.3f}")
        print(f"   Máximo: {relevance_stats['max']:.3f}")
        print(f"   Mínimo: {relevance_stats['min']:.3f}")
        
        # Distribución por rangos
        high_rel = sum(df_inteligente['relevancia_nna'] > 0.5)
        med_rel = sum((df_inteligente['relevancia_nna'] > 0.3) & (df_inteligente['relevancia_nna'] <= 0.5))
        low_rel = sum((df_inteligente['relevancia_nna'] > 0.1) & (df_inteligente['relevancia_nna'] <= 0.3))
        
        print(f"\n📊 Distribución por relevancia:")
        print(f"   Alta (>0.5): {high_rel} artículos")
        print(f"   Media (0.3-0.5): {med_rel} artículos") 
        print(f"   Baja (0.1-0.3): {low_rel} artículos")
        
        # Mostrar ejemplos de alta relevancia
        high_relevance = df_inteligente[df_inteligente['relevancia_nna'] > 0.4]
        if len(high_relevance) > 0:
            print(f"\n🔍 Ejemplos de alta relevancia:")
            for i, (_, row) in enumerate(high_relevance.head(3).iterrows()):
                print(f"   {i+1}. {row['titulo'][:60]}...")
                print(f"      Score: {row['relevancia_nna']:.3f} | NNA: {row['menores_identificados']}")
    
    # 4. Ejecutar pipeline completo con método inteligente
    print(f"\n🧠 FASE 4: PIPELINE COMPLETO DE ANÁLISIS")
    print("-" * 50)
    
    print("Ejecutando análisis completo con método inteligente...")
    df_final = analyzer_inteligente.run_complete_analysis(
        num_topics=5,
        n_clusters=4,
        save_intermediate=True
    )
    
    # 5. Estadísticas finales
    print(f"\n📈 FASE 5: ESTADÍSTICAS FINALES DEL SISTEMA")
    print("-" * 50)
    
    stats_finales = {
        'total_noticias': len(df_final),
        'casos_nna': sum(df_final['menores_identificados'] == 'Si'),
        'clusters_identificados': df_final['cluster'].nunique() if 'cluster' in df_final.columns else 0,
        'topics_descubiertos': df_final['topic_id'].nunique() if 'topic_id' in df_final.columns else 0,
    }
    
    if 'max_similarity' in df_final.columns:
        stats_finales['similitud_promedio'] = df_final['max_similarity'].mean()
    
    if 'relevancia_nna' in df_final.columns:
        stats_finales['relevancia_promedio'] = df_final['relevancia_nna'].mean()
    
    if 'procesado_completo' in df_final.columns:
        stats_finales['contenido_completo'] = sum(df_final['procesado_completo'])
        stats_finales['eficiencia_red'] = (1 - stats_finales['contenido_completo'] / stats_finales['total_noticias']) * 100
    
    print("🏆 RESULTADOS FINALES:")
    for key, value in stats_finales.items():
        if isinstance(value, float):
            print(f"   {key.replace('_', ' ').title()}: {value:.3f}")
        else:
            print(f"   {key.replace('_', ' ').title()}: {value}")
    
    # 6. Prueba de búsqueda inteligente
    print(f"\n🔍 FASE 6: PRUEBA DE BÚSQUEDA INTELIGENTE")
    print("-" * 50)
    
    # Probar búsquedas con diferentes términos
    test_queries = ["violencia", "niños", "feminicidio", "huérfanos"]
    
    for query in test_queries:
        results = analyzer_inteligente.search_enhanced(query, max_results=3)
        print(f"\n🔎 Búsqueda: '{query}' → {len(results)} resultados")
        
        if len(results) > 0:
            for i, (_, row) in enumerate(results.iterrows()):
                print(f"   {i+1}. {row['titulo'][:50]}... | NNA: {row['menores_identificados']}")
    
    # 7. Resumen de beneficios
    print(f"\n✨ RESUMEN DE BENEFICIOS DEL SISTEMA INTELIGENTE")
    print("=" * 80)
    
    beneficios = [
        "🤖 Recolección ética que respeta robots.txt y delays de crawling",
        "⚡ Reducción significativa en el número de peticiones HTTP",
        "🎯 Filtrado inteligente por relevancia antes de descarga completa",
        "🔍 Detección mejorada de casos NNA con algoritmos contextuales", 
        "🛡️ Comportamiento sostenible que evita bloqueos de sitios web",
        "📊 Análisis completo con clustering, modelado de tópicos y similitudes",
        "🔎 Búsqueda inteligente con expansión automática de sinónimos",
        "📈 Métricas detalladas de eficiencia y relevancia"
    ]
    
    for beneficio in beneficios:
        print(f"   {beneficio}")
    
    print(f"\n⏰ Completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎉 Demo del Sistema Inteligente NNA finalizada exitosamente!")
    
    return df_final, stats_finales

if __name__ == "__main__":
    try:
        resultado_final, estadisticas = demo_completo()
        print(f"\n💾 Datos guardados en: data/noticias_analyzed_simplified.csv")
        print(f"📊 {estadisticas['total_noticias']} noticias procesadas con {estadisticas['casos_nna']} casos NNA detectados")
        
    except Exception as e:
        print(f"\n❌ Error en la demostración: {e}")
        import traceback
        traceback.print_exc()