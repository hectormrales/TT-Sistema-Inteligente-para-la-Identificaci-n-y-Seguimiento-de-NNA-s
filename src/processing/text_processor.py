# src/processing/text_processor.py
import re
from unicodedata import normalize

def clean_and_lemmatize_series(series):
    """Aplica la limpieza de texto básica a una Serie de pandas."""
    def process_text(text):
        if not isinstance(text, str):
            return ""
        # Limpieza básica del texto
        text = text.lower()
        text = normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')  # Quitar acentos
        text = re.sub(r'[^\w\s]', '', text)  # Quitar puntuación
        text = re.sub(r'\s+', ' ', text).strip()  # Normalizar espacios
        return text
    
    print("Limpiando texto...")
    return series.apply(process_text)