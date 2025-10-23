#!/usr/bin/env python3
"""
📊 Script de Visualización Gráfica de TF-IDF
=============================================
Este script genera gráficas (heatmaps, distribuciones) de la matriz TF-IDF.

Uso:
    python visualize_tfidf_plots.py
    
Autor: Héctor Morales
Fecha: 23 de octubre de 2025
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.feature_extraction.text import TfidfVectorizer
import warnings
warnings.filterwarnings('ignore')

# Configurar estilo de gráficas
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


def load_data():
    """Carga las noticias procesadas"""
    print("📂 Cargando datos...")
    try:
        df = pd.read_csv('data/noticias_analyzed_simplified.csv')
        print(f"✅ {len(df)} noticias cargadas")
        return df
    except FileNotFoundError:
        print("❌ No se encontró el archivo de análisis")
        return None


def recreate_tfidf(df):
    """Recrea el vectorizador TF-IDF"""
    print("🔢 Recreando vectorizador TF-IDF...")
    
    texts = (df['titulo_limpio'].fillna('') + ' ' + df['contenido_limpio'].fillna('')).tolist()
    
    vectorizer = TfidfVectorizer(
        max_features=3000,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.8,
        strip_accents='unicode',
        lowercase=True,
        stop_words=None
    )
    
    tfidf_matrix = vectorizer.fit_transform(texts)
    print(f"✅ Matriz TF-IDF: {tfidf_matrix.shape}")
    
    return vectorizer, tfidf_matrix


def plot_top_words_distribution(vectorizer, tfidf_matrix):
    """Gráfica de barras con top palabras"""
    print("\n📊 Generando gráfica de top palabras...")
    
    feature_names = vectorizer.get_feature_names_out()
    mean_tfidf = np.array(tfidf_matrix.mean(axis=0)).flatten()
    
    # Top 25 palabras
    top_indices = mean_tfidf.argsort()[-25:][::-1]
    top_words = [feature_names[i] for i in top_indices]
    top_scores = mean_tfidf[top_indices]
    
    # Crear gráfica
    fig, ax = plt.subplots(figsize=(14, 8))
    
    bars = ax.barh(range(len(top_words)), top_scores, color='steelblue')
    ax.set_yticks(range(len(top_words)))
    ax.set_yticklabels(top_words)
    ax.invert_yaxis()
    ax.set_xlabel('TF-IDF Score Promedio', fontsize=12, fontweight='bold')
    ax.set_title('Top 25 Palabras con Mayor TF-IDF en el Corpus', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='x', alpha=0.3)
    
    # Agregar valores en las barras
    for i, (bar, score) in enumerate(zip(bars, top_scores)):
        ax.text(score + 0.0001, i, f'{score:.5f}', 
                va='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig('visualizations/top_words_tfidf.png', dpi=300, bbox_inches='tight')
    print("✅ Guardado: visualizations/top_words_tfidf.png")
    plt.close()


def plot_tfidf_heatmap(vectorizer, tfidf_matrix, n_docs=20, n_words=30):
    """Heatmap de matriz TF-IDF"""
    print("\n🔥 Generando heatmap de matriz TF-IDF...")
    
    feature_names = vectorizer.get_feature_names_out()
    mean_tfidf = np.array(tfidf_matrix.mean(axis=0)).flatten()
    
    # Seleccionar top palabras
    top_word_indices = mean_tfidf.argsort()[-n_words:][::-1]
    top_words = [feature_names[i] for i in top_word_indices]
    
    # Convertir a array denso
    matrix_sample = tfidf_matrix[:n_docs, top_word_indices].toarray()
    
    # Crear heatmap
    fig, ax = plt.subplots(figsize=(16, 10))
    
    sns.heatmap(matrix_sample.T, 
                xticklabels=[f'Doc {i}' for i in range(n_docs)],
                yticklabels=top_words,
                cmap='YlOrRd',
                cbar_kws={'label': 'TF-IDF Score'},
                linewidths=0.5,
                linecolor='gray',
                ax=ax)
    
    ax.set_title(f'Heatmap de Matriz TF-IDF\n({n_docs} documentos × {n_words} palabras top)', 
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Documentos', fontsize=12, fontweight='bold')
    ax.set_ylabel('Palabras', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('visualizations/tfidf_heatmap.png', dpi=300, bbox_inches='tight')
    print("✅ Guardado: visualizations/tfidf_heatmap.png")
    plt.close()


def plot_score_distribution(tfidf_matrix):
    """Histograma de distribución de scores TF-IDF"""
    print("\n📈 Generando distribución de scores...")
    
    # Obtener todos los valores no-cero
    non_zero_values = tfidf_matrix.data
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Histograma
    ax1.hist(non_zero_values, bins=50, color='skyblue', edgecolor='black', alpha=0.7)
    ax1.set_xlabel('TF-IDF Score', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Frecuencia', fontsize=11, fontweight='bold')
    ax1.set_title('Distribución de Scores TF-IDF (valores no-cero)', 
                  fontsize=12, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    
    # Agregar líneas de percentiles
    p25, p50, p75 = np.percentile(non_zero_values, [25, 50, 75])
    ax1.axvline(p25, color='orange', linestyle='--', linewidth=2, label=f'P25: {p25:.4f}')
    ax1.axvline(p50, color='red', linestyle='--', linewidth=2, label=f'P50: {p50:.4f}')
    ax1.axvline(p75, color='darkred', linestyle='--', linewidth=2, label=f'P75: {p75:.4f}')
    ax1.legend()
    
    # Boxplot
    ax2.boxplot(non_zero_values, vert=True)
    ax2.set_ylabel('TF-IDF Score', fontsize=11, fontweight='bold')
    ax2.set_title('Boxplot de Scores TF-IDF', fontsize=12, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('visualizations/tfidf_score_distribution.png', dpi=300, bbox_inches='tight')
    print("✅ Guardado: visualizations/tfidf_score_distribution.png")
    plt.close()


def plot_nna_keywords_comparison(vectorizer, tfidf_matrix):
    """Gráfica comparativa de palabras clave NNA"""
    print("\n🎯 Generando comparación de palabras clave NNA...")
    
    keywords = [
        'niño', 'niña', 'niños', 'niñas',
        'menor', 'menores', 
        'adolescente', 'adolescentes',
        'feminicidio', 
        'desaparecido', 'desaparecida',
        'abuso', 'violencia', 'maltrato',
        'víctima'
    ]
    
    feature_names = vectorizer.get_feature_names_out()
    mean_tfidf = np.array(tfidf_matrix.mean(axis=0)).flatten()
    word_scores = dict(zip(feature_names, mean_tfidf))
    
    # Filtrar palabras encontradas
    found = [(word, word_scores.get(word, 0)) for word in keywords if word in word_scores]
    
    if not found:
        print("⚠️  No se encontraron palabras clave en el vocabulario")
        return
    
    found.sort(key=lambda x: x[1], reverse=True)
    words, scores = zip(*found)
    
    # Crear gráfica
    fig, ax = plt.subplots(figsize=(12, 6))
    
    bars = ax.bar(range(len(words)), scores, color='coral', edgecolor='black', alpha=0.8)
    ax.set_xticks(range(len(words)))
    ax.set_xticklabels(words, rotation=45, ha='right')
    ax.set_ylabel('TF-IDF Score Promedio', fontsize=11, fontweight='bold')
    ax.set_title('Scores TF-IDF de Palabras Clave NNA', 
                 fontsize=13, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3)
    
    # Agregar valores
    for bar, score in zip(bars, scores):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.0001,
                f'{score:.5f}',
                ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig('visualizations/nna_keywords_scores.png', dpi=300, bbox_inches='tight')
    print("✅ Guardado: visualizations/nna_keywords_scores.png")
    plt.close()


def plot_sparsity_analysis(tfidf_matrix):
    """Análisis de dispersión (sparsity) de la matriz"""
    print("\n💎 Generando análisis de dispersión...")
    
    n_docs, n_features = tfidf_matrix.shape
    
    # Calcular sparsity por documento
    doc_sparsity = []
    for i in range(n_docs):
        row = tfidf_matrix[i]
        non_zero = row.nnz
        sparsity = 100 * (1 - non_zero / n_features)
        doc_sparsity.append(sparsity)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Histograma de sparsity
    ax1.hist(doc_sparsity, bins=30, color='lightgreen', edgecolor='black', alpha=0.7)
    ax1.set_xlabel('Sparsity (%)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Número de Documentos', fontsize=11, fontweight='bold')
    ax1.set_title('Distribución de Sparsity por Documento', 
                  fontsize=12, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    ax1.axvline(np.mean(doc_sparsity), color='red', linestyle='--', 
                linewidth=2, label=f'Media: {np.mean(doc_sparsity):.2f}%')
    ax1.legend()
    
    # Sparsity por documento
    ax2.plot(range(n_docs), doc_sparsity, marker='o', markersize=3, 
             linewidth=1, color='darkgreen', alpha=0.7)
    ax2.set_xlabel('Índice de Documento', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Sparsity (%)', fontsize=11, fontweight='bold')
    ax2.set_title('Sparsity por Documento Individual', 
                  fontsize=12, fontweight='bold')
    ax2.grid(alpha=0.3)
    
    # Agregar estadísticas
    global_sparsity = 100 * (1 - tfidf_matrix.nnz / (n_docs * n_features))
    ax2.text(0.02, 0.98, 
             f'Sparsity Global: {global_sparsity:.2f}%\n'
             f'Valores no-cero: {tfidf_matrix.nnz:,}\n'
             f'Total valores: {n_docs * n_features:,}',
             transform=ax2.transAxes,
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
             fontsize=10)
    
    plt.tight_layout()
    plt.savefig('visualizations/tfidf_sparsity_analysis.png', dpi=300, bbox_inches='tight')
    print("✅ Guardado: visualizations/tfidf_sparsity_analysis.png")
    plt.close()


def plot_nna_vs_nonna_comparison(vectorizer, tfidf_matrix, df):
    """Comparación visual entre documentos NNA y no-NNA"""
    print("\n🔍 Generando comparación NNA vs NO-NNA...")
    
    nna_mask = df['menores_identificados'] == 'Si'
    nna_indices = np.where(nna_mask)[0]
    non_nna_indices = np.where(~nna_mask)[0]
    
    if len(nna_indices) == 0 or len(non_nna_indices) == 0:
        print("⚠️  No hay suficientes documentos para comparar")
        return
    
    feature_names = vectorizer.get_feature_names_out()
    nna_mean = np.array(tfidf_matrix[nna_indices].mean(axis=0)).flatten()
    non_nna_mean = np.array(tfidf_matrix[non_nna_indices].mean(axis=0)).flatten()
    
    # Calcular diferencias
    diff = nna_mean - non_nna_mean
    
    # Top palabras distintivas
    top_nna_indices = diff.argsort()[-15:][::-1]
    top_nna_words = [feature_names[i] for i in top_nna_indices]
    nna_scores = nna_mean[top_nna_indices]
    non_nna_scores = non_nna_mean[top_nna_indices]
    
    # Crear gráfica
    fig, ax = plt.subplots(figsize=(12, 7))
    
    x = np.arange(len(top_nna_words))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, nna_scores, width, label='Noticias NNA', 
                   color='indianred', alpha=0.8)
    bars2 = ax.bar(x + width/2, non_nna_scores, width, label='Noticias NO-NNA', 
                   color='steelblue', alpha=0.8)
    
    ax.set_xlabel('Palabras', fontsize=11, fontweight='bold')
    ax.set_ylabel('TF-IDF Score Promedio', fontsize=11, fontweight='bold')
    ax.set_title('Comparación: Palabras Distintivas de Noticias NNA', 
                 fontsize=13, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(top_nna_words, rotation=45, ha='right')
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('visualizations/nna_vs_nonna_comparison.png', dpi=300, bbox_inches='tight')
    print("✅ Guardado: visualizations/nna_vs_nonna_comparison.png")
    plt.close()


def main():
    """Función principal"""
    print("\n" + "="*80)
    print("📊 VISUALIZACIÓN GRÁFICA DE MATRIZ TF-IDF")
    print("   Sistema Inteligente para Identificación de NNA")
    print("="*80)
    
    # Crear directorio de visualizaciones
    import os
    os.makedirs('visualizations', exist_ok=True)
    
    # Cargar datos
    df = load_data()
    if df is None:
        return
    
    # Recrear TF-IDF
    vectorizer, tfidf_matrix = recreate_tfidf(df)
    
    # Generar todas las visualizaciones
    print("\n🎨 Generando visualizaciones...")
    plot_top_words_distribution(vectorizer, tfidf_matrix)
    plot_tfidf_heatmap(vectorizer, tfidf_matrix, n_docs=20, n_words=30)
    plot_score_distribution(tfidf_matrix)
    plot_nna_keywords_comparison(vectorizer, tfidf_matrix)
    plot_sparsity_analysis(tfidf_matrix)
    plot_nna_vs_nonna_comparison(vectorizer, tfidf_matrix, df)
    
    # Resumen
    print("\n" + "="*80)
    print("✅ VISUALIZACIONES COMPLETADAS")
    print("="*80)
    print("\n📂 Archivos generados en carpeta 'visualizations/':")
    print("   1. top_words_tfidf.png - Top palabras del corpus")
    print("   2. tfidf_heatmap.png - Heatmap de matriz TF-IDF")
    print("   3. tfidf_score_distribution.png - Distribución de scores")
    print("   4. nna_keywords_scores.png - Scores de palabras clave NNA")
    print("   5. tfidf_sparsity_analysis.png - Análisis de dispersión")
    print("   6. nna_vs_nonna_comparison.png - Comparación NNA vs NO-NNA")
    print("\n💡 Abre estos archivos para validar que las palabras importantes")
    print("   están recibiendo los scores TF-IDF correctos.")
    print()


if __name__ == "__main__":
    main()
