# test_app.py
"""Script de prueba para verificar que la aplicación funciona correctamente."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.collection.data_collector import detect_children_mentions, collect_news_from_rss
from src.processing.text_processor import clean_and_lemmatize_series
from src.utils.file_handler import load_from_csv
import pandas as pd

def test_children_detection():
    """Prueba la detección de menciones de menores."""
    print("\n=== Prueba de Detección de Menores ===")
    
    test_cases = [
        ("La víctima tenía dos hijos menores de edad", "Sí"),
        ("El incidente ocurrió en la madrugada", "No"),
        ("Sus hijas quedaron huérfanas tras el femicidio", "Sí"),
        ("Los niños presenciaron el terrible evento", "Sí"),
    ]
    
    for text, expected in test_cases:
        result = detect_children_mentions(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{text[:50]}...' -> {result} (esperado: {expected})")

def test_text_processing():
    """Prueba el procesamiento de texto."""
    print("\n=== Prueba de Procesamiento de Texto ===")
    
    sample_texts = pd.Series([
        "Este es un texto con MAYÚSCULAS y números 123",
        "Texto con acentos: niños, niñas, corazón",
        "¡Signos de puntuación! ¿Qué tal?",
    ])
    
    processed = clean_and_lemmatize_series(sample_texts)
    
    for original, processed_text in zip(sample_texts, processed):
        print(f"Original: {original}")
        print(f"Procesado: {processed_text}")
        print("---")

def test_csv_loading():
    """Prueba la carga del archivo CSV."""
    print("\n=== Prueba de Carga de CSV ===")
    
    try:
        df = load_from_csv('data/noticias_analizadas.csv')
        print(f"✅ CSV cargado exitosamente: {len(df)} filas")
        print(f"Columnas: {list(df.columns)}")
        
        if len(df) > 0:
            print(f"Primera fila:")
            print(df.iloc[0].to_dict())
    except Exception as e:
        print(f"❌ Error cargando CSV: {e}")

if __name__ == "__main__":
    print("🧪 Ejecutando pruebas del sistema...")
    
    test_children_detection()
    test_text_processing()
    test_csv_loading()
    
    print("\n✅ Pruebas completadas!")