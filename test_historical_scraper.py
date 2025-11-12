# -*- coding: utf-8 -*-
"""
Test del scraper histórico para encontrar noticias de feminicidios.
Este script busca en archivos y categorías específicas, no solo RSS.
"""

import sys
import os

# Configurar encoding para Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from src.collection.historical_scraper import collect_feminicide_news_historical
import pandas as pd

def main():
    print("="*80)
    print("TEST: SCRAPER HISTORICO DE FEMINICIDIOS")
    print("="*80)
    print("\nEste scraper busca en:")
    print("  1. Categorias de feminicidios en CIMAC")
    print("  2. Busqueda en SEM Mexico")
    print("  3. Google News (backup)")
    print("\nEsto es MAS EFECTIVO que solo RSS feeds...")
    print("="*80)
    
    # Recolectar noticias de los últimos 7 días
    df = collect_feminicide_news_historical(days_back=7)
    
    if len(df) > 0:
        # Guardar resultados
        output_file = 'data/noticias_historicas_feminicidios.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\nResultados guardados en: {output_file}")
        
        # Mostrar ejemplos de noticias OBJETIVO
        objetivo_df = df[df['es_objetivo'] == True]
        if len(objetivo_df) > 0:
            print("\n" + "="*80)
            print("EJEMPLOS DE NOTICIAS OBJETIVO (Feminicidio + NNA)")
            print("="*80)
            
            for idx, row in objetivo_df.head(5).iterrows():
                print(f"\n[{row['prioridad']}] Confianza: {row['confianza']:.0%}")
                print(f"Titulo: {row['titulo']}")
                print(f"Fuente: {row['fuente']}")
                print(f"NNA: {row['tiene_nna']} | Huerfanos: {row['tiene_huerfanos']}")
                print("-"*80)
        else:
            print("\nNo se encontraron noticias OBJETIVO esta semana.")
            print("Mostrando noticias de feminicidios sin mencion clara de NNA:")
            
            feminicidios_df = df[df['es_feminicidio'] == True]
            for idx, row in feminicidios_df.head(5).iterrows():
                print(f"\n[{row['prioridad']}] Confianza: {row['confianza']:.0%}")
                print(f"Titulo: {row['titulo']}")
                print(f"Fuente: {row['fuente']}")
                print("-"*80)
        
        print("\n" + "="*80)
        print("CONCLUSION:")
        print("="*80)
        
        if len(objetivo_df) > 0:
            print(f"EXITO: Se encontraron {len(objetivo_df)} noticias objetivo")
            print("El detector funciona correctamente.")
        else:
            print("Esta semana no hubo noticias que mencionen:")
            print("  Feminicidio + NNA (hijos/huerfanos) en el mismo articulo")
            print("\nPosibles razones:")
            print("  1. No hubo casos reportados esta semana")
            print("  2. Los medios no mencionaron a los hijos en el titular/resumen")
            print("  3. Necesitas ampliar a mas dias (days_back=14 o 30)")
        
        print("="*80)
        
    else:
        print("\nNo se encontraron noticias de feminicidios.")
        print("Esto puede deberse a problemas de conexion o cambios en los sitios web.")

if __name__ == "__main__":
    main()
