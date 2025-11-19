#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análisis Simple - Pipeline Optimizado
======================================

Pipeline simplificado sin ML innecesario:
1. RECOLECCIÓN (Internet → RSS + Google News)
2. DETECTOR (Filtra feminicidios con NNA)
3. ¡LISTO!

Los pasos de ML (TF-IDF, LDA, DBSCAN) solo sirven con cientos/miles de noticias.
Con <100 noticias, este pipeline simple es MÁS EFICIENTE.

Autor: Héctor Morales
Fecha: 18 de noviembre de 2025
"""

import sys
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

# Configurar encoding UTF-8 para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Agregar src al path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.collection.data_collector import collect_all_news
import config


def print_section(title, char="="):
    """Imprime una sección visual."""
    print(f"\n{char * 80}")
    print(f" {title}")
    print(f"{char * 80}\n")


def analizar_simple():
    """
    Pipeline simple y eficiente.
    
    Returns:
        DataFrame con noticias objetivo detectadas
    """
    print_section("PIPELINE SIMPLE - SISTEMA NNA")
    
    print("Este pipeline usa SOLO los pasos necesarios:")
    print("  1. RECOLECCION: Buscar noticias en Internet")
    print("  2. DETECTOR: Filtrar feminicidios con NNA")
    print("  3. GUARDAR: Exportar resultados")
    print()
    print("NO usa pasos ML innecesarios (TF-IDF, LDA, DBSCAN)")
    print("Razon: Con <100 noticias, ML no aporta valor significativo.")
    print()
    
    # ========================================================================
    # PASO 1: RECOLECCIÓN
    # ========================================================================
    
    print_section("PASO 1: RECOLECCION DE NOTICIAS", "-")
    
    print(f"Fuentes configuradas: {len(config.RSS_FEEDS)} RSS + Google News")
    print(f"Google News max resultados: {config.GOOGLE_NEWS_CONFIG['max_results']}")
    print()
    
    print("Iniciando recoleccion...")
    df_noticias = collect_all_news(use_google_news=True)
    
    print(f"\nNoticias recolectadas: {len(df_noticias)}")
    
    if len(df_noticias) == 0:
        print("\nAdvertencia: No se recolectaron noticias. Verifica conexion a Internet.")
        return pd.DataFrame()
    
    # ========================================================================
    # PASO 2: ANÁLISIS CON DETECTOR (ya aplicado en collect_all_news)
    # ========================================================================
    
    print_section("PASO 2: ANALISIS CON DETECTOR", "-")
    
    # Estadísticas
    total = len(df_noticias)
    feminicidios = df_noticias['es_feminicidio'].sum()
    con_nna = df_noticias['tiene_nna'].sum()
    objetivo = df_noticias['es_objetivo'].sum()
    
    # Por prioridad
    alta = len(df_noticias[df_noticias['prioridad'] == 'ALTA'])
    media = len(df_noticias[df_noticias['prioridad'] == 'MEDIA'])
    baja = len(df_noticias[df_noticias['prioridad'] == 'BAJA'])
    irrelevante = len(df_noticias[df_noticias['prioridad'] == 'IRRELEVANTE'])
    
    print("Resultados del detector:")
    print(f"  Total noticias: {total}")
    print(f"  Feminicidios detectados: {feminicidios} ({feminicidios/total*100:.1f}%)")
    print(f"  Con mencion de NNA: {con_nna} ({con_nna/total*100:.1f}%)")
    print(f"  NOTICIAS OBJETIVO: {objetivo} ({objetivo/total*100:.1f}%)")
    print()
    
    print("Distribucion por prioridad:")
    print(f"  ALTA: {alta}")
    print(f"  MEDIA: {media}")
    print(f"  BAJA: {baja}")
    print(f"  IRRELEVANTE: {irrelevante}")
    print()
    
    # ========================================================================
    # MOSTRAR NOTICIAS OBJETIVO
    # ========================================================================
    
    noticias_objetivo = df_noticias[df_noticias['es_objetivo'] == True].copy()
    
    if len(noticias_objetivo) > 0:
        print_section("NOTICIAS OBJETIVO DETECTADAS", "-")
        
        # Ordenar por prioridad y confianza
        prioridad_order = {'ALTA': 0, 'MEDIA': 1, 'BAJA': 2}
        noticias_objetivo['_orden'] = noticias_objetivo['prioridad'].map(prioridad_order)
        noticias_objetivo = noticias_objetivo.sort_values(['_orden', 'confianza'], ascending=[True, False])
        
        for idx, row in noticias_objetivo.head(10).iterrows():
            print(f"\n[{row['prioridad']}] Confianza: {row['confianza']:.1%}")
            print(f"Titulo: {row['titulo'][:75]}...")
            print(f"Fuente: {row['fuente']}")
            print(f"Fecha: {row['fecha']}")
            
            # Mostrar snippet del contenido
            if pd.notna(row['contenido']) and len(row['contenido']) > 0:
                snippet = row['contenido'][:150].replace('\n', ' ')
                print(f"Contenido: {snippet}...")
        
        if len(noticias_objetivo) > 10:
            print(f"\n... y {len(noticias_objetivo) - 10} noticias mas")
    else:
        print("No se encontraron noticias objetivo.")
        print("Recomendacion: Ajustar parametros del detector o agregar mas fuentes RSS.")
    
    # ========================================================================
    # PASO 3: GUARDAR RESULTADOS
    # ========================================================================
    
    print_section("PASO 3: GUARDAR RESULTADOS", "-")
    
    # Guardar todas las noticias
    output_all = config.DATA_PATH
    df_noticias.to_csv(output_all, index=False, encoding='utf-8-sig')
    print(f"Todas las noticias guardadas en: {output_all}")
    
    # Guardar solo objetivo
    if len(noticias_objetivo) > 0:
        output_objetivo = str(config.DATA_DIR / 'noticias_objetivo.csv')
        noticias_objetivo.to_csv(output_objetivo, index=False, encoding='utf-8-sig')
        print(f"Noticias objetivo guardadas en: {output_objetivo}")
    
    # ========================================================================
    # RESUMEN Y RECOMENDACIONES
    # ========================================================================
    
    print_section("RESUMEN Y RECOMENDACIONES", "=")
    
    print("METRICAS:")
    print(f"  Tasa de exito: {objetivo/total*100:.1f}% noticias objetivo")
    print(f"  Eficiencia detector: Filtro {irrelevante} noticias irrelevantes")
    print()
    
    print("EVALUACION:")
    
    if objetivo / total < 0.10:
        print("  [!!] Muy pocas noticias objetivo (<10%)")
        print("       Recomendacion:")
        print("       - Agregar mas fuentes RSS especializadas")
        print("       - Ajustar query de Google News")
        print("       - Reducir umbral de confianza en detector")
    elif objetivo / total > 0.40:
        print("  [!!] Demasiadas noticias objetivo (>40%)")
        print("       Recomendacion:")
        print("       - Detector puede estar sobre-detectando")
        print("       - Revisar que no detecte falsos positivos")
    else:
        print("  [OK] Tasa de noticias objetivo es aceptable (10-40%)")
    
    print()
    
    if total < 50:
        print("  [!!] Pocas noticias recolectadas (<50)")
        print("       Recomendacion:")
        print("       - Agregar mas fuentes RSS")
        print("       - Aumentar max_results en Google News")
    else:
        print(f"  [OK] Recoleccion exitosa ({total} noticias)")
    
    print()
    print("VENTAJAS DE ESTE PIPELINE SIMPLE:")
    print("  - 3-5x mas rapido (sin procesamiento ML innecesario)")
    print("  - Resultados igual de precisos (detector es lo importante)")
    print("  - Mas facil de mantener y debuggear")
    print("  - Consume menos memoria")
    print()
    print("CUANDO USAR ML (TF-IDF, LDA, DBSCAN):")
    print("  - Si tienes >500 noticias objetivo")
    print("  - Si necesitas agrupar casos similares")
    print("  - Si quieres analizar temas/topicos")
    print("  - Si implementas 'noticias relacionadas' en dashboard")
    
    return noticias_objetivo


def main():
    """Función principal."""
    print()
    print("="*80)
    print(" ANALISIS SIMPLE - SISTEMA INTELIGENTE NNA")
    print(" Pipeline Optimizado (sin ML innecesario)")
    print(" ESIME Zacatenco - IPN")
    print("="*80)
    print()
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        noticias_objetivo = analizar_simple()
        
        print()
        print("="*80)
        print(" ANALISIS COMPLETADO EXITOSAMENTE")
        print("="*80)
        print()
        
        if len(noticias_objetivo) > 0:
            print(f"Se detectaron {len(noticias_objetivo)} noticias objetivo.")
            print(f"Revisa los archivos en: {config.DATA_DIR}")
        else:
            print("No se detectaron noticias objetivo.")
            print("Revisa las recomendaciones arriba.")
        
        print()
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
