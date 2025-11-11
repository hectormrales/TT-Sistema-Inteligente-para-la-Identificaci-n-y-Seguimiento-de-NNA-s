"""
Script para probar el detector de feminicidios en los datos reales existentes.
Esto nos dirá cuántas noticias realmente cumplen con el objetivo.
"""

import pandas as pd
import sys
import os

# Agregar directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from collection.feminicide_detector import FeminicideDetector

def test_detector_on_real_data():
    """Prueba el detector en las noticias reales del CSV."""
    
    print("="*80)
    print("ANÁLISIS DE DATOS REALES CON NUEVO DETECTOR DE FEMINICIDIOS")
    print("="*80)
    
    # Cargar datos
    csv_path = 'data/noticias.csv'
    
    if not os.path.exists(csv_path):
        print(f"❌ ERROR: No se encontró {csv_path}")
        return
    
    df = pd.read_csv(csv_path)
    print(f"\n📊 Total de noticias en CSV: {len(df)}")
    
    # Inicializar detector
    detector = FeminicideDetector()
    
    # Analizar cada noticia
    results = []
    for idx, row in df.iterrows():
        # Combinar título y contenido
        text = f"{row.get('titulo', '')} {row.get('contenido', '')}"
        
        # Detectar
        detection = detector.detect(text)
        
        # Agregar información de la fila
        detection['titulo'] = row.get('titulo', '')[:80]  # Truncar
        detection['fuente'] = row.get('fuente', 'N/A')
        detection['fecha'] = row.get('fecha_publicacion', 'N/A')
        detection['menores_identificados_original'] = row.get('menores_identificados', 'N/A')
        
        results.append(detection)
    
    # Convertir a DataFrame
    results_df = pd.DataFrame(results)
    
    # ESTADÍSTICAS GENERALES
    print("\n" + "="*80)
    print("ESTADÍSTICAS GENERALES")
    print("="*80)
    
    total = len(results_df)
    feminicides = results_df['is_feminicide'].sum()
    with_children = results_df['has_children'].sum()
    with_orphans = results_df['has_orphans'].sum()
    target_news = results_df['is_target_news'].sum()
    
    print(f"\n📈 Detección:")
    print(f"   - Noticias de feminicidio: {feminicides} ({feminicides/total*100:.1f}%)")
    print(f"   - Con mención de NNA: {with_children} ({with_children/total*100:.1f}%)")
    print(f"   - Con mención de huérfanos: {with_orphans} ({with_orphans/total*100:.1f}%)")
    print(f"   - NOTICIAS OBJETIVO (feminicidio+NNA): {target_news} ({target_news/total*100:.1f}%)")
    
    # PRIORIDADES
    print(f"\n🎯 Por prioridad:")
    priority_counts = results_df['priority'].value_counts()
    for priority in ['ALTA', 'MEDIA', 'BAJA', 'IRRELEVANTE']:
        count = priority_counts.get(priority, 0)
        print(f"   - {priority}: {count} ({count/total*100:.1f}%)")
    
    # CONFIANZA PROMEDIO
    avg_confidence = results_df['confidence'].mean()
    avg_confidence_target = results_df[results_df['is_target_news']]['confidence'].mean()
    
    print(f"\n💯 Confianza promedio:")
    print(f"   - General: {avg_confidence:.1%}")
    if target_news > 0:
        print(f"   - Noticias objetivo: {avg_confidence_target:.1%}")
    
    # COMPARACIÓN CON DETECCIÓN ORIGINAL
    print("\n" + "="*80)
    print("COMPARACIÓN: DETECCIÓN ORIGINAL VS NUEVA")
    print("="*80)
    
    # Contar detección original (menores_identificados)
    original_detection = (df['menores_identificados'] == 'Si').sum()
    
    print(f"\n📊 Sistema original (genérico):")
    print(f"   - Detectó NNA en: {original_detection} noticias ({original_detection/total*100:.1f}%)")
    print(f"   - Criterio: Cualquier mención de menores/niños/hijos")
    
    print(f"\n📊 Nuevo detector (específico):")
    print(f"   - Detectó OBJETIVO en: {target_news} noticias ({target_news/total*100:.1f}%)")
    print(f"   - Criterio: Feminicidio + NNA (víctimas indirectas)")
    
    reduction = original_detection - target_news
    if original_detection > 0:
        print(f"\n⚠️  Reducción: {reduction} noticias ({reduction/original_detection*100:.1f}%)")
        print(f"   → Estas {reduction} noticias eran FALSOS POSITIVOS")
        print(f"   → Mencionaban NNA pero NO eran sobre feminicidios")
    
    # MOSTRAR EJEMPLOS DE NOTICIAS OBJETIVO
    print("\n" + "="*80)
    print("EJEMPLOS DE NOTICIAS OBJETIVO DETECTADAS (PRIORIDAD ALTA)")
    print("="*80)
    
    high_priority = results_df[results_df['priority'] == 'ALTA'].head(5)
    
    if len(high_priority) > 0:
        for idx, row in high_priority.iterrows():
            print(f"\n📰 Noticia #{idx + 1}:")
            print(f"   Título: {row['titulo']}")
            print(f"   Fuente: {row['fuente']}")
            print(f"   Confianza: {row['confidence']:.1%}")
            print(f"   Feminicidio: {'✅' if row['is_feminicide'] else '❌'}")
            print(f"   NNA: {'✅' if row['has_children'] else '❌'}")
            print(f"   Huérfanos: {'✅' if row['has_orphans'] else '❌'}")
    else:
        print("\n❌ No se detectaron noticias de PRIORIDAD ALTA")
        print("   Esto confirma el problema: las fuentes RSS actuales NO proporcionan")
        print("   noticias sobre feminicidios con víctimas indirectas.")
    
    # MOSTRAR EJEMPLOS DE FALSOS POSITIVOS
    print("\n" + "="*80)
    print("EJEMPLOS DE FALSOS POSITIVOS (detectados antes, irrelevantes ahora)")
    print("="*80)
    
    # Noticias que el sistema original marcó como NNA pero que NO son objetivo
    false_positives = results_df[
        (results_df['menores_identificados_original'] == 'Si') & 
        (results_df['is_target_news'] == False)
    ].head(5)
    
    if len(false_positives) > 0:
        for idx, row in false_positives.iterrows():
            print(f"\n📰 Falso Positivo #{idx + 1}:")
            print(f"   Título: {row['titulo']}")
            print(f"   Fuente: {row['fuente']}")
            print(f"   Detección original: ✅ (marcado como NNA)")
            print(f"   Detección nueva: ❌ (NO es feminicidio con NNA)")
            print(f"   Razón: ", end="")
            if not row['is_feminicide']:
                print("No menciona feminicidio")
            elif not row['has_children']:
                print("No menciona NNA")
            else:
                print("Confianza muy baja")
    
    # CONCLUSIÓN
    print("\n" + "="*80)
    print("CONCLUSIÓN Y RECOMENDACIÓN")
    print("="*80)
    
    target_percentage = (target_news / total * 100) if total > 0 else 0
    
    print(f"\n🎯 Porcentaje de noticias OBJETIVO: {target_percentage:.1f}%")
    print(f"   Meta esperada: >70%")
    
    if target_percentage < 10:
        print(f"\n❌ CRÍTICO: Solo {target_percentage:.1f}% de las noticias cumplen el objetivo")
        print("   → Las fuentes RSS actuales NO son adecuadas")
        print("   → Se requiere cambiar a fuentes especializadas:")
        print("      • CIMAC Noticias (cimacnoticias.com.mx)")
        print("      • SEM México (semmexico.mx)")
        print("      • Secciones de género de medios nacionales")
    elif target_percentage < 50:
        print(f"\n⚠️  INSUFICIENTE: Solo {target_percentage:.1f}% cumple el objetivo")
        print("   → Se recomienda agregar más fuentes especializadas")
    else:
        print(f"\n✅ ACEPTABLE: {target_percentage:.1f}% cumple el objetivo")
        print("   → Las fuentes RSS son adecuadas")
    
    # Guardar resultados
    output_path = 'data/noticias_analyzed_with_new_detector.csv'
    results_df.to_csv(output_path, index=False)
    print(f"\n💾 Resultados guardados en: {output_path}")

if __name__ == "__main__":
    test_detector_on_real_data()
