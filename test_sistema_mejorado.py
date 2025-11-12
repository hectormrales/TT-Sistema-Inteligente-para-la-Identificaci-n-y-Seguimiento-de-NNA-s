# -*- coding: utf-8 -*-
"""
Script de prueba del sistema completo con las correcciones implementadas.

Este script ejecuta el pipeline completo con las siguientes mejoras:
1.  Fuentes RSS especializadas en feminicidios
2.  Detector especializado de feminicidios con NNA
3.  TF-IDF ajustado (min_df=1, stopwords espaol, sin strip_accents)
4.  DBSCAN ms permisivo (eps=0.6, min_samples=2)

Autor: Hctor Morales
Fecha: 12 de noviembre de 2025
"""

import sys
import os

# Configurar salida UTF-8 para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from analysis.simplified_analyzer import SimplifiedNewsAnalyzer
import pandas as pd

def print_separator(title=""):
    """Imprime separador visual."""
    print("\n" + "="*80)
    if title:
        print(f"  {title}")
        print("="*80)

def test_complete_pipeline():
    """Prueba el pipeline completo con las correcciones."""
    
    print_separator(" SISTEMA MEJORADO: DETECCIN DE FEMINICIDIOS CON NNA")
    print("\n Correcciones implementadas:")
    print("   1.  Fuentes RSS especializadas (CIMAC, SEM Mxico, etc.)")
    print("   2.  Detector de feminicidios con patrones especficos")
    print("   3.  TF-IDF ajustado (min_df=1, stopwords espaol)")
    print("   4.  DBSCAN ms permisivo (eps=0.6, min_samples=2)")
    
    # Inicializar analizador
    analyzer = SimplifiedNewsAnalyzer()
    
    # Ejecutar pipeline completo
    print_separator("EJECUTANDO PIPELINE COMPLETO")
    
    try:
        df_final = analyzer.run_complete_analysis(
            num_topics=6,
            clustering_method='dbscan',
            eps=0.6,           # CORREGIDO: era 0.4
            min_samples=2,     # CORREGIDO: era 3
            save_intermediate=True
        )
        
        print_separator(" PIPELINE COMPLETADO EXITOSAMENTE")
        
        # Estadsticas finales
        print_statistics(df_final)
        
        # Mostrar ejemplos de noticias objetivo
        show_target_news_examples(df_final)
        
        # Mostrar anlisis de clusters
        show_cluster_analysis(df_final)
        
        # Guardar reporte final
        save_final_report(df_final)
        
        return df_final
        
    except Exception as e:
        print(f"\n Error en pipeline: {e}")
        import traceback
        traceback.print_exc()
        return None

def print_statistics(df):
    """Imprime estadsticas detalladas."""
    print_separator(" ESTADSTICAS GENERALES")
    
    total = len(df)
    print(f"\n Total de noticias: {total}")
    
    if 'es_feminicidio' in df.columns:
        feminicides = df['es_feminicidio'].sum()
        print(f" Noticias de feminicidio: {feminicides} ({feminicides/total*100:.1f}%)")
    
    if 'tiene_nna' in df.columns:
        with_nna = df['tiene_nna'].sum()
        print(f" Con mencin de NNA: {with_nna} ({with_nna/total*100:.1f}%)")
    
    if 'tiene_huerfanos' in df.columns:
        with_orphans = df['tiene_huerfanos'].sum()
        print(f" Con mencin de hurfanos: {with_orphans} ({with_orphans/total*100:.1f}%)")
    
    if 'es_objetivo' in df.columns:
        target = df['es_objetivo'].sum()
        print(f"\n NOTICIAS OBJETIVO (feminicidio+NNA): {target} ({target/total*100:.1f}%)")
        
        if target / total >= 0.50:
            print("    EXCELENTE: Ms del 50% son noticias objetivo")
        elif target / total >= 0.30:
            print("    ACEPTABLE: Ms del 30% son noticias objetivo")
        elif target / total >= 0.10:
            print("     BAJO: Menos del 30% son noticias objetivo")
        else:
            print("    CRTICO: Menos del 10% son noticias objetivo")
            print("       Considera agregar ms fuentes especializadas")
    
    if 'prioridad' in df.columns:
        print(f"\n Por prioridad:")
        for priority in ['ALTA', 'MEDIA', 'BAJA', 'IRRELEVANTE']:
            count = len(df[df['prioridad'] == priority])
            print(f"   - {priority}: {count} ({count/total*100:.1f}%)")
    
    if 'confianza' in df.columns:
        avg_confidence = df['confianza'].mean()
        print(f"\n Confianza promedio: {avg_confidence:.1%}")
        
        if 'es_objetivo' in df.columns:
            target_df = df[df['es_objetivo'] == True]
            if len(target_df) > 0:
                target_confidence = target_df['confianza'].mean()
                print(f"   (Solo noticias objetivo: {target_confidence:.1%})")
    
    if 'cluster' in df.columns:
        clusters = df[df['cluster'] != -1]['cluster'].nunique()
        outliers = len(df[df['cluster'] == -1])
        print(f"\n Clusters detectados: {clusters}")
        print(f"   Noticias en clusters: {total - outliers}")
        print(f"   Outliers (casos atpicos): {outliers}")

def show_target_news_examples(df):
    """Muestra ejemplos de noticias objetivo."""
    print_separator(" EJEMPLOS DE NOTICIAS OBJETIVO (PRIORIDAD ALTA)")
    
    if 'prioridad' not in df.columns:
        print("\n  No hay informacin de prioridad disponible")
        return
    
    high_priority = df[df['prioridad'] == 'ALTA'].head(5)
    
    if len(high_priority) == 0:
        print("\n No se encontraron noticias de PRIORIDAD ALTA")
        print("   Posibles causas:")
        print("   - Las fuentes RSS an no tienen suficiente cobertura de feminicidios")
        print("   - Se necesita agregar ms fuentes especializadas")
        
        # Mostrar ejemplos de prioridad MEDIA como alternativa
        medium_priority = df[df['prioridad'] == 'MEDIA'].head(3)
        if len(medium_priority) > 0:
            print("\n Ejemplos de PRIORIDAD MEDIA (segunda mejor opcin):")
            for idx, row in medium_priority.iterrows():
                print(f"\n   Noticia #{idx + 1}:")
                print(f"   Ttulo: {row.get('titulo', 'N/A')[:80]}")
                print(f"   Fuente: {row.get('fuente', 'N/A')}")
                print(f"   Confianza: {row.get('confianza', 0):.1%}")
                print(f"   Feminicidio: {'' if row.get('es_feminicidio', False) else ''}")
                print(f"   NNA: {'' if row.get('tiene_nna', False) else ''}")
                print(f"   Hurfanos: {'' if row.get('tiene_huerfanos', False) else ''}")
    else:
        for idx, row in high_priority.iterrows():
            print(f"\n Noticia #{idx + 1}:")
            print(f"   Ttulo: {row.get('titulo', 'N/A')[:80]}")
            print(f"   Fuente: {row.get('fuente', 'N/A')}")
            print(f"   Confianza: {row.get('confianza', 0):.1%}")
            print(f"   Feminicidio: {'' if row.get('es_feminicidio', False) else ''}")
            print(f"   NNA: {'' if row.get('tiene_nna', False) else ''}")
            print(f"   Hurfanos: {'' if row.get('tiene_huerfanos', False) else ''}")
            if 'cluster' in row:
                print(f"   Cluster: {row['cluster']}")

def show_cluster_analysis(df):
    """Muestra anlisis de clusters."""
    print_separator(" ANLISIS DE CLUSTERS")
    
    if 'cluster' not in df.columns:
        print("\n  No hay informacin de clusters disponible")
        return
    
    clusters = df[df['cluster'] != -1]['cluster'].unique()
    
    if len(clusters) == 0:
        print("\n  No se formaron clusters (todas las noticias son outliers)")
        print("   Esto puede indicar:")
        print("   - Noticias muy diversas sin temas comunes")
        print("   - Se necesitan ms noticias sobre temas similares")
        return
    
    print(f"\n Se formaron {len(clusters)} clusters")
    
    for cluster_id in sorted(clusters)[:5]:  # Mostrar primeros 5
        cluster_news = df[df['cluster'] == cluster_id]
        n_news = len(cluster_news)
        
        print(f"\n Cluster {cluster_id}: {n_news} noticias")
        
        if 'es_objetivo' in df.columns:
            n_target = cluster_news['es_objetivo'].sum()
            print(f"   Noticias objetivo: {n_target} ({n_target/n_news*100:.0f}%)")
        
        # Mostrar ejemplo de ttulo
        example = cluster_news.iloc[0]
        print(f"   Ejemplo: {example.get('titulo', 'N/A')[:60]}...")

def save_final_report(df):
    """Guarda reporte final en CSV."""
    output_path = 'data/noticias_sistema_mejorado.csv'
    
    try:
        df.to_csv(output_path, index=False, encoding='utf-8')
        print_separator(" REPORTE GUARDADO")
        print(f"\n Datos guardados en: {output_path}")
        print(f" Total de registros: {len(df)}")
        
        # Listar columnas disponibles
        print(f"\n Columnas disponibles ({len(df.columns)}):")
        for col in df.columns:
            print(f"   - {col}")
    
    except Exception as e:
        print(f"\n Error guardando reporte: {e}")

def compare_with_previous():
    """Compara resultados con sistema anterior."""
    print_separator(" COMPARACIN CON SISTEMA ANTERIOR")
    
    old_file = 'data/noticias_analyzed_with_new_detector.csv'
    new_file = 'data/noticias_sistema_mejorado.csv'
    
    if not os.path.exists(old_file):
        print("\n  No se encontr archivo de comparacin anterior")
        return
    
    if not os.path.exists(new_file):
        print("\n  Ejecuta primero el pipeline para generar datos nuevos")
        return
    
    df_old = pd.read_csv(old_file)
    df_new = pd.read_csv(new_file)
    
    print(f"\n Sistema ANTERIOR:")
    print(f"   Total noticias: {len(df_old)}")
    if 'es_objetivo' in df_old.columns:
        old_target = df_old['es_objetivo'].sum()
        print(f"   Noticias objetivo: {old_target} ({old_target/len(df_old)*100:.1f}%)")
    
    print(f"\n Sistema MEJORADO:")
    print(f"   Total noticias: {len(df_new)}")
    if 'es_objetivo' in df_new.columns:
        new_target = df_new['es_objetivo'].sum()
        print(f"   Noticias objetivo: {new_target} ({new_target/len(df_new)*100:.1f}%)")
        
        if 'es_objetivo' in df_old.columns:
            improvement = new_target - old_target
            if improvement > 0:
                print(f"\n MEJORA: +{improvement} noticias objetivo")
            elif improvement < 0:
                print(f"\n  Disminucin: {improvement} noticias objetivo")
            else:
                print(f"\n  Sin cambio en cantidad")

if __name__ == "__main__":
    print("\n" + "="*80)
    print("PRUEBA COMPLETA DEL SISTEMA MEJORADO")
    print("="*80 + "\n")
    
    # Ejecutar pipeline
    df_result = test_complete_pipeline()
    
    if df_result is not None:
        print_separator(" PRUEBA COMPLETADA")
        print("\n Archivos generados:")
        print("   - data/noticias_raw.csv (datos originales)")
        print("   - data/noticias.csv (datos procesados)")
        print("   - data/noticias_sistema_mejorado.csv (resultado final)")
        
        # Comparar con sistema anterior si existe
        print("\n")
        compare_with_previous()
        
        print("\n Sistema listo para uso en produccin")
    else:
        print_separator(" PRUEBA FALLIDA")
        print("\nRevisa los errores anteriores para ms detalles")

