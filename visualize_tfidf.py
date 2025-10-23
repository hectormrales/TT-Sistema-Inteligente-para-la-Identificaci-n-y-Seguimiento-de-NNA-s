#!/usr/bin/env python3
"""
🔍 Script de Visualización de Matriz TF-IDF
============================================
Este script muestra la matriz TF-IDF y los pesos de palabras importantes
para validar que el sistema está asignando scores correctos.

Uso:
    python visualize_tfidf.py
    
Autor: Héctor Morales
Fecha: 23 de octubre de 2025
"""

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import warnings
warnings.filterwarnings('ignore')


def load_data():
    """Carga las noticias procesadas"""
    print("📂 Cargando datos...")
    try:
        df = pd.read_csv('data/noticias_analyzed_simplified.csv')
        print(f"✅ {len(df)} noticias cargadas")
        return df
    except FileNotFoundError:
        print("❌ No se encontró el archivo de análisis")
        print("💡 Ejecuta primero: python demo_docker.py")
        return None


def recreate_tfidf(df):
    """Recrea el vectorizador TF-IDF con los mismos parámetros"""
    print("\n🔢 Recreando vectorizador TF-IDF...")
    
    # Combinar título y contenido limpio
    texts = (df['titulo_limpio'].fillna('') + ' ' + df['contenido_limpio'].fillna('')).tolist()
    
    # Configuración idéntica a simplified_analyzer.py
    vectorizer = TfidfVectorizer(
        max_features=3000,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.8,
        strip_accents='unicode',
        lowercase=True,
        stop_words=None
    )
    
    # Generar matriz TF-IDF
    tfidf_matrix = vectorizer.fit_transform(texts)
    
    print(f"✅ Matriz TF-IDF creada: {tfidf_matrix.shape}")
    print(f"   📊 {tfidf_matrix.shape[0]} documentos")
    print(f"   📝 {tfidf_matrix.shape[1]} términos")
    print(f"   💾 Valores no-cero: {tfidf_matrix.nnz:,}")
    
    return vectorizer, tfidf_matrix


def show_top_words_global(vectorizer, tfidf_matrix, top_n=30):
    """Muestra las palabras con mayor score TF-IDF promedio en todo el corpus"""
    print("\n" + "="*80)
    print("🏆 TOP PALABRAS CON MAYOR TF-IDF PROMEDIO (TODO EL CORPUS)")
    print("="*80)
    
    # Calcular score promedio por palabra
    feature_names = vectorizer.get_feature_names_out()
    mean_tfidf = np.array(tfidf_matrix.mean(axis=0)).flatten()
    
    # Ordenar por score
    top_indices = mean_tfidf.argsort()[-top_n:][::-1]
    
    print(f"\n{'#':<4} {'PALABRA':<30} {'TF-IDF PROMEDIO':<20} {'BARRA'}")
    print("-"*80)
    
    max_score = mean_tfidf[top_indices[0]]
    for rank, idx in enumerate(top_indices, 1):
        word = feature_names[idx]
        score = mean_tfidf[idx]
        bar_length = int((score / max_score) * 40)
        bar = "█" * bar_length
        
        print(f"{rank:<4} {word:<30} {score:<20.6f} {bar}")
    
    print("-"*80)
    print("💡 Interpretación:")
    print("   - Scores altos = Palabras distintivas importantes")
    print("   - Scores bajos = Palabras comunes o poco informativas")


def show_nna_keywords_scores(vectorizer, tfidf_matrix):
    """Muestra scores TF-IDF de palabras clave relacionadas con NNA"""
    print("\n" + "="*80)
    print("🎯 SCORES DE PALABRAS CLAVE NNA")
    print("="*80)
    
    # Palabras clave que nos interesan
    keywords = [
        'niño', 'niña', 'niños', 'niñas',
        'menor', 'menores', 'menor edad',
        'adolescente', 'adolescentes',
        'feminicidio', 'femicidio',
        'desaparecido', 'desaparecidos', 'desaparecida', 'desaparición',
        'abuso', 'violencia', 'maltrato',
        'alerta amber', 'alerta',
        'jalisco', 'monterrey', 'méxico',
        'víctima', 'victima'
    ]
    
    feature_names = vectorizer.get_feature_names_out()
    mean_tfidf = np.array(tfidf_matrix.mean(axis=0)).flatten()
    
    # Crear diccionario palabra -> score
    word_scores = dict(zip(feature_names, mean_tfidf))
    
    print(f"\n{'PALABRA CLAVE':<25} {'TF-IDF PROMEDIO':<20} {'ESTADO':<15} {'BARRA'}")
    print("-"*80)
    
    found_words = []
    for keyword in keywords:
        if keyword in word_scores:
            score = word_scores[keyword]
            found_words.append((keyword, score))
    
    # Ordenar por score
    found_words.sort(key=lambda x: x[1], reverse=True)
    
    # Calcular percentiles
    all_scores = list(word_scores.values())
    p75 = np.percentile(all_scores, 75)
    p50 = np.percentile(all_scores, 50)
    p25 = np.percentile(all_scores, 25)
    
    max_score = found_words[0][1] if found_words else 1.0
    
    for word, score in found_words:
        bar_length = int((score / max_score) * 30)
        bar = "█" * bar_length
        
        # Clasificar el score
        if score > p75:
            status = "✅ EXCELENTE"
        elif score > p50:
            status = "✓ BUENO"
        elif score > p25:
            status = "⚠️  REGULAR"
        else:
            status = "❌ BAJO"
        
        print(f"{word:<25} {score:<20.6f} {status:<15} {bar}")
    
    # Palabras no encontradas
    not_found = set(keywords) - {w for w, _ in found_words}
    if not_found:
        print("\n⚠️  Palabras NO encontradas en vocabulario (eliminadas por min_df o max_df):")
        for word in sorted(not_found):
            print(f"   - {word}")
    
    print("-"*80)
    print("💡 Interpretación:")
    print(f"   - Percentil 75: {p75:.6f} (score alto)")
    print(f"   - Percentil 50: {p50:.6f} (score medio)")
    print(f"   - Percentil 25: {p25:.6f} (score bajo)")


def show_document_vectors(vectorizer, tfidf_matrix, df, doc_indices=[0, 10, 20]):
    """Muestra vectores TF-IDF de documentos específicos"""
    print("\n" + "="*80)
    print("📄 VECTORES TF-IDF DE DOCUMENTOS ESPECÍFICOS")
    print("="*80)
    
    feature_names = vectorizer.get_feature_names_out()
    
    for doc_idx in doc_indices:
        if doc_idx >= len(df):
            continue
        
        print(f"\n📰 DOCUMENTO #{doc_idx}")
        print(f"   Título: {df.iloc[doc_idx]['titulo'][:70]}...")
        print(f"   NNA: {'✅ SÍ' if df.iloc[doc_idx].get('menores_identificados') == 'Si' else '❌ NO'}")
        
        # Obtener vector del documento
        doc_vector = tfidf_matrix[doc_idx].toarray().flatten()
        
        # Palabras con score > 0
        non_zero_indices = np.where(doc_vector > 0)[0]
        word_scores = [(feature_names[i], doc_vector[i]) for i in non_zero_indices]
        word_scores.sort(key=lambda x: x[1], reverse=True)
        
        print(f"\n   Top 15 palabras con mayor peso TF-IDF:")
        print(f"   {'#':<4} {'PALABRA':<25} {'TF-IDF':<15} {'BARRA'}")
        print("   " + "-"*70)
        
        max_score = word_scores[0][1] if word_scores else 1.0
        for rank, (word, score) in enumerate(word_scores[:15], 1):
            bar_length = int((score / max_score) * 25)
            bar = "█" * bar_length
            print(f"   {rank:<4} {word:<25} {score:<15.6f} {bar}")
        
        print(f"\n   📊 Estadísticas del vector:")
        print(f"      - Palabras únicas: {len(word_scores)}")
        print(f"      - Score máximo: {doc_vector.max():.6f}")
        print(f"      - Score promedio: {doc_vector[doc_vector > 0].mean():.6f}")
        print(f"      - Dispersión (sparsity): {100 * (1 - len(word_scores)/len(feature_names)):.2f}%")


def show_tfidf_matrix_sample(vectorizer, tfidf_matrix, n_docs=5, n_words=10):
    """Muestra una muestra de la matriz TF-IDF completa"""
    print("\n" + "="*80)
    print("📊 MUESTRA DE MATRIZ TF-IDF COMPLETA")
    print("="*80)
    
    feature_names = vectorizer.get_feature_names_out()
    
    # Seleccionar palabras más frecuentes para la muestra
    mean_tfidf = np.array(tfidf_matrix.mean(axis=0)).flatten()
    top_word_indices = mean_tfidf.argsort()[-n_words:][::-1]
    top_words = [feature_names[i] for i in top_word_indices]
    
    # Convertir a array denso (solo muestra)
    matrix_sample = tfidf_matrix[:n_docs, top_word_indices].toarray()
    
    # Crear DataFrame para visualización
    df_matrix = pd.DataFrame(
        matrix_sample,
        columns=top_words,
        index=[f"Doc {i}" for i in range(n_docs)]
    )
    
    print(f"\nMatriz TF-IDF (primeros {n_docs} documentos × top {n_words} palabras):\n")
    
    # Mostrar con formato
    print(df_matrix.to_string(float_format=lambda x: f"{x:.4f}"))
    
    print(f"\n📐 Dimensiones completas: {tfidf_matrix.shape[0]} docs × {tfidf_matrix.shape[1]} palabras")
    print(f"💾 Valores no-cero: {tfidf_matrix.nnz:,} de {tfidf_matrix.shape[0] * tfidf_matrix.shape[1]:,} ({100*tfidf_matrix.nnz/(tfidf_matrix.shape[0]*tfidf_matrix.shape[1]):.2f}%)")


def compare_nna_vs_nonna(vectorizer, tfidf_matrix, df):
    """Compara scores TF-IDF entre noticias NNA vs no-NNA"""
    print("\n" + "="*80)
    print("🔍 COMPARACIÓN: NOTICIAS NNA vs NO-NNA")
    print("="*80)
    
    # Separar documentos
    nna_mask = df['menores_identificados'] == 'Si'
    nna_indices = np.where(nna_mask)[0]
    non_nna_indices = np.where(~nna_mask)[0]
    
    print(f"\n📊 Documentos:")
    print(f"   - Con NNA: {len(nna_indices)} noticias")
    print(f"   - Sin NNA: {len(non_nna_indices)} noticias")
    
    if len(nna_indices) == 0 or len(non_nna_indices) == 0:
        print("⚠️  No hay suficientes documentos para comparar")
        return
    
    # Calcular scores promedio por grupo
    feature_names = vectorizer.get_feature_names_out()
    nna_mean = np.array(tfidf_matrix[nna_indices].mean(axis=0)).flatten()
    non_nna_mean = np.array(tfidf_matrix[non_nna_indices].mean(axis=0)).flatten()
    
    # Calcular diferencias
    diff = nna_mean - non_nna_mean
    
    # Top palabras más distintivas de NNA
    top_nna_indices = diff.argsort()[-20:][::-1]
    
    print("\n🎯 TOP 20 PALABRAS MÁS DISTINTIVAS DE NOTICIAS NNA:")
    print(f"{'#':<4} {'PALABRA':<25} {'TF-IDF NNA':<15} {'TF-IDF NO-NNA':<15} {'DIFERENCIA':<15}")
    print("-"*80)
    
    for rank, idx in enumerate(top_nna_indices, 1):
        word = feature_names[idx]
        nna_score = nna_mean[idx]
        non_nna_score = non_nna_mean[idx]
        difference = diff[idx]
        
        print(f"{rank:<4} {word:<25} {nna_score:<15.6f} {non_nna_score:<15.6f} {difference:<15.6f}")
    
    print("-"*80)
    print("💡 Interpretación:")
    print("   - Diferencia positiva = Palabra más común en noticias NNA")
    print("   - Diferencia negativa = Palabra más común en noticias NO-NNA")


def main():
    """Función principal"""
    print("\n" + "="*80)
    print("🔍 VISUALIZACIÓN DE MATRIZ TF-IDF")
    print("   Sistema Inteligente para Identificación de NNA")
    print("="*80)
    
    # Cargar datos
    df = load_data()
    if df is None:
        return
    
    # Recrear TF-IDF
    vectorizer, tfidf_matrix = recreate_tfidf(df)
    
    # Visualizaciones
    show_top_words_global(vectorizer, tfidf_matrix, top_n=30)
    show_nna_keywords_scores(vectorizer, tfidf_matrix)
    show_document_vectors(vectorizer, tfidf_matrix, df, doc_indices=[0, 5, 10])
    show_tfidf_matrix_sample(vectorizer, tfidf_matrix, n_docs=5, n_words=12)
    compare_nna_vs_nonna(vectorizer, tfidf_matrix, df)
    
    # Resumen final
    print("\n" + "="*80)
    print("✅ ANÁLISIS COMPLETADO")
    print("="*80)
    print("\n💡 RECOMENDACIONES:")
    print("   1. Verifica que palabras clave NNA tengan scores altos")
    print("   2. Si scores son bajos, ajusta min_df/max_df en TfidfVectorizer")
    print("   3. Considera agregar stopwords específicas si ves palabras irrelevantes")
    print("   4. Analiza outliers en DBSCAN para casos únicos importantes")
    print("\n📊 Para visualizaciones gráficas, ejecuta: python visualize_tfidf_plots.py")
    print()


if __name__ == "__main__":
    main()
