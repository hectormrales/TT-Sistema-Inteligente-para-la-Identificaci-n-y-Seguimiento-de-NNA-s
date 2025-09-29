# src/utils/file_handler.py
import pandas as pd
import os

def save_to_csv(dataframe, path):
    """Guarda un DataFrame de pandas en una ruta específica."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dataframe.to_csv(path, index=False, encoding='utf-8-sig')
    print(f"Datos guardados exitosamente en {path}")

def load_from_csv(path):
    """Carga un DataFrame de pandas desde una ruta."""
    print(f"Cargando datos desde {path}...")
    return pd.read_csv(path)