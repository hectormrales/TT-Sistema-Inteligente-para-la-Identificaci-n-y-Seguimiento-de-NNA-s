"""
scripts/evaluar_poc_csv.py
Script para probar la PoC de extracción de roles con datos reales del CSV.
"""
import pandas as pd
import spacy
import sys
import os

# Asegurar que encuentre la PoC
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from poc_roles_victimas import analizar_roles_victimas

def evaluar_csv(ruta_csv: str, muestras_por_clase: int = 5):
    print(f"Cargando CSV: {ruta_csv}")
    df = pd.read_csv(ruta_csv)
    
    # Asegurar que no haya valores nulos
    df['titulo'] = df['titulo'].fillna('')
    df['contenido'] = df['contenido'].fillna('')
    df['texto_completo'] = df['titulo'] + " " + df['contenido']
    
    print("Cargando modelo spaCy es_core_news_lg...")
    nlp = spacy.load("es_core_news_lg")
    
    # Tomar muestras estratificadas según tu clasificador anterior
    muestras = pd.DataFrame()
    for clase in ['Alta', 'Media', 'Baja', 'No relevante']:
        # Filtrar por clase y tomar N muestras al azar
        subset = df[df['clasificacion_final'] == clase]
        if not subset.empty:
            n_samples = min(muestras_por_clase, len(subset))
            muestras = pd.concat([muestras, subset.sample(n_samples, random_state=42)])
            
    print(f"\nSe evaluarán {len(muestras)} noticias de tu base de datos.\n")
    print("="*80)
    
    # Evaluar
    for idx, row in muestras.iterrows():
        texto = row['texto_completo'][:1500] # Analizamos los primeros 1500 caracteres
        clase_anterior = row['clasificacion_final']
        
        # Ejecutar PoC
        es_valido, roles = analizar_roles_victimas(texto, nlp)
        
        # Mostrar resultados
        color_res = "\033[92m" if es_valido else "\033[91m"
        reset = "\033[0m"
        
        print(f"Noticia original: {clase_anterior} | Título: {row['titulo'][:80]}...")
        print(f"Resultado spaCy : {color_res}{es_valido}{reset}")
        
        if roles['victima_adulta']:
            print(f"  › Víctima adulta: {roles['victima_adulta']}")
        if roles['menor_superviviente']:
            print(f"  › Menor superviviente: {roles['menor_superviviente']}")
        if roles['menor_victima_directa']:
            print(f"  › ⚠ FALSO POSITIVO BLOQUEADO: Menor atacado")
        if roles['señales_orfandad']:
            print(f"  › Señales orfandad: {roles['señales_orfandad']}")
        
        print("-" * 80)

if __name__ == "__main__":
    # Ruta relativa desde la raíz del proyecto dentro del contenedor
    RUTA = "data/noticias_analyzed_simplified.csv" 
    
    if os.path.exists(RUTA):
        evaluar_csv(RUTA, muestras_por_clase=5)
    else:
        # Si sigue fallando, imprimimos la ruta absoluta para depurar
        print(f"No se encontró el archivo CSV en la ruta del contenedor: {os.path.abspath(RUTA)}")
        print("Archivos disponibles en la carpeta 'data/':")
        try:
            print(os.listdir("data"))
        except Exception as e:
            print(f"Tampoco se pudo leer la carpeta 'data': {e}")