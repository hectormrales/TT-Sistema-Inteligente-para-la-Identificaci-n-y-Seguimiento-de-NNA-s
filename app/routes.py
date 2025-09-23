# app/routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from src.utils import file_handler
from src.collection import data_collector
import config
import os

# Creamos un "Blueprint" para organizar nuestras rutas
bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('dashboard.html', articles=[])

@bp.route('/dashboard')
def dashboard():
    # 1. LLAMAMOS A NUESTRO MÓDULO 'src' PARA OBTENER LOS DATOS
    try:
        df = file_handler.load_from_csv('data/noticias_analizadas.csv')
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
        
        # Analizar menciones de menores
        df['menores_identificados'] = df['contenido'].apply(data_collector.detect_children_mentions)
        
        # Guardar en CSV
        file_handler.save_to_csv(df, 'data/noticias_analizadas.csv')
        
        return jsonify({
            'message': f'Se recolectaron y analizaron {len(df)} noticias',
            'articles_with_children': len(df[df['menores_identificados'] == 'Sí'])
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/status')
def api_status():
    """Endpoint para verificar el estado de la API."""
    csv_exists = os.path.exists('data/noticias_analizadas.csv')
    return jsonify({
        'status': 'running',
        'data_available': csv_exists
    })