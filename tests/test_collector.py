# tests/test_collector.py
# -*- coding: utf-8 -*-
"""
Tests para el módulo de recolección de noticias.
"""

import sys
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collection.data_collector import (
    collect_news_from_rss,
    collect_from_google_news,
    collect_all_news
)
from src.collection.feminicide_detector import FeminicideDetector
import config


def test_rss_collection():
    """Prueba recolección desde RSS feeds."""
    print("\n" + "="*80)
    print("TEST: Recolección desde RSS Feeds")
    print("="*80)
    
    # Probar con el primer feed
    rss_url = config.RSS_FEEDS[0] if config.RSS_FEEDS else None
    if not rss_url:
        print("⚠️  No hay RSS feeds configurados")
        return
    
    articles = collect_news_from_rss(rss_url)
    
    print(f"\n✓ Recolectadas {len(articles)} noticias de {rss_url}")
    
    if articles:
        print("\nEjemplo de noticia:")
        art = articles[0]
        print(f"  Título: {art['titulo'][:80]}...")
        print(f"  Fuente: {art['fuente']}")
        print(f"  Fecha: {art['fecha']}")
        print(f"  Es feminicidio: {art['es_feminicidio']}")
        print(f"  Tiene NNA: {art['tiene_nna']}")
        print(f"  Prioridad: {art['prioridad']}")
        print(f"  Confianza: {art['confianza']:.2%}")


def test_google_news():
    """Prueba recolección desde Google News."""
    print("\n" + "="*80)
    print("TEST: Recolección desde Google News")
    print("="*80)
    
    articles = collect_from_google_news(max_results=10)
    
    print(f"\n✓ Recolectadas {len(articles)} noticias de Google News")
    
    if articles:
        # Mostrar estadísticas
        feminicides = sum(1 for a in articles if a['es_feminicidio'])
        target = sum(1 for a in articles if a['es_objetivo'])
        high_priority = sum(1 for a in articles if a['prioridad'] == 'ALTA')
        
        print(f"\nEstadísticas:")
        print(f"  Feminicidios: {feminicides}/{len(articles)} ({feminicides/len(articles)*100:.1f}%)")
        print(f"  Noticias objetivo: {target}/{len(articles)} ({target/len(articles)*100:.1f}%)")
        print(f"  Prioridad ALTA: {high_priority}")
        
        # Mostrar ejemplo de noticia objetivo
        target_news = [a for a in articles if a['es_objetivo']]
        if target_news:
            print("\nEjemplo de noticia OBJETIVO:")
            art = target_news[0]
            print(f"  Título: {art['titulo']}")
            print(f"  Prioridad: {art['prioridad']}")
            print(f"  Confianza: {art['confianza']:.2%}")


def test_detector():
    """Prueba el detector de feminicidios."""
    print("\n" + "="*80)
    print("TEST: Detector de Feminicidios")
    print("="*80)
    
    detector = FeminicideDetector()
    
    # Casos de prueba
    test_cases = [
        ("Feminicidio en Edomex deja a dos hijos huérfanos", True, True, True),
        ("Mujer asesinada tenía tres hijos menores de edad", True, True, True),
        ("Madre de dos niños hallada sin vida en su domicilio", True, True, True),
        ("Accidente de tráfico deja dos muertos", False, False, False),
        ("Reunión de vecinos sobre seguridad en colonia", False, False, False),
    ]
    
    print("\nResultados de detección:")
    for text, expected_fem, expected_children, expected_target in test_cases:
        result = detector.detect(text)
        
        status = "✓" if (
            result['is_feminicide'] == expected_fem and
            result['has_children'] == expected_children and
            result['is_target_news'] == expected_target
        ) else "✗"
        
        print(f"\n{status} \"{text[:60]}...\"")
        print(f"    Feminicidio: {result['is_feminicide']}, "
              f"NNA: {result['has_children']}, "
              f"Objetivo: {result['is_target_news']}")
        print(f"    Prioridad: {result['priority']}, Confianza: {result['confidence']:.2%}")


def test_full_collection():
    """Prueba recolección completa (RSS + Google News)."""
    print("\n" + "="*80)
    print("TEST: Recolección Completa (RSS + Google News)")
    print("="*80)
    
    df = collect_all_news(use_google_news=True)
    
    if len(df) > 0:
        print(f"\n✓ Recolección exitosa: {len(df)} noticias")
        
        # Estadísticas
        feminicides = df['es_feminicidio'].sum()
        target_news = df['es_objetivo'].sum()
        high_priority = len(df[df['prioridad'] == 'ALTA'])
        
        print(f"\nResultados:")
        print(f"  Feminicidios: {feminicides} ({feminicides/len(df)*100:.1f}%)")
        print(f"  Noticias objetivo: {target_news} ({target_news/len(df)*100:.1f}%)")
        print(f"  Prioridad ALTA: {high_priority}")
        
        # Mostrar ejemplos de alta prioridad
        high_prio_news = df[df['prioridad'] == 'ALTA']
        if len(high_prio_news) > 0:
            print(f"\nEjemplos de noticias de ALTA prioridad:")
            for idx, row in high_prio_news.head(3).iterrows():
                print(f"\n  {idx+1}. {row['titulo'][:70]}...")
                print(f"     Confianza: {row['confianza']:.2%}")
                print(f"     Fuente: {row['fuente']}")
    else:
        print("⚠️  No se recolectaron noticias")


def main():
    """Ejecuta todos los tests."""
    print("\n" + "="*80)
    print(" SUITE DE PRUEBAS - SISTEMA NNA")
    print(" Trabajo Terminal 1 - ESIME Zacatenco")
    print("="*80)
    
    try:
        # Ejecutar tests
        test_detector()
        test_rss_collection()
        test_google_news()
        test_full_collection()
        
        print("\n" + "="*80)
        print("✓ TODOS LOS TESTS COMPLETADOS")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n✗ ERROR EN TESTS: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
