# test_smart_collector.py
"""
Script de prueba para el nuevo recolector inteligente de datos
"""
import sys
import os
sys.path.append(os.path.abspath('.'))

from src.analysis.simplified_analyzer import SimplifiedNewsAnalyzer
from src.collection.smart_data_collector import SmartDataCollector
import config

def test_robots_txt_check():
    """Prueba la verificación de robots.txt"""
    print("🤖 PRUEBA: Verificación de robots.txt")
    print("=" * 50)
    
    collector = SmartDataCollector()
    
    # Probar con algunas fuentes RSS configuradas
    test_urls = config.RSS_FEEDS[:3]  # Solo las primeras 3 para prueba
    
    for url in test_urls:
        print(f"\n📰 Probando: {url}")
        can_crawl = collector.check_robots_txt(url)
        delay = collector.get_crawl_delay(url)
        print(f"   Permitido: {'✓' if can_crawl else '✗'}")
        print(f"   Delay recomendado: {delay}s")

def test_header_collection():
    """Prueba la recolección de solo encabezados"""
    print("\n🔍 PRUEBA: Recolección de encabezados")
    print("=" * 50)
    
    collector = SmartDataCollector()
    
    # Probar con una sola fuente
    test_url = config.RSS_FEEDS[0]
    print(f"Recolectando encabezados de: {test_url}")
    
    headers = collector.collect_rss_headers_only(test_url)
    
    if headers:
        print(f"✅ {len(headers)} encabezados recolectados")
        print("\n📋 Ejemplos de encabezados:")
        
        for i, article in enumerate(headers[:3]):
            print(f"\n   {i+1}. {article['titulo'][:60]}...")
            print(f"      Relevancia NNA: {article['relevancia_nna']:.3f}")
            print(f"      Descripción: {article['descripcion'][:100]}...")
    else:
        print("❌ No se recolectaron encabezados")

def test_relevance_filtering():
    """Prueba el filtrado por relevancia"""
    print("\n🎯 PRUEBA: Filtrado por relevancia")
    print("=" * 50)
    
    collector = SmartDataCollector()
    
    # Recolectar algunos encabezados
    test_url = config.RSS_FEEDS[0]
    all_headers = collector.collect_rss_headers_only(test_url)
    
    if not all_headers:
        print("❌ No hay datos para filtrar")
        return
    
    # Probar diferentes umbrales
    thresholds = [0.1, 0.3, 0.5, 0.7]
    
    print(f"Total de artículos: {len(all_headers)}")
    
    for threshold in thresholds:
        relevant = collector.filter_relevant_articles(all_headers, threshold)
        print(f"Umbral {threshold}: {len(relevant)} artículos relevantes")
        
        if relevant:
            max_score = max(art['relevancia_nna'] for art in relevant)
            min_score = min(art['relevancia_nna'] for art in relevant)
            print(f"   Rango de scores: {min_score:.3f} - {max_score:.3f}")

def test_smart_analyzer():
    """Prueba el analizador completo con recolector inteligente"""
    print("\n🧠 PRUEBA: Analizador completo con Smart Collector")
    print("=" * 60)
    
    # Crear analizador con recolector inteligente
    analyzer = SimplifiedNewsAnalyzer(use_smart_collector=True)
    
    print("Ejecutando recolección inteligente...")
    df_result = analyzer.step_1_collect_data(relevance_threshold=0.2)  # Umbral bajo para obtener más datos
    
    if df_result is not None and len(df_result) > 0:
        print(f"\n✅ Análisis completado:")
        print(f"   📊 Total noticias: {len(df_result)}")
        print(f"   🎯 Menciones NNA: {sum(df_result['menores_identificados'] == 'Si')}")
        
        if 'procesado_completo' in df_result.columns:
            complete_content = sum(df_result['procesado_completo'])
            print(f"   📄 Contenido completo descargado: {complete_content}")
        
        if 'relevancia_nna' in df_result.columns:
            avg_relevance = df_result['relevancia_nna'].mean()
            print(f"   📈 Relevancia promedio: {avg_relevance:.3f}")
        
        # Mostrar algunos ejemplos
        print(f"\n📋 Ejemplos de noticias procesadas:")
        for i, (_, row) in enumerate(df_result.head(3).iterrows()):
            print(f"   {i+1}. {row['titulo'][:50]}...")
            print(f"      NNA: {row['menores_identificados']}")
            if 'relevancia_nna' in row:
                print(f"      Relevancia: {row['relevancia_nna']:.3f}")
    else:
        print("❌ No se obtuvieron resultados")

def compare_collectors():
    """Compara recolector tradicional vs inteligente"""
    print("\n⚖️  COMPARACIÓN: Tradicional vs Inteligente")
    print("=" * 60)
    
    print("🔄 Probando recolector TRADICIONAL...")
    analyzer_traditional = SimplifiedNewsAnalyzer(use_smart_collector=False)
    df_traditional = analyzer_traditional.step_1_collect_data()
    
    print("\n🤖 Probando recolector INTELIGENTE...")
    analyzer_smart = SimplifiedNewsAnalyzer(use_smart_collector=True)
    df_smart = analyzer_smart.step_1_collect_data(relevance_threshold=0.3)
    
    # Comparar resultados
    print(f"\n📊 RESULTADOS COMPARATIVOS:")
    print(f"   Tradicional: {len(df_traditional)} noticias")
    print(f"   Inteligente: {len(df_smart)} noticias")
    
    if len(df_traditional) > 0:
        trad_nna = sum(df_traditional['menores_identificados'] == 'Si')
        trad_rate = (trad_nna / len(df_traditional)) * 100
        print(f"   Tradicional NNA: {trad_nna} ({trad_rate:.1f}%)")
    
    if len(df_smart) > 0:
        smart_nna = sum(df_smart['menores_identificados'] == 'Si') 
        smart_rate = (smart_nna / len(df_smart)) * 100
        print(f"   Inteligente NNA: {smart_nna} ({smart_rate:.1f}%)")
        
        if 'procesado_completo' in df_smart.columns:
            complete_rate = (sum(df_smart['procesado_completo']) / len(df_smart)) * 100
            print(f"   Contenido completo: {complete_rate:.1f}%")

def main():
    """Función principal de pruebas"""
    print("🚀 PRUEBAS DEL SISTEMA DE RECOLECCIÓN INTELIGENTE")
    print("=" * 70)
    
    try:
        # Ejecutar todas las pruebas
        test_robots_txt_check()
        test_header_collection()
        test_relevance_filtering()
        test_smart_analyzer()
        compare_collectors()
        
        print("\n" + "=" * 70)
        print("✅ TODAS LAS PRUEBAS COMPLETADAS")
        print("\n💡 BENEFICIOS DEL RECOLECTOR INTELIGENTE:")
        print("   • Respeta robots.txt y delays de crawling")
        print("   • Filtra contenido por relevancia antes de descargar")
        print("   • Reduce el número de peticiones HTTP")
        print("   • Detecta mejor las menciones NNA")
        print("   • Evita bloqueos por hacer demasiadas peticiones")
        
    except Exception as e:
        print(f"\n❌ ERROR EN PRUEBAS: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()