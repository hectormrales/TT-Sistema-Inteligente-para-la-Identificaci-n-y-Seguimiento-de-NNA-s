#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Análisis Detallado del Pipeline Completo
===================================================

Este script ejecuta el sistema completo mostrando en CADA PASO:
- ¿Qué hace?
- ¿Por qué es necesario?
- ¿Qué parámetros usa?
- ¿Qué palabras/valores considera?
- ¿Está dando resultados esperados?

Autor: Héctor Morales
Fecha: 18 de noviembre de 2025
"""

import sys
import os

# Configurar encoding UTF-8 para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json

# Agregar src al path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.collection.data_collector import collect_all_news
from src.collection.feminicide_detector import FeminicideDetector
from src.analysis.simplified_analyzer import SimplifiedNewsAnalyzer
import config


def print_section(title, char="="):
    """Imprime una sección visual."""
    print(f"\n{char * 80}")
    print(f" {title}")
    print(f"{char * 80}\n")


def print_subsection(title):
    """Imprime una subsección."""
    print(f"\n{'─' * 80}")
    print(f"▸ {title}")
    print(f"{'─' * 80}\n")


class PipelineAnalyzer:
    """Analiza y documenta cada paso del pipeline."""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'steps': []
        }
    
    def step_1_recoleccion(self):
        """
        PASO 1: RECOLECCIÓN DE NOTICIAS
        ¿Qué hace? Busca noticias en internet desde fuentes especializadas
        ¿Por qué? Necesitamos datos frescos sobre feminicidios
        """
        print_section("PASO 1: RECOLECCIÓN DE NOTICIAS", "=")
        
        print("📌 ¿QUÉ HACE ESTE PASO?")
        print("   Busca y descarga noticias de 2 fuentes:")
        print("   1. RSS Feeds de medios especializados (8 fuentes)")
        print("   2. Google News con búsqueda específica")
        print()
        
        print("📌 ¿POR QUÉ ES NECESARIO?")
        print("   Sin noticias no hay nada que analizar. Este es el inicio de todo.")
        print()
        
        print("📌 PARÁMETROS QUE USA:")
        print(f"   • RSS Feeds configurados: {len(config.RSS_FEEDS)}")
        for i, feed in enumerate(config.RSS_FEEDS, 1):
            print(f"     {i}. {feed[:60]}...")
        
        google_config = config.GOOGLE_NEWS_CONFIG
        print(f"\n   • Google News:")
        print(f"     - Query: '{google_config['query']}'")
        print(f"     - Max resultados: {google_config['max_results']}")
        print()
        
        print("🔄 EJECUTANDO RECOLECCIÓN...")
        df_noticias = collect_all_news(use_google_news=True)
        
        print("\n✅ RESULTADOS DE RECOLECCIÓN:")
        print(f"   Total noticias: {len(df_noticias)}")
        
        if len(df_noticias) > 0:
            feminicidios = df_noticias['es_feminicidio'].sum()
            objetivo = df_noticias['es_objetivo'].sum()
            alta = len(df_noticias[df_noticias['prioridad'] == 'ALTA'])
            
            print(f"   • Feminicidios detectados: {feminicidios} ({feminicidios/len(df_noticias)*100:.1f}%)")
            print(f"   • Noticias OBJETIVO: {objetivo} ({objetivo/len(df_noticias)*100:.1f}%)")
            print(f"   • Prioridad ALTA: {alta}")
            
            print("\n📊 EJEMPLOS DE NOTICIAS RECOLECTADAS:")
            for idx, row in df_noticias.head(3).iterrows():
                print(f"\n   Noticia {idx + 1}:")
                print(f"   Título: {row['titulo'][:70]}...")
                print(f"   Fuente: {row['fuente']}")
                print(f"   Es feminicidio: {row['es_feminicidio']}")
                print(f"   Tiene NNA: {row['tiene_nna']}")
                print(f"   Prioridad: {row['prioridad']}")
                print(f"   Confianza: {row['confianza']:.1%}")
        
        print("\n❓ ¿ESTÁ DANDO RESULTADOS ESPERADOS?")
        if len(df_noticias) < 50:
            print("   ⚠️  ADVERTENCIA: Pocas noticias recolectadas (<50)")
            print("   💡 RECOMENDACIÓN: Agregar más fuentes RSS")
        elif objetivo / len(df_noticias) < 0.10:
            print(f"   ⚠️  ADVERTENCIA: Solo {objetivo/len(df_noticias)*100:.1f}% son noticias objetivo")
            print("   💡 RECOMENDACIÓN: Ajustar query de Google News o agregar fuentes especializadas")
        else:
            print("   ✅ La recolección está funcionando bien")
        
        self.results['steps'].append({
            'step': 1,
            'name': 'Recolección',
            'total_noticias': len(df_noticias),
            'feminicidios': int(feminicidios) if len(df_noticias) > 0 else 0,
            'objetivo': int(objetivo) if len(df_noticias) > 0 else 0
        })
        
        return df_noticias
    
    def step_2_detector(self, df_noticias):
        """
        PASO 2: DETECTOR DE FEMINICIDIOS
        ¿Qué hace? Analiza cada noticia con patrones especializados
        ¿Por qué? Filtra solo las noticias relevantes (feminicidio + NNA)
        """
        print_section("PASO 2: DETECTOR DE FEMINICIDIOS", "=")
        
        print("📌 ¿QUÉ HACE ESTE PASO?")
        print("   Usa más de 40 patrones regex para detectar:")
        print("   1. Palabras de feminicidio (peso 40%)")
        print("   2. Palabras de NNA/hijos (peso 20%)")
        print("   3. Palabras de orfandad (peso 30% + 10% bonus)")
        print()
        
        print("📌 ¿POR QUÉ ES NECESARIO?")
        print("   No todas las noticias recolectadas son sobre feminicidios con NNA.")
        print("   Este paso FILTRA solo las relevantes antes del análisis ML.")
        print()
        
        detector = FeminicideDetector()
        
        print("📌 PATRONES QUE USA:")
        print(f"\n   🔴 FEMINICIDIO ({len(detector.feminicide_patterns)} patrones):")
        for i, pattern in enumerate(detector.feminicide_patterns[:5], 1):
            print(f"      {i}. {pattern}")
        print(f"      ... y {len(detector.feminicide_patterns) - 5} patrones más")
        
        print(f"\n   👶 NNA/HIJOS ({len(detector.children_patterns)} patrones):")
        for i, pattern in enumerate(detector.children_patterns[:5], 1):
            print(f"      {i}. {pattern}")
        
        print(f"\n   💔 ORFANDAD ({len(detector.orphan_patterns)} patrones):")
        for i, pattern in enumerate(detector.orphan_patterns[:5], 1):
            print(f"      {i}. {pattern}")
        print(f"      ... y {len(detector.orphan_patterns) - 5} patrones más")
        
        print("\n📊 ANÁLISIS DE EJEMPLO:")
        # Analizar primera noticia objetivo
        objetivo_news = df_noticias[df_noticias['es_objetivo'] == True]
        
        if len(objetivo_news) > 0:
            ejemplo = objetivo_news.iloc[0]
            texto = f"{ejemplo['titulo']} {ejemplo['contenido']}"
            resultado = detector.detect(texto)
            
            print(f"\n   Noticia: {ejemplo['titulo'][:70]}...")
            print(f"\n   Análisis del detector:")
            print(f"   • Es feminicidio: {resultado['is_feminicide']}")
            print(f"   • Tiene NNA: {resultado['has_children']}")
            print(f"   • Tiene huérfanos: {resultado['has_orphans']}")
            print(f"   • Es OBJETIVO: {resultado['is_target_news']}")
            print(f"   • Confianza: {resultado['confidence']:.1%}")
            print(f"   • Prioridad: {resultado['priority']}")
            
            print(f"\n   Desglose de coincidencias:")
            print(f"   • Patrones feminicidio: {len(resultado['matched_patterns']['feminicide'])}")
            print(f"   • Patrones NNA: {len(resultado['matched_patterns']['children'])}")
            print(f"   • Patrones orfandad: {len(resultado['matched_patterns']['orphans'])}")
            print(f"   • Patrones refuerzo: {len(resultado['matched_patterns']['reinforcing'])}")
            print(f"\n   Confianza TOTAL: {resultado['confidence']:.2%}")
        
        print("\n❓ ¿ESTÁ DANDO RESULTADOS ESPERADOS?")
        if len(df_noticias) > 0:
            precision_estimada = df_noticias['es_objetivo'].sum() / len(df_noticias)
            
            if precision_estimada < 0.10:
                print(f"   ⚠️  ADVERTENCIA: Solo {precision_estimada*100:.1f}% son noticias objetivo")
                print("   💡 RECOMENDACIÓN: Los patrones son muy estrictos, considerar:")
                print("      - Reducir umbral de confianza ALTA (actualmente 70%)")
                print("      - Agregar más patrones de orfandad")
            elif precision_estimada > 0.50:
                print(f"   ⚠️  ADVERTENCIA: {precision_estimada*100:.1f}% son objetivo (muy alto)")
                print("   💡 RECOMENDACIÓN: Puede estar sobre-detectando, verificar:")
                print("      - Revisar que no detecte casos no relacionados")
                print("      - Aumentar umbral de confianza")
            else:
                print(f"   ✅ Detector bien calibrado ({precision_estimada*100:.1f}% objetivo)")
        
        return df_noticias
    
    def step_3_vectorizacion(self, df_noticias):
        """
        PASO 3: VECTORIZACIÓN TF-IDF
        ¿Qué hace? Convierte texto en números que la computadora puede analizar
        ¿Por qué? Los algoritmos ML solo entienden números, no palabras
        """
        print_section("PASO 3: VECTORIZACIÓN TF-IDF", "=")
        
        print("📌 ¿QUÉ HACE ESTE PASO?")
        print("   Convierte cada noticia en un VECTOR de números.")
        print("   Cada dimensión del vector representa la 'importancia' de una palabra.")
        print()
        
        print("📌 ¿POR QUÉ ES NECESARIO?")
        print("   Los algoritmos de Machine Learning NO entienden palabras.")
        print("   Solo entienden NÚMEROS.")
        print("   TF-IDF transforma: 'feminicidio en Edomex' → [0.8, 0.3, 0.0, ...]")
        print()
        
        tfidf_config = config.TFIDF_CONFIG
        print("📌 PARÁMETROS QUE USA:")
        print(f"   • max_features: {tfidf_config['max_features']}")
        print(f"     └─ Solo considera las {tfidf_config['max_features']} palabras más importantes")
        print(f"\n   • min_df: {tfidf_config['min_df']}")
        print(f"     └─ Palabra debe aparecer mínimo {tfidf_config['min_df']} vez(ces)")
        print(f"\n   • max_df: {tfidf_config['max_df']}")
        print(f"     └─ Ignora palabras que aparecen en más del {tfidf_config['max_df']*100}% de docs")
        print(f"\n   • ngram_range: {tfidf_config['ngram_range']}")
        print(f"     └─ Considera palabras individuales (1) y pares (2)")
        print()
        
        print("🔄 EJECUTANDO VECTORIZACIÓN...")
        analyzer = SimplifiedNewsAnalyzer()
        analyzer.df_original = df_noticias
        analyzer.step_3_vectorize_text()
        
        print(f"\n✅ MATRIZ TF-IDF CREADA:")
        print(f"   Dimensiones: {analyzer.tfidf_matrix.shape}")
        print(f"   • {analyzer.tfidf_matrix.shape[0]} noticias (filas)")
        print(f"   • {analyzer.tfidf_matrix.shape[1]} palabras únicas (columnas)")
        print()
        
        # Mostrar palabras más importantes
        feature_names = analyzer.vectorizer.get_feature_names_out()
        
        print("📊 PALABRAS CON MAYOR PESO GLOBAL:")
        # Calcular suma de cada columna
        col_sums = np.asarray(analyzer.tfidf_matrix.sum(axis=0)).flatten()
        top_indices = col_sums.argsort()[::-1][:20]
        
        print("\n   Top 20 palabras más relevantes:")
        for i, idx in enumerate(top_indices, 1):
            palabra = feature_names[idx]
            peso = col_sums[idx]
            print(f"   {i:2d}. '{palabra}' (peso total: {peso:.2f})")
        
        # Mostrar ejemplo de vector
        print("\n📊 EJEMPLO DE VECTORIZACIÓN:")
        if len(df_noticias) > 0:
            idx_ejemplo = 0
            noticia_vector = analyzer.tfidf_matrix[idx_ejemplo].toarray().flatten()
            palabras_con_peso = [(feature_names[i], noticia_vector[i]) 
                                 for i in range(len(noticia_vector)) 
                                 if noticia_vector[i] > 0]
            palabras_con_peso.sort(key=lambda x: x[1], reverse=True)
            
            print(f"\n   Noticia: {df_noticias.iloc[idx_ejemplo]['titulo'][:60]}...")
            print(f"\n   Palabras más importantes de esta noticia:")
            for palabra, peso in palabras_con_peso[:10]:
                print(f"   • '{palabra}': {peso:.3f}")
            print(f"   ... y {len(palabras_con_peso) - 10} palabras más")
        
        print("\n❓ ¿ESTÁ DANDO RESULTADOS ESPERADOS?")
        
        # Verificar si hay palabras clave
        palabras_clave = ['feminicidio', 'mujer', 'hijos', 'niños', 'huerfanos', 'madre']
        palabras_encontradas = [p for p in palabras_clave if p in feature_names]
        
        print(f"\n   Palabras clave encontradas: {len(palabras_encontradas)}/{len(palabras_clave)}")
        print(f"   Presentes: {', '.join(palabras_encontradas)}")
        
        if len(palabras_encontradas) < len(palabras_clave) // 2:
            print("\n   ⚠️  ADVERTENCIA: Pocas palabras clave detectadas")
            print("   💡 RECOMENDACIÓN:")
            print("      - Verificar que strip_accents=None (preserva acentos)")
            print("      - Considerar reducir max_df si elimina palabras importantes")
        else:
            print("\n   ✅ Vectorización captura palabras clave correctamente")
        
        if analyzer.tfidf_matrix.shape[1] < 500:
            print("\n   ⚠️  ADVERTENCIA: Pocas features (<500)")
            print("   💡 RECOMENDACIÓN: Aumentar max_features o recolectar más noticias")
        
        self.results['steps'].append({
            'step': 3,
            'name': 'Vectorización',
            'matriz_shape': list(analyzer.tfidf_matrix.shape),
            'top_palabras': [palabra for palabra, _ in 
                           [(feature_names[i], col_sums[i]) for i in top_indices[:10]]]
        })
        
        return analyzer
    
    def step_4_topicos(self, analyzer):
        """
        PASO 4: MODELADO DE TÓPICOS (LDA)
        ¿Qué hace? Encuentra temas comunes en las noticias
        ¿Por qué? Ayuda a agrupar noticias por tema (ej: "feminicidio Edomex", "apoyo a huérfanos")
        """
        print_section("PASO 4: MODELADO DE TÓPICOS (LDA)", "=")
        
        print("📌 ¿QUÉ HACE ESTE PASO?")
        print("   Encuentra TEMAS comunes en las noticias.")
        print("   Ejemplo: Tópico 1 podría ser 'feminicidio + edomex + asesinato'")
        print("           Tópico 2 podría ser 'apoyo + huérfanos + gobierno'")
        print()
        
        print("📌 ¿POR QUÉ ES NECESARIO?")
        print("   Ayuda a entender de QUÉ hablan las noticias.")
        print("   Agrupa noticias similares temáticamente.")
        print()
        
        lda_config = config.LDA_CONFIG
        print("📌 PARÁMETROS QUE USA:")
        print(f"   • n_components: {lda_config['n_components']}")
        print(f"     └─ Buscará {lda_config['n_components']} temas diferentes")
        print(f"\n   • random_state: {lda_config['random_state']}")
        print(f"     └─ Semilla para reproducibilidad")
        print()
        
        print("🔄 EJECUTANDO LDA...")
        df_processed, topic_info = analyzer.step_4_topic_modeling(
            num_topics=lda_config['n_components']
        )
        
        if topic_info:
            print(f"\n✅ {topic_info['num_topics']} TÓPICOS DESCUBIERTOS:")
            print(f"   Perplexity: {topic_info['perplexity']:.2f}")
            print(f"   (Menor perplexity = mejor modelo)")
            print()
            
            for topic in topic_info['topics']:
                print(f"\n   📌 TÓPICO {topic['topic_id']}:")
                print(f"      Palabras clave: {', '.join(topic['words'][:8])}")
                
                # Mostrar ejemplos de noticias de este tópico
                noticias_topico = df_processed[df_processed['topic_id'] == topic['topic_id']]
                print(f"      Noticias en este tópico: {len(noticias_topico)}")
                
                if len(noticias_topico) > 0:
                    print(f"      Ejemplo: {noticias_topico.iloc[0]['titulo'][:60]}...")
            
            print("\n❓ ¿ESTÁ DANDO RESULTADOS ESPERADOS?")
            
            # Verificar distribución de tópicos
            topic_counts = df_processed['topic_id'].value_counts()
            desbalance = topic_counts.max() / topic_counts.min() if len(topic_counts) > 1 else 1
            
            print(f"\n   Distribución de noticias por tópico:")
            for topic_id in sorted(topic_counts.index):
                count = topic_counts[topic_id]
                percentage = count / len(df_processed) * 100
                bar = "█" * int(percentage / 2)
                print(f"   Tópico {topic_id}: {bar} {count} ({percentage:.1f}%)")
            
            if desbalance > 5:
                print(f"\n   ⚠️  ADVERTENCIA: Distribución muy desbalanceada (ratio {desbalance:.1f})")
                print("   💡 RECOMENDACIÓN:")
                print("      - Reducir n_components (menos tópicos)")
                print("      - Recolectar más noticias variadas")
            else:
                print("\n   ✅ Distribución de tópicos es aceptable")
            
            self.results['steps'].append({
                'step': 4,
                'name': 'Tópicos LDA',
                'num_topicos': topic_info['num_topics'],
                'perplexity': float(topic_info['perplexity']),
                'topicos': [{
                    'id': t['topic_id'],
                    'palabras': t['words'][:5],
                    'count': int(topic_counts.get(t['topic_id'], 0))
                } for t in topic_info['topics']]
            })
        
        return analyzer
    
    def step_5_clustering(self, analyzer):
        """
        PASO 5: CLUSTERING (DBSCAN)
        ¿Qué hace? Agrupa noticias MUY similares
        ¿Por qué? Encuentra casos duplicados o muy relacionados
        """
        print_section("PASO 5: CLUSTERING (DBSCAN)", "=")
        
        print("📌 ¿QUÉ HACE ESTE PASO?")
        print("   Agrupa noticias que son MUY SIMILARES entre sí.")
        print("   Usa distancia coseno entre vectores TF-IDF.")
        print()
        
        print("📌 ¿POR QUÉ ES NECESARIO?")
        print("   Identifica:")
        print("   • Noticias duplicadas (mismo caso reportado varias veces)")
        print("   • Casos relacionados (mismo feminicidio, diferentes fuentes)")
        print("   • Outliers (casos únicos sin similitud)")
        print()
        
        dbscan_config = config.DBSCAN_CONFIG
        print("📌 PARÁMETROS QUE USA:")
        print(f"   • eps: {dbscan_config['eps']}")
        print(f"     └─ Distancia máxima para agrupar")
        print(f"     └─ eps=0.6 significa: similitud > 40% para mismo cluster")
        print(f"\n   • min_samples: {dbscan_config['min_samples']}")
        print(f"     └─ Mínimo {dbscan_config['min_samples']} noticias para formar cluster")
        print(f"\n   • metric: '{dbscan_config['metric']}'")
        print(f"     └─ Usa similitud coseno (mejor para texto)")
        print()
        
        print("🔄 EJECUTANDO DBSCAN...")
        df_processed, cluster_info = analyzer.step_5_clustering(
            method='dbscan',
            eps=dbscan_config['eps'],
            min_samples=dbscan_config['min_samples']
        )
        
        if cluster_info:
            print(f"\n✅ CLUSTERING COMPLETADO:")
            print(f"   • Clusters encontrados: {cluster_info['n_clusters']}")
            print(f"   • Outliers (noticias únicas): {cluster_info['n_outliers']}")
            print(f"   • Silhouette Score: {cluster_info['silhouette']:.3f}")
            print(f"     └─ Entre -1 y 1, >0.3 es bueno, >0.5 es excelente")
            print()
            
            print("📊 DISTRIBUCIÓN DE CLUSTERS:")
            for cluster_id in sorted(cluster_info['cluster_sizes'].keys()):
                count = cluster_info['cluster_sizes'][cluster_id]
                
                if cluster_id == -1:
                    print(f"\n   🔹 OUTLIERS ({count} noticias):")
                    print(f"      Son casos únicos sin similitud suficiente con otros")
                else:
                    terms = cluster_info['top_terms'][cluster_id][:5]
                    print(f"\n   🔹 CLUSTER {cluster_id} ({count} noticias):")
                    print(f"      Palabras clave: {', '.join(terms)}")
                    
                    # Mostrar ejemplos
                    noticias_cluster = df_processed[df_processed['cluster'] == cluster_id]
                    for idx, row in noticias_cluster.head(2).iterrows():
                        print(f"      • {row['titulo'][:65]}...")
            
            print("\n❓ ¿ESTÁ DANDO RESULTADOS ESPERADOS?")
            
            ratio_outliers = cluster_info['n_outliers'] / len(df_processed)
            
            print(f"\n   Outliers: {cluster_info['n_outliers']} ({ratio_outliers*100:.1f}%)")
            
            if ratio_outliers > 0.90:
                print("\n   ⚠️  ADVERTENCIA: Demasiados outliers (>90%)")
                print("   💡 RECOMENDACIÓN:")
                print("      - Aumentar eps (ej: 0.7 o 0.8) para ser más permisivo")
                print("      - Reducir min_samples a 2")
                print("      - Las noticias son muy diferentes, esto es normal")
            elif ratio_outliers < 0.10:
                print("\n   ⚠️  ADVERTENCIA: Muy pocos outliers (<10%)")
                print("   💡 RECOMENDACIÓN:")
                print("      - Reducir eps (ej: 0.4 o 0.5) para ser más estricto")
                print("      - Puede estar agrupando noticias no relacionadas")
            else:
                print("\n   ✅ Clustering está funcionando bien")
            
            if cluster_info['silhouette'] < 0.3:
                print("\n   ⚠️  ADVERTENCIA: Silhouette Score bajo (<0.3)")
                print("   💡 RECOMENDACIÓN:")
                print("      - Ajustar eps (probar valores entre 0.4 y 0.8)")
                print("      - Considerar usar K-Means en lugar de DBSCAN")
            
            self.results['steps'].append({
                'step': 5,
                'name': 'Clustering DBSCAN',
                'n_clusters': cluster_info['n_clusters'],
                'n_outliers': cluster_info['n_outliers'],
                'silhouette': float(cluster_info['silhouette']),
                'ratio_outliers': float(ratio_outliers)
            })
        
        return analyzer
    
    def step_6_similitud(self, analyzer):
        """
        PASO 6: ANÁLISIS DE SIMILITUD
        ¿Qué hace? Calcula qué tan parecida es cada noticia con las demás
        ¿Por qué? Permite encontrar noticias relacionadas
        """
        print_section("PASO 6: ANÁLISIS DE SIMILITUD", "=")
        
        print("📌 ¿QUÉ HACE ESTE PASO?")
        print("   Calcula la SIMILITUD entre cada par de noticias.")
        print("   Usa coseno del ángulo entre vectores TF-IDF.")
        print()
        
        print("📌 ¿POR QUÉ ES NECESARIO?")
        print("   Permite:")
        print("   • Encontrar noticias relacionadas al mismo caso")
        print("   • Recomendar noticias similares")
        print("   • Detectar posibles duplicados")
        print()
        
        print("🔄 CALCULANDO SIMILITUDES...")
        df_analyzed = analyzer.step_6_similarity_analysis()
        
        print("\n✅ SIMILITUDES CALCULADAS:")
        avg_sim = df_analyzed['max_similarity'].mean()
        high_sim = (df_analyzed['max_similarity'] > 0.5).sum()
        
        print(f"   Similitud promedio: {avg_sim:.3f}")
        print(f"   Pares con alta similitud (>0.5): {high_sim}")
        print()
        
        print("📊 EJEMPLOS DE NOTICIAS SIMILARES:")
        # Encontrar par con mayor similitud
        max_sim_idx = df_analyzed['max_similarity'].idxmax()
        if pd.notna(max_sim_idx):
            noticia1 = df_analyzed.loc[max_sim_idx]
            similar_idx = int(noticia1['most_similar_doc_idx'])
            noticia2 = df_analyzed.iloc[similar_idx]
            similitud = noticia1['max_similarity']
            
            print(f"\n   Par más similar (similitud: {similitud:.3f}):")
            print(f"\n   1. {noticia1['titulo'][:65]}...")
            print(f"   2. {noticia2['titulo'][:65]}...")
        
        print("\n❓ ¿ESTÁ DANDO RESULTADOS ESPERADOS?")
        
        if avg_sim < 0.10:
            print(f"\n   ⚠️  ADVERTENCIA: Similitud promedio muy baja ({avg_sim:.3f})")
            print("   💡 RECOMENDACIÓN:")
            print("      - Normal si las noticias son de casos diferentes")
            print("      - Verificar que TF-IDF capture bien las palabras clave")
        elif avg_sim > 0.50:
            print(f"\n   ⚠️  ADVERTENCIA: Similitud promedio muy alta ({avg_sim:.3f})")
            print("   💡 RECOMENDACIÓN:")
            print("      - Puede haber muchas noticias duplicadas")
            print("      - Revisar proceso de recolección")
        else:
            print(f"\n   ✅ Similitud promedio es normal ({avg_sim:.3f})")
        
        self.results['steps'].append({
            'step': 6,
            'name': 'Similitud',
            'similitud_promedio': float(avg_sim),
            'pares_alta_similitud': int(high_sim)
        })
        
        return df_analyzed
    
    def generar_reporte(self, df_analyzed):
        """Genera reporte final con recomendaciones."""
        print_section("REPORTE FINAL Y RECOMENDACIONES", "=")
        
        print("📊 RESUMEN DEL PIPELINE COMPLETO:\n")
        
        for step in self.results['steps']:
            print(f"✓ Paso {step['step']}: {step['name']}")
            if step['step'] == 1:
                print(f"  • Noticias recolectadas: {step['total_noticias']}")
                print(f"  • Feminicidios: {step['feminicidios']}")
                print(f"  • Objetivo: {step['objetivo']}")
            elif step['step'] == 3:
                print(f"  • Matriz: {step['matriz_shape']}")
                print(f"  • Top palabras: {', '.join(step['top_palabras'][:5])}")
            elif step['step'] == 4:
                print(f"  • Tópicos: {step['num_topicos']}")
                print(f"  • Perplexity: {step['perplexity']:.2f}")
            elif step['step'] == 5:
                print(f"  • Clusters: {step['n_clusters']}")
                print(f"  • Outliers: {step['n_outliers']} ({step['ratio_outliers']*100:.1f}%)")
                print(f"  • Silhouette: {step['silhouette']:.3f}")
            elif step['step'] == 6:
                print(f"  • Similitud promedio: {step['similitud_promedio']:.3f}")
            print()
        
        print("\n" + "="*80)
        print("💡 RECOMENDACIONES GENERALES:")
        print("="*80 + "\n")
        
        # Recomendaciones basadas en resultados
        step1 = self.results['steps'][0]
        if step1['total_noticias'] < 50:
            print("1. RECOLECCIÓN:")
            print("   ⚠️  Pocas noticias (<50). Agregar más fuentes RSS especializadas.")
            print()
        
        if len(self.results['steps']) >= 5:
            step5 = self.results['steps'][4]
            if step5['ratio_outliers'] > 0.90:
                print("2. CLUSTERING:")
                print("   ⚠️  Muchos outliers. Aumentar eps de 0.6 a 0.7 o 0.8")
                print()
            elif step5['silhouette'] < 0.3:
                print("2. CLUSTERING:")
                print("   ⚠️  Silhouette bajo. Ajustar parámetros DBSCAN")
                print()
        
        print("✅ El pipeline está funcionando. Revisa las advertencias arriba.")
        
        # Guardar reporte JSON
        output_file = 'analisis_pipeline_reporte.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Reporte completo guardado en: {output_file}")


def main():
    """Función principal."""
    print("\n" + "="*80)
    print(" ANÁLISIS DETALLADO DEL PIPELINE COMPLETO")
    print(" Sistema Inteligente NNA - ESIME Zacatenco")
    print("="*80)
    
    analyzer_pipeline = PipelineAnalyzer()
    
    try:
        # Ejecutar cada paso
        df_noticias = analyzer_pipeline.step_1_recoleccion()
        
        if len(df_noticias) == 0:
            print("\n⚠️  No se recolectaron noticias. Abortando análisis.")
            return
        
        analyzer_pipeline.step_2_detector(df_noticias)
        analyzer = analyzer_pipeline.step_3_vectorizacion(df_noticias)
        analyzer = analyzer_pipeline.step_4_topicos(analyzer)
        analyzer = analyzer_pipeline.step_5_clustering(analyzer)
        df_analyzed = analyzer_pipeline.step_6_similitud(analyzer)
        
        # Generar reporte final
        analyzer_pipeline.generar_reporte(df_analyzed)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
