# demo_sistema_avanzado.py
"""
Demostración del Sistema Avanzado de Web Scraping con Gestión de Fuentes
"""
import sys
import os
sys.path.append(os.path.abspath('.'))

from src.collection.advanced_scraper import AdvancedScraper, SourceManager
import json
from datetime import datetime

def demo_gestion_fuentes():
    """Demostración de gestión dinámica de fuentes"""
    print("🔧 DEMOSTRACIÓN: GESTIÓN DINÁMICA DE FUENTES")
    print("=" * 60)
    
    # Crear gestor de fuentes
    source_manager = SourceManager()
    
    print("📋 Fuentes actuales:")
    for source_id, source in source_manager.sources.items():
        status = "✅ Activo" if source.get('enabled', True) else "❌ Inactivo"
        print(f"   {source_id}: {source['name']} - {status}")
    
    # Agregar nueva fuente de ejemplo
    print(f"\n➕ Agregando nueva fuente: Excélsior")
    success = source_manager.add_source(
        "excelsior",
        "Excélsior Digital", 
        "https://www.excelsior.com.mx/rss.xml",
        "rss"
    )
    
    if success:
        print("✅ Fuente agregada exitosamente")
    else:
        print("❌ Error agregando fuente")
    
    # Mostrar fuentes actualizadas
    print(f"\n📋 Fuentes después de agregar:")
    for source_id, source in source_manager.sources.items():
        status = "✅ Activo" if source.get('enabled', True) else "❌ Inactivo"
        technique = source.get('scraping_config', {}).get('technique', 'requests')
        delay = source.get('scraping_config', {}).get('delay', 2)
        print(f"   {source_id}: {source['name']} - {status} (Técnica: {technique}, Delay: {delay}s)")
    
    return source_manager

def demo_tecnicas_scraping():
    """Demostración de múltiples técnicas de scraping"""
    print(f"\n🛠️ DEMOSTRACIÓN: TÉCNICAS DE WEB SCRAPING")
    print("=" * 60)
    
    # Crear scraper avanzado
    scraper = AdvancedScraper()
    
    print("🔍 Técnicas disponibles:")
    for technique in scraper.techniques.keys():
        print(f"   • {technique}")
    
    print(f"\n🎯 Probando scraping con selección automática de técnicas...")
    
    # Probar con las fuentes habilitadas
    sources = scraper.source_manager.get_enabled_sources()
    
    results = []
    for source_id in list(sources.keys())[:3]:  # Solo las primeras 3 para demo
        print(f"\n📰 Probando fuente: {sources[source_id]['name']}")
        
        try:
            articles = scraper.scrape_source(source_id)
            
            result = {
                'source_id': source_id,
                'source_name': sources[source_id]['name'],
                'articles_count': len(articles),
                'success': True,
                'technique_used': 'auto-selected'
            }
            
            if articles:
                result['sample_title'] = articles[0]['titulo'][:60] + "..."
            
            results.append(result)
            
            print(f"✅ {len(articles)} artículos obtenidos")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                'source_id': source_id,
                'source_name': sources[source_id]['name'],
                'articles_count': 0,
                'success': False,
                'error': str(e)
            })
    
    return results

def demo_persistencia_configuracion():
    """Demostración de persistencia de configuraciones"""
    print(f"\n💾 DEMOSTRACIÓN: PERSISTENCIA DE CONFIGURACIONES")
    print("=" * 60)
    
    source_manager = SourceManager()
    
    # Modificar configuración de una fuente
    print("⚙️ Modificando configuración de 'jornada'...")
    
    original_config = source_manager.sources.get('jornada', {}).get('scraping_config', {})
    print(f"   Configuración original: Técnica={original_config.get('technique', 'N/A')}, Delay={original_config.get('delay', 'N/A')}s")
    
    # Actualizar configuración
    success = source_manager.update_source(
        'jornada',
        config_technique='delayed_requests',
        config_delay=5
    )
    
    if success:
        updated_config = source_manager.sources['jornada']['scraping_config']
        print(f"   Configuración nueva: Técnica={updated_config['technique']}, Delay={updated_config['delay']}s")
        print("✅ Configuración actualizada y guardada")
        
        # Verificar que se guardó en archivo
        config_file = "data/sources_config.json"
        if os.path.exists(config_file):
            print(f"📁 Configuración persistida en: {config_file}")
            
            with open(config_file, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                
            jornada_saved = saved_config.get('jornada', {}).get('scraping_config', {})
            print(f"   Verificación archivo: Técnica={jornada_saved.get('technique')}, Delay={jornada_saved.get('delay')}s")
        
    else:
        print("❌ Error actualizando configuración")

def demo_recuperacion_errores():
    """Demostración de manejo y recuperación de errores"""
    print(f"\n🚨 DEMOSTRACIÓN: MANEJO Y RECUPERACIÓN DE ERRORES")
    print("=" * 60)
    
    source_manager = SourceManager()
    
    # Agregar fuente de prueba que probablemente falle
    print("🧪 Agregando fuente de prueba (URL inválida)...")
    source_manager.add_source(
        "test_invalid",
        "Fuente de Prueba Inválida",
        "https://sitio-que-no-existe-12345.com/feed.xml",
        "rss"
    )
    
    scraper = AdvancedScraper()
    
    print("⚠️ Intentando scrapear fuente inválida...")
    articles = scraper.scrape_source("test_invalid")
    
    # Verificar conteo de errores
    error_count = source_manager.sources['test_invalid']['scraping_config']['error_count']
    print(f"📊 Contador de errores: {error_count}")
    
    # Simular múltiples errores
    print("🔄 Simulando múltiples fallos...")
    for i in range(1, 4):
        print(f"   Intento {i}...")
        articles = scraper.scrape_source("test_invalid")
        error_count = source_manager.sources['test_invalid']['scraping_config']['error_count']
        enabled = source_manager.sources['test_invalid']['enabled']
        print(f"   Errores: {error_count}, Habilitado: {enabled}")
        
        if not enabled:
            print("🛑 Fuente deshabilitada automáticamente por exceso de errores")
            break
    
    # Limpiar fuente de prueba
    source_manager.delete_source("test_invalid")
    print("🧹 Fuente de prueba eliminada")

def demo_estadisticas_detalladas():
    """Mostrar estadísticas detalladas del sistema"""
    print(f"\n📊 ESTADÍSTICAS DETALLADAS DEL SISTEMA")
    print("=" * 60)
    
    source_manager = SourceManager()
    sources = source_manager.sources
    
    # Estadísticas generales
    total_sources = len(sources)
    enabled_sources = len([s for s in sources.values() if s.get('enabled', True)])
    
    print(f"📈 Resumen General:")
    print(f"   • Total de fuentes: {total_sources}")
    print(f"   • Fuentes activas: {enabled_sources}")
    print(f"   • Fuentes inactivas: {total_sources - enabled_sources}")
    
    # Estadísticas por técnica
    techniques = {}
    for source in sources.values():
        tech = source.get('scraping_config', {}).get('technique', 'requests')
        techniques[tech] = techniques.get(tech, 0) + 1
    
    print(f"\n🔧 Distribución por Técnica:")
    for tech, count in techniques.items():
        print(f"   • {tech}: {count} fuentes")
    
    # Fuentes con errores
    error_sources = [(k, v) for k, v in sources.items() 
                    if v.get('scraping_config', {}).get('error_count', 0) > 0]
    
    if error_sources:
        print(f"\n⚠️ Fuentes con Errores:")
        for source_id, source in error_sources:
            error_count = source['scraping_config']['error_count']
            print(f"   • {source['name']}: {error_count} errores")
    else:
        print(f"\n✅ Todas las fuentes sin errores recientes")
    
    # Delays configurados
    delays = [s.get('scraping_config', {}).get('delay', 2) for s in sources.values()]
    avg_delay = sum(delays) / len(delays) if delays else 0
    
    print(f"\n⏱️ Configuración de Delays:")
    print(f"   • Delay promedio: {avg_delay:.1f} segundos")
    print(f"   • Delay mínimo: {min(delays)}s")
    print(f"   • Delay máximo: {max(delays)}s")

def main():
    """Función principal de demostración"""
    print("🚀 SISTEMA AVANZADO DE WEB SCRAPING")
    print("🎯 Gestión Dinámica de Fuentes y Técnicas Múltiples")
    print("=" * 80)
    print(f"⏰ Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # 1. Gestión de fuentes
        source_manager = demo_gestion_fuentes()
        
        # 2. Técnicas de scraping
        results = demo_tecnicas_scraping()
        
        # 3. Persistencia
        demo_persistencia_configuracion()
        
        # 4. Manejo de errores
        demo_recuperacion_errores()
        
        # 5. Estadísticas
        demo_estadisticas_detalladas()
        
        print(f"\n✨ RESUMEN DE CAPACIDADES IMPLEMENTADAS")
        print("=" * 80)
        
        capabilities = [
            "🔧 Gestión dinámica de fuentes RSS (CRUD completo)",
            "💾 Persistencia automática de configuraciones",
            "🛠️ Múltiples técnicas de web scraping",
            "🤖 Selección automática de técnica según robots.txt",
            "⚡ Técnicas avanzadas: Selenium, rotación UA, delays, async",
            "🛡️ Manejo inteligente de errores y recuperación",
            "📊 Estadísticas detalladas por fuente",
            "🔄 Auto-deshabilitación de fuentes problemáticas",
            "⏱️ Delays configurables y progresivos",
            "🌐 Interfaz web para gestión completa"
        ]
        
        for capability in capabilities:
            print(f"   {capability}")
        
        print(f"\n📈 RESULTADOS DE LA DEMOSTRACIÓN:")
        successful_scrapes = sum(1 for r in results if r['success'])
        total_articles = sum(r['articles_count'] for r in results if r['success'])
        
        print(f"   • Fuentes probadas: {len(results)}")
        print(f"   • Scraping exitoso: {successful_scrapes}/{len(results)}")
        print(f"   • Total artículos obtenidos: {total_articles}")
        
        print(f"\n⏰ Completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🎉 Demostración del Sistema Avanzado finalizada exitosamente!")
        
    except Exception as e:
        print(f"\n❌ Error en la demostración: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()