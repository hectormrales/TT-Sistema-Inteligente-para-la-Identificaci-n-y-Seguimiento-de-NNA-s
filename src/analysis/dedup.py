# src/analysis/dedup.py — Detección avanzada de duplicados cross-site
"""
Detecta noticias duplicadas o cuasi-duplicadas provenientes de
diferentes fuentes usando múltiples estrategias:

  1. Hash exacto       → título + contenido idénticos.
  2. Similitud de título → fuzzy matching de títulos (Jaccard).
  3. SimHash             → huellas digitales de contenido (near-duplicate).
  4. TF-IDF coseno       → similitud semántica con vectorización.

Se prioriza velocidad: primero filtros baratos, luego costosos.
"""

import re
import hashlib
import logging
from collections import defaultdict
from typing import Optional

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


# ── 1. Normalización de texto ───────────────────────────────

def _normalize_for_dedup(text: str) -> str:
    """Normaliza texto para comparación: minúsculas, sin puntuación."""
    if not isinstance(text, str):
        return ''
    text = text.lower().strip()
    # Quitar dominios y URLs
    text = re.sub(r'https?://\S+', '', text)
    # Quitar puntuación
    text = re.sub(r'[^\w\sáéíóúñü]', ' ', text)
    # Colapsar espacios
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _tokenize(text: str) -> set[str]:
    """Convierte texto normalizado en conjunto de tokens."""
    return set(_normalize_for_dedup(text).split())


# ── 2. Métricas de similitud ───────────────────────────────

def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Similitud de Jaccard entre dos textos tokenizados."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _simhash(text: str, hashbits: int = 64) -> int:
    """
    Genera un SimHash (locality-sensitive hash) de un texto.
    Documentos similares generan hashes con pocos bits de diferencia.
    """
    tokens = _normalize_for_dedup(text).split()
    if not tokens:
        return 0

    v = [0] * hashbits
    for token in tokens:
        h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
        for i in range(hashbits):
            bitmask = 1 << i
            if h & bitmask:
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(hashbits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def hamming_distance(hash1: int, hash2: int) -> int:
    """Distancia de Hamming entre dos hashes."""
    return bin(hash1 ^ hash2).count('1')


# ── 3. Deduplicador principal ──────────────────────────────

class NewsDeduplicator:
    """
    Detecta y elimina noticias duplicadas o cuasi-duplicadas.

    Estrategia en cascada (de más rápido a más preciso):
      1. Hash exacto de título normalizado.
      2. Jaccard de títulos (umbral configurable).
      3. SimHash de contenido completo (distancia de Hamming).
      4. TF-IDF + cosine similarity (solo si los pasos anteriores
         no son concluyentes).
    """

    def __init__(
        self,
        title_threshold: float = 0.70,
        content_threshold: float = 0.80,
        simhash_max_distance: int = 8,
    ):
        """
        Args:
            title_threshold: Jaccard mínimo para considerar títulos duplicados.
            content_threshold: Cosine similarity mínima para contenido duplicado.
            simhash_max_distance: Máx distancia de Hamming para SimHash.
        """
        self.title_threshold = title_threshold
        self.content_threshold = content_threshold
        self.simhash_max_distance = simhash_max_distance

    def deduplicate(
        self,
        df: pd.DataFrame,
        title_col: str = 'titulo',
        content_col: str = 'contenido',
        keep: str = 'first',
    ) -> pd.DataFrame:
        """
        Elimina duplicados de un DataFrame de noticias.

        Args:
            df: DataFrame con columnas de título y contenido.
            title_col: Nombre de la columna de títulos.
            content_col: Nombre de la columna de contenido.
            keep: 'first' conserva la primera aparición,
                  'best' conserva la con mayor score_compuesto.

        Returns:
            DataFrame sin duplicados + columna 'dedup_group' con el
            ID del grupo de duplicados.
        """
        if df.empty or len(df) < 2:
            return df.copy()

        logger.info(f"Deduplicación: {len(df)} noticias de entrada")

        # Preparar textos normalizados
        titles = df[title_col].fillna('').astype(str)
        contents = df[content_col].fillna('').astype(str)
        titles_norm = titles.apply(_normalize_for_dedup)
        contents_norm = contents.apply(_normalize_for_dedup)

        n = len(df)
        # Grupo de duplicados: cada noticia empieza en su propio grupo
        groups = list(range(n))

        # ── Paso 1: Hash exacto de título ──
        title_hash_groups = defaultdict(list)
        for i, t in enumerate(titles_norm):
            if t:
                h = hashlib.md5(t.encode()).hexdigest()
                title_hash_groups[h].append(i)

        exact_dupes = 0
        for indices in title_hash_groups.values():
            if len(indices) > 1:
                root = min(indices)
                for idx in indices:
                    groups[idx] = root
                exact_dupes += len(indices) - 1

        logger.info(f"  Paso 1 - Hash exacto título: {exact_dupes} duplicados")

        # ── Paso 2: Jaccard de títulos (solo pares no ya agrupados) ──
        jaccard_dupes = 0
        # Solo comparar pares que no son del mismo grupo
        checked = set()
        for i in range(n):
            if groups[i] != i:  # Ya agrupado
                continue
            for j in range(i + 1, n):
                if groups[j] != j:  # Ya agrupado
                    continue
                pair = (i, j)
                if pair in checked:
                    continue
                checked.add(pair)

                sim = jaccard_similarity(titles_norm.iloc[i], titles_norm.iloc[j])
                if sim >= self.title_threshold:
                    groups[j] = groups[i]
                    jaccard_dupes += 1

                # Optimización: limitar comparaciones
                if len(checked) > n * 5:
                    break

        logger.info(f"  Paso 2 - Jaccard títulos: {jaccard_dupes} duplicados")

        # ── Paso 3: SimHash de contenido ──
        simhashes = []
        for i in range(n):
            text = f"{titles_norm.iloc[i]} {contents_norm.iloc[i][:500]}"
            simhashes.append(_simhash(text))

        simhash_dupes = 0
        for i in range(n):
            if groups[i] != i:
                continue
            for j in range(i + 1, n):
                if groups[j] != j:
                    continue
                if groups[i] == groups[j]:
                    continue
                dist = hamming_distance(simhashes[i], simhashes[j])
                if dist <= self.simhash_max_distance:
                    groups[j] = groups[i]
                    simhash_dupes += 1

        logger.info(f"  Paso 3 - SimHash: {simhash_dupes} duplicados")

        # ── Paso 4: TF-IDF cosine similarity (solo no-agrupados) ──
        # Solo ejecutar si quedan bastantes noticias no-agrupadas
        unique_roots = set(groups)
        if len(unique_roots) > 5:
            tfidf_dupes = self._tfidf_dedup(
                df, titles_norm, contents_norm, groups
            )
            logger.info(f"  Paso 4 - TF-IDF cosine: {tfidf_dupes} duplicados")

        # ── Asignar grupos y elegir representante ──
        df_result = df.copy()
        df_result['dedup_group'] = groups

        # Resolver grupos transitivos
        for i in range(n):
            root = groups[i]
            while groups[root] != root:
                root = groups[root]
            groups[i] = root
        df_result['dedup_group'] = groups

        # Contar duplicados
        group_counts = df_result['dedup_group'].value_counts()
        n_groups = len(group_counts)
        n_duplicates = n - n_groups

        logger.info(
            f"  Resultado: {n} → {n_groups} únicos "
            f"({n_duplicates} duplicados eliminados)"
        )

        # Seleccionar representante de cada grupo
        if keep == 'best' and 'score_compuesto' in df_result.columns:
            # Conservar la noticia con mayor score
            idx_keep = (
                df_result.groupby('dedup_group')['score_compuesto']
                .idxmax()
            )
        else:
            # Conservar la primera aparición
            idx_keep = (
                df_result.groupby('dedup_group')
                .apply(lambda g: g.index[0])
            )

        df_deduped = df_result.loc[idx_keep].copy()
        df_deduped = df_deduped.drop(columns=['dedup_group'], errors='ignore')
        df_deduped = df_deduped.reset_index(drop=True)

        return df_deduped

    def _tfidf_dedup(
        self,
        df: pd.DataFrame,
        titles_norm: pd.Series,
        contents_norm: pd.Series,
        groups: list[int],
    ) -> int:
        """Fase TF-IDF: detecta duplicados semánticos."""
        n = len(df)
        dupes = 0

        # Crear textos combinados
        combined = [
            f"{titles_norm.iloc[i]} {contents_norm.iloc[i][:1000]}"
            for i in range(n)
        ]

        try:
            vectorizer = TfidfVectorizer(
                max_features=3000,
                ngram_range=(1, 2),
                min_df=1,
                max_df=0.9,
            )
            matrix = vectorizer.fit_transform(combined)

            # Calcular similitud por bloques para no agotar memoria
            block_size = 100
            for start in range(0, n, block_size):
                end = min(start + block_size, n)
                block = matrix[start:end]
                sims = cosine_similarity(block, matrix)

                for local_i in range(end - start):
                    global_i = start + local_i
                    if groups[global_i] != global_i:
                        continue

                    for j in range(global_i + 1, n):
                        if groups[j] != j:
                            continue
                        if groups[global_i] == groups[j]:
                            continue

                        if sims[local_i, j] >= self.content_threshold:
                            groups[j] = groups[global_i]
                            dupes += 1
        except Exception as e:
            logger.warning(f"Error en TF-IDF dedup: {e}")

        return dupes

    def find_similar_pairs(
        self,
        df: pd.DataFrame,
        title_col: str = 'titulo',
        content_col: str = 'contenido',
        min_similarity: float = 0.60,
    ) -> list[dict]:
        """
        Encuentra pares de noticias similares (para inspección manual).

        Returns:
            Lista de dicts con idx_a, idx_b, similarity, titles.
        """
        titles = df[title_col].fillna('').astype(str)
        contents = df[content_col].fillna('').astype(str)

        combined = [
            f"{_normalize_for_dedup(titles.iloc[i])} "
            f"{_normalize_for_dedup(contents.iloc[i][:500])}"
            for i in range(len(df))
        ]

        vectorizer = TfidfVectorizer(max_features=2000, ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(combined)
        sim_matrix = cosine_similarity(matrix)

        pairs = []
        for i in range(len(df)):
            for j in range(i + 1, len(df)):
                if sim_matrix[i, j] >= min_similarity:
                    pairs.append({
                        'idx_a': i,
                        'idx_b': j,
                        'similarity': round(float(sim_matrix[i, j]), 4),
                        'title_a': titles.iloc[i][:100],
                        'title_b': titles.iloc[j][:100],
                    })

        return sorted(pairs, key=lambda x: x['similarity'], reverse=True)
