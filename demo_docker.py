#!/usr/bin/env python3
"""
Demostración del Sistema Avanzado en Docker
Versión simplificada para contenedores
"""
import sys
import os
sys.path.append(os.path.abspath('.'))

import json
import time
from datetime import datetime

def test_api_endpoints():
    """Probar los endpoints de la API"""
    print("🔗 PROBANDO ENDPOINTS DE LA API")
    print("=" * 50)
    
    base_url = "http://localhost:5000"
    
    # Test 1: Página principal
    print("📄 Probando página principal...")
    try:
        import requests
        response = requests.get(f"{base_url}/", timeout=10)
        if response.status_code == 200:
            print("✅ Página principal accesible")
        else:
            print(f"❌ Error en página principal: {response.status_code}")
    except Exception as e:
        print(f"❌ Error conectando: {e}")
    
    # Test 2: API de fuentes
    print("\n� Probando API de fuentes...")
    try:
        import requests
        response = requests.get(f"{base_url}/api/sources", timeout=10)
        if response.status_code == 200:
            sources = response.json()
            print(f"✅ API de fuentes funcionando - {len(sources)} fuentes")
            
            # Mostrar algunas fuentes
            for source_id, source in list(sources.items())[:3]:
                status = "✅" if source.get('enabled', True) else "❌"
                print(f"   {status} {source_id}: {source['name']}")
        else:
            print(f"❌ Error en API de fuentes: {response.status_code}")
    except Exception as e:
        print(f"❌ Error en API: {e}")
    
    # Test 3: Agregar fuente de prueba
    print("\n➕ Probando agregar nueva fuente...")
    try:
        import requests
        new_source = {
            "id": "test_docker",
            "name": "Fuente de Prueba Docker",
            "url": "https://www.excelsior.com.mx/rss.xml",
            "type": "rss"
        }
        
        response = requests.post(
            f"{base_url}/api/sources",
            json=new_source,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Fuente agregada exitosamente")
            
            # Verificar que se agregó
            response = requests.get(f"{base_url}/api/sources", timeout=10)
            if response.status_code == 200:
                sources = response.json()
                if "test_docker" in sources:
                    print("✅ Fuente verificada en la lista")
        else:
            print(f"❌ Error agregando fuente: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error agregando fuente: {e}")
    
    # Test 4: Eliminar fuente de prueba
    print("\n🗑️ Limpiando fuente de prueba...")
    try:
        import requests
        response = requests.delete(f"{base_url}/api/sources/test_docker", timeout=10)
        if response.status_code == 200:
            print("✅ Fuente de prueba eliminada")
        else:
            print(f"⚠️ Fuente de prueba no eliminada: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Error eliminando fuente: {e}")

def test_scraping_basic():
    """Probar funcionalidad básica de scraping"""
    print("\n🕷️ PROBANDO SCRAPING BÁSICO")
    print("=" * 50)
    
    base_url = "http://localhost:5000"
    
    try:
        import requests
        # Probar análisis básico
        response = requests.post(
            f"{base_url}/api/analyze",
            json={"sources": ["jornada", "milenio"]},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Análisis completado")
            print(f"   📰 Artículos procesados: {result.get('total_articles', 0)}")
            print(f"   🚨 Casos detectados: {result.get('casos_detectados', 0)}")
            
            # Mostrar algunos títulos si existen
            if 'articulos' in result and result['articulos']:
                print("\n📋 Ejemplos de artículos:")
                for i, articulo in enumerate(result['articulos'][:3]):
                    titulo = articulo.get('titulo', 'Sin título')[:60]
                    print(f"   {i+1}. {titulo}...")
        else:
            print(f"❌ Error en análisis: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error en scraping: {e}")

def check_docker_status():
    """Verificar estado del contenedor Docker"""
    print("🐳 VERIFICANDO ESTADO DEL CONTENEDOR")
    print("=" * 50)
    
    # Verificar si estamos en Docker
    if os.path.exists('/.dockerenv'):
        print("✅ Ejecutándose dentro de contenedor Docker")
    else:
        print("⚠️ No se detectó entorno Docker")
    
    # Verificar archivos importantes
    files_to_check = [
        "app_docker.py",
        "requirements.txt", 
        "data/sources_config.json",
        "src/collection/advanced_scraper.py"
    ]
    
    print("\n📁 Verificando archivos del sistema:")
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - No encontrado")
    
    # Verificar puerto de la aplicación
    print(f"\n🌐 Aplicación debería estar en: http://localhost:5000")

def show_docker_instructions():
    """Mostrar instrucciones para Docker"""
    print("\n🚀 INSTRUCCIONES PARA EJECUTAR CON DOCKER")
    print("=" * 80)
    
    print("1️⃣ Construir la imagen Docker:")
    print("   docker build -t nna-sistema-avanzado .")
    print()
    
    print("2️⃣ Ejecutar el contenedor:")
    print("   docker run -d --name nna-container -p 5000:5000 nna-sistema-avanzado")
    print()
    
    print("3️⃣ Ver logs del contenedor:")
    print("   docker logs -f nna-container")
    print()
    
    print("4️⃣ Acceder al contenedor:")
    print("   docker exec -it nna-container /bin/bash")
    print()
    
    print("5️⃣ Detener el contenedor:")
    print("   docker stop nna-container")
    print()
    
    print("6️⃣ Acceder a la aplicación:")
    print("   🌐 Dashboard: http://localhost:5000")
    print("   📡 API: http://localhost:5000/api/sources")

def demo_configuration_management():
    """Demostración de gestión de configuraciones"""
    print("\n⚙️ GESTIÓN DE CONFIGURACIONES EN DOCKER")
    print("=" * 50)
    
    config_file = "data/sources_config.json"
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            print(f"📋 Configuración cargada desde {config_file}")
            print(f"   🔢 Total de fuentes: {len(config)}")
            
            # Mostrar configuración de las fuentes
            for source_id, source_data in list(config.items())[:5]:
                name = source_data.get('name', 'Sin nombre')
                enabled = source_data.get('enabled', True)
                technique = source_data.get('scraping_config', {}).get('technique', 'requests')
                delay = source_data.get('scraping_config', {}).get('delay', 2)
                
                status = "✅" if enabled else "❌"
                print(f"   {status} {source_id}: {name}")
                print(f"      Técnica: {technique}, Delay: {delay}s")
        
        except Exception as e:
            print(f"❌ Error leyendo configuración: {e}")
    else:
        print(f"❌ Archivo de configuración no encontrado: {config_file}")

def main():
    """Función principal de demostración Docker"""
    print("🐳 DEMOSTRACIÓN DEL SISTEMA AVANZADO EN DOCKER")
    print("🎯 Sistema de Web Scraping con Gestión Dinámica de Fuentes")
    print("=" * 80)
    print(f"⏰ Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Verificar estado del Docker
    check_docker_status()
    
    # Gestión de configuraciones
    demo_configuration_management()
    
    # Mostrar instrucciones
    show_docker_instructions()
    
    # Si la aplicación está corriendo, probar APIs
    print("\n🔍 PROBANDO CONECTIVIDAD (requiere aplicación ejecutándose)")
    print("=" * 50)
    
    try:
        # Esperar un poco para que la aplicación inicie
        print("⏳ Esperando que la aplicación inicie...")
        time.sleep(3)
        
        # Probar endpoints
        test_api_endpoints()
        
        # Probar scraping básico
        test_scraping_basic()
        
    except Exception as e:
        print(f"ℹ️ Pruebas de conectividad omitidas: {e}")
        print("   Ejecutar después de 'docker run' para probar APIs")
    
    print(f"\n✨ CAPACIDADES DEL SISTEMA DOCKERIZADO")
    print("=" * 80)
    
    capabilities = [
        "🐳 Contenedor Docker completo con todas las dependencias",
        "🔧 Gestión dinámica de fuentes RSS via API REST",
        "🛠️ Múltiples técnicas de web scraping integradas",
        "🌐 Interfaz web Bootstrap 5 completamente funcional",
        "💾 Persistencia de datos en volúmenes Docker",
        "📡 API REST completa para integración externa",
        "🛡️ Scraping ético con verificación robots.txt",
        "⚡ Procesamiento asíncrono y técnicas avanzadas",
        "� Monitoreo y estadísticas en tiempo real",
        "🔄 Auto-recuperación y manejo de errores"
    ]
    
    for capability in capabilities:
        print(f"   {capability}")
    
    print(f"\n⏰ Completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎉 Sistema listo para producción con Docker!")

if __name__ == "__main__":
    main()