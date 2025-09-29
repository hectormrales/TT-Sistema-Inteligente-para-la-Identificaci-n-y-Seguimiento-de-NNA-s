from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

def _pick_text_series(df: pd.DataFrame) -> pd.Series:
    """Selecciona la mejor columna de texto disponible para modelado.
    Prioriza 'contenido_limpio' y usa 'contenido' como respaldo.
    """
    if 'contenido_limpio' in df.columns:
        return df['contenido_limpio'].fillna('').astype(str)
    if 'contenido' in df.columns:
        return df['contenido'].fillna('').astype(str)
    raise KeyError("No se encontró 'contenido_limpio' ni 'contenido' en el DataFrame")

def build_tfidf(texts: List[str], max_features: int = 5000) -> Tuple[TfidfVectorizer, any]:
    """Crea el vectorizador TF-IDF y ajusta sobre los textos dados."""
    vectorizer = TfidfVectorizer(max_features=max_features)
    X = vectorizer.fit_transform(texts)
    return vectorizer, X

def run_kmeans(X, n_clusters: int = 5, random_state: int = 42) -> Tuple[KMeans, np.ndarray, float]:
    """Ejecuta KMeans y devuelve: modelo, labels y silhouette (si aplicable)."""
    km = KMeans(n_clusters=n_clusters, n_init='auto', random_state=random_state)
    labels = km.fit_predict(X)
    score = -1.0
    try:
        if X.shape[0] >= (n_clusters * 2):  # condición mínima razonable
            score = silhouette_score(X, labels, sample_size=min(10000, X.shape[0]))
    except Exception:
        pass
    return km, labels, float(score)

def top_terms_per_cluster(vectorizer: TfidfVectorizer, km: KMeans, top_n: int = 12) -> Dict[int, List[str]]:
    """Obtiene las top palabras por cluster según centroides de KMeans."""
    terms = vectorizer.get_feature_names_out()
    top_terms: Dict[int, List[str]] = {}
    centroids = km.cluster_centers_
    for k in range(km.n_clusters):
        idx = np.argsort(centroids[k])[::-1][:top_n]
        top_terms[k] = [terms[i] for i in idx]
    return top_terms

def cluster_dataframe(
    df: pd.DataFrame,
    n_clusters: int = 5,
    max_features: int = 5000,
    random_state: int = 42,
    top_n_terms: int = 12
) -> Tuple[pd.DataFrame, Dict]:
    """Clusterea el DataFrame en 'cluster' usando TF-IDF + KMeans.

    Devuelve:
      - df_out: copia del DF con columna 'cluster' (int)
      - info: dict con 'silhouette', 'top_terms' por cluster y 'n_clusters'
    """
    texts = _pick_text_series(df).tolist()
    vectorizer, X = build_tfidf(texts, max_features=max_features)
    km, labels, sil = run_kmeans(X, n_clusters=n_clusters, random_state=random_state)
    df_out = df.copy()
    df_out['cluster'] = labels
    info = {
        'silhouette': sil,
        'n_clusters': n_clusters,
        'top_terms': top_terms_per_cluster(vectorizer, km, top_n=top_n_terms)
    }
    return df_out, info
