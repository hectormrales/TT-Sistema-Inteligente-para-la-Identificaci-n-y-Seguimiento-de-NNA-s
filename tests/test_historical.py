import sys
import os
import logging

# Configurar logging básico para ver las advertencias del colector
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Añadir el directorio raíz al path para que los imports funcionen
sys.path.append(os.getcwd())

# Intentar cargar el contexto de la aplicación para que las queries a la BD no fallen
try:
    if os.path.exists("wsgi.py"):
        from wsgi import app
    elif os.path.exists("app.py"):
        from app import app
    else:
        from app import create_app
        app = create_app()
    
    ctx = app.app_context()
    ctx.push()
    print("[INFO] Contexto de aplicación Flask cargado exitosamente.")
except Exception as e:
    print(f"[WARN] No se pudo cargar el contexto de la aplicación: {e}")
    print("[WARN] Las validaciones contra la base de datos (PostgreSQL) podrían ser omitidas o fallar.")

from src.collection.collector import _inject_date_operators, _scrape_google_search_html, collect_all_news
from src.collection.scraper import StealthSession

def test_historical_logic():
    print("\n" + "="*70)
    print("  TEST DE RECOLECCIÓN HISTÓRICA (MODO VALIDACIÓN TÉCNICA)")
    print("="*70)

    # Parámetros de prueba: Enero 2025
    start_date = "2025-01-01"
    end_date = "2025-01-31"
    
    # 1. Validar la inyección de parámetros con urllib.parse
    print(f"\n[1] VALIDACIÓN DE INYECCIÓN DE URL (urllib.parse):")
    original_url = "https://news.google.com/rss/search?q=feminicidio+mexico&hl=es-419&gl=MX&ceid=MX:es-419"
    injected_url = _inject_date_operators(original_url, start_date, end_date)
    
    print(f"    Original:  {original_url}")
    print(f"    Inyectada: {injected_url}")
    
    if "after:2025-01-01" in injected_url and "before:2025-01-31" in injected_url:
        print("    ✅ OK: Parámetros 'after:' y 'before:' inyectados correctamente.")
    else:
        print("    ❌ ERROR: La inyección de URL falló.")

    # 2. Validar el scraping de HTML directo (Fallback)
    print(f"\n[2] VALIDACIÓN DE FALLBACK HTML (_scrape_google_search_html):")
    session = StealthSession(test_mode=False) 
    query = "feminicidio hijos huerfanos mexico"
    
    print(f"    Ejecutando búsqueda profunda para: '{query}'...")
    articles = _scrape_google_search_html(query, start_date, end_date, session)
    
    print(f"    -> Se extrajeron {len(articles)} resultados desde la pestaña de noticias de Google.")
    if articles:
        for i, art in enumerate(articles[:3]):
            print(f"       [{i+1}] {art['titulo'][:60]}...")
            print(f"           URL: {art['enlace'][:70]}...")
    else:
        print("    ⚠️ No se extrajeron artículos. Esto puede deberse a la estructura del DOM o bloqueos.")

    # 3. Prueba de integración con collect_all_news
    print(f"\n[3] VALIDACIÓN DE INTEGRACIÓN (collect_all_news - Modo Google):")
    print("    Iniciando recolección simulada (se omitirán duplicados en BD si el contexto cargó)...")
    
    df = collect_all_news(
        keep_all=True, 
        start_date=start_date, 
        end_date=end_date, 
        scraper_type='google'
    )
    
    print(f"\n[RESUMEN DE RESULTADOS]:")
    print(f"    Total de noticias encontradas para Enero 2025: {len(df)}")
    if not df.empty:
        fuentes = df['fuente'].value_counts()
        print(f"    Desglose por fuente:\n{fuentes}")
        
        print(f"\n    Muestra de artículos:")
        for _, row in df.head(2).iterrows():
            print(f"    - {row['titulo'][:70]}...")
    
    print("\n" + "="*70)
    print("  VALIDACIÓN COMPLETADA")
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        test_historical_logic()
    except KeyboardInterrupt:
        print("\nTest cancelado por el usuario.")
    except Exception as e:
        print(f"\n[FATAL] Error ejecutando el test: {e}")
        import traceback
        traceback.print_exc()
