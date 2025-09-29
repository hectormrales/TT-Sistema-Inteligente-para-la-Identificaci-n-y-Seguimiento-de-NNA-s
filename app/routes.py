# app/routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from src.utils import file_handler
from src.collection import data_collector
from src.processing.text_processor import clean_and_lemmatize_series
import config
import os
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from src.analysis.news_analyzer import cluster_dataframe
from src.analysis.feminicidio_extractor import annotate_feminicidios, filter_feminicidios

# Creamos un "Blueprint" para organizar nuestras rutas
bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('dashboard.html', articles=[])

@bp.route('/dashboard')
def dashboard():
    # 1. LLAMAMOS A NUESTRO MÓDULO 'src' PARA OBTENER LOS DATOS
    try:
        df = file_handler.load_from_csv(config.DATA_PATH)
        # Limpiar valores NaN y convertir a strings
        df = df.fillna('')  # Reemplazar NaN con strings vacíos
        # Convertir campos específicos a strings para evitar errores
        for col in ['titulo', 'contenido', 'fuente']:
            if col in df.columns:
                df[col] = df[col].astype(str)
        # Convertimos el dataframe a una lista de diccionarios para el HTML
        articles = df.to_dict('records')
    except FileNotFoundError:
        articles = []
        
    # 2. PASAMOS LOS DATOS A LA PLANTILLA HTML
    return render_template('dashboard.html', articles=articles)


@bp.route('/collect-news', methods=['POST'])
def collect_news():
    """Recolecta noticias y las analiza para detectar menciones de menores."""
    try:
        # Recolectar noticias
        df = data_collector.collect_all_news()
        
        if df.empty:
            return jsonify({'error': 'No se pudieron recolectar noticias'}), 400
        
        #Limpar texto
        df['contenido_limpio'] = clean_and_lemmatize_series(df['contenido'])
        
        #Analizar menciones de menores 
        df['menores_identificados'] = df['contenido_limpio'].apply(data_collector.detect_children_mentions)

        #Anotar feminicidios
        df = annotate_feminicidios(
            df,
            text_col='contenido_limpio',
            title_col='titulo',
            threshold= 0.8
        )

        #Clustering con KMeans + TF-IDF
        try:
            df, clustering_info = cluster_dataframe(
                df,
                n_clusters=getattr(config, 'KMEANS_CLUSTERS', 5),
                max_features=getattr(config, 'TFIDF_MAX_FEATURES', 5000),
                random_state=42,
                top_n_terms=12
            )
            print(
                f"[CLUSTER] silhouette={clustering_info['silhouette']:.4f}, "
                f"clusters={clustering_info['n_clusters']}"
            )
        except Exception as e:
            print(f"Clustering no aplicado: {e}")

        # Guardar en CSV
        file_handler.save_to_csv(df, config.DATA_PATH)
        
        #CSV solo de feminicidios(
        fems = filter_feminicidios(df)
        if not fems.empty:
            os.makedirs('data', exist_ok=True)
            file_handler.save_to_csv(fems, 'data/feminicidios.csv')


        return jsonify({
            'message': f'Se recolectaron y analizaron {len(df)} noticias',
            'articles_with_children': len(df[df['menores_identificados'] == 'Sí'])
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/status')
def api_status():
    """Endpoint para verificar el estado de la API."""
    csv_exists = os.path.exists(config.DATA_PATH)
    fems_exists = os.path.exists('data/feminicidios.csv')
    return jsonify({
        'status': 'running',
        'data_available': csv_exists,
        'feminicidios.csv': fems_exists
    })