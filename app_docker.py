# app_docker.py - Aplicación Flask optimizada para Docker
"""
Aplicación web Flask containerizada para el Sistema NNA.
Interfaz web para visualizar resultados del análisis.
"""

import os
import json
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from datetime import datetime
import sys

# Agregar el directorio actual al path
sys.path.append('/app')

from src.analysis.simplified_analyzer import SimplifiedNewsAnalyzer
from src.analysis.synonym_dictionary import SynonymDictionary

# Crear aplicación Flask
app = Flask(__name__, template_folder='/app/app/templates')
CORS(app)

# Configuración
app.config['SECRET_KEY'] = 'nna-sistema-seguro-2024'
app.config['JSON_AS_ASCII'] = False

# Variables globales
analyzer = None
current_data = None

def load_data():
    """Cargar datos si existen."""
    global current_data
    
    data_file = '/app/data/noticias_analyzed_simplified.csv'
    if os.path.exists(data_file):
        try:
            current_data = pd.read_csv(data_file)
            return True
        except Exception as e:
            app.logger.error(f"Error cargando datos: {e}")
            return False
    return False

def get_stats():
    """Obtener estadísticas de los datos."""
    if current_data is None:
        return None
    
    return {
        'total_noticias': len(current_data),
        'noticias_nna': int((current_data['menores_identificados'] == 'Si').sum()),
        'clusters': int(current_data['cluster'].nunique()) if 'cluster' in current_data.columns else 0,
        'topics': int(current_data['topic_id'].nunique()) if 'topic_id' in current_data.columns else 0,
        'similitud_promedio': float(current_data['max_similarity'].mean()) if 'max_similarity' in current_data.columns else 0,
        'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

@app.route('/')
def index():
    """Página principal."""
    return render_template('dashboard_docker.html')

@app.route('/api/stats')
def api_stats():
    """API para obtener estadísticas."""
    stats = get_stats()
    if stats is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404
    
    return jsonify(stats)

@app.route('/api/noticias')
def api_noticias():
    """API para obtener noticias."""
    if current_data is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404
    
    # Parámetros de filtrado
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    only_nna = request.args.get('only_nna', 'false').lower() == 'true'
    
    # Filtrar datos
    data = current_data.copy()
    if only_nna:
        data = data[data['menores_identificados'] == 'Si']
    
    # Paginación
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    paginated_data = data.iloc[start_idx:end_idx]
    
    # Convertir a diccionario
    noticias = []
    for idx, row in paginated_data.iterrows():
        noticia = {
            'id': int(idx),
            'titulo': row['titulo'],
            'contenido': row['contenido'][:200] + '...' if len(row['contenido']) > 200 else row['contenido'],
            'fecha': row['fecha'],
            'fuente': row['fuente'],
            'menores_identificados': row['menores_identificados'],
            'cluster': int(row.get('cluster', -1)),
            'topic_id': int(row.get('topic_id', -1)),
            'similitud': float(row.get('max_similarity', 0))
        }
        noticias.append(noticia)
    
    return jsonify({
        'noticias': noticias,
        'total': len(data),
        'page': page,
        'per_page': per_page,
        'total_pages': (len(data) + per_page - 1) // per_page
    })

@app.route('/api/search')
def api_search():
    """API para búsqueda de noticias."""
    if current_data is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404
    
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Query requerido'}), 400
    
    try:
        # Usar diccionario de sinónimos para búsqueda
        synonym_dict = SynonymDictionary()
        
        # Búsqueda en títulos y contenido
        mask = (
            current_data['titulo'].str.contains(query, case=False, na=False) |
            current_data['contenido'].str.contains(query, case=False, na=False)
        )
        
        # Expandir búsqueda con sinónimos
        synonyms = synonym_dict.get_synonyms(query)
        for synonym in synonyms:
            if synonym != query:
                mask = mask | (
                    current_data['titulo'].str.contains(synonym, case=False, na=False) |
                    current_data['contenido'].str.contains(synonym, case=False, na=False)
                )
        
        results = current_data[mask]
        
        # Convertir resultados
        noticias = []
        for idx, row in results.head(20).iterrows():  # Limitar a 20 resultados
            noticia = {
                'id': int(idx),
                'titulo': row['titulo'],
                'contenido': row['contenido'][:200] + '...' if len(row['contenido']) > 200 else row['contenido'],
                'fecha': row['fecha'],
                'fuente': row['fuente'],
                'menores_identificados': row['menores_identificados'],
                'cluster': int(row.get('cluster', -1)),
                'topic_id': int(row.get('topic_id', -1)),
                'similitud': float(row.get('max_similarity', 0))
            }
            noticias.append(noticia)
        
        return jsonify({
            'query': query,
            'resultados': len(results),
            'noticias': noticias,
            'synonyms_used': list(synonyms)
        })
        
    except Exception as e:
        app.logger.error(f"Error en búsqueda: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/analyze')
def api_analyze():
    """API para ejecutar análisis."""
    try:
        global analyzer, current_data
        
        # Crear analizador
        analyzer = SimplifiedNewsAnalyzer()
        
        # Ejecutar análisis
        result_data = analyzer.run_complete_analysis(
            num_topics=5,
            n_clusters=4,
            save_intermediate=False
        )
        
        # Recargar datos
        if load_data():
            return jsonify({
                'status': 'success',
                'message': 'Análisis completado exitosamente',
                'stats': get_stats()
            })
        else:
            return jsonify({'error': 'Análisis completado pero error cargando datos'}), 500
            
    except Exception as e:
        app.logger.error(f"Error en análisis: {e}")
        return jsonify({'error': f'Error ejecutando análisis: {str(e)}'}), 500

@app.route('/api/export/csv')
def api_export_csv():
    """API para exportar datos en CSV."""
    if current_data is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404
    
    try:
        output_path = '/app/data/export_noticias.csv'
        current_data.to_csv(output_path, index=False, encoding='utf-8')
        return send_file(output_path, as_attachment=True, download_name='noticias_nna.csv')
    except Exception as e:
        return jsonify({'error': f'Error exportando: {str(e)}'}), 500

@app.route('/health')
def health_check():
    """Health check para Docker."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'data_loaded': current_data is not None,
        'data_size': len(current_data) if current_data is not None else 0
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint no encontrado'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Error interno del servidor'}), 500

# Inicialización
if __name__ == '__main__':
    # Cargar datos existentes al inicio
    load_data()
    
    # Configurar logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/app/logs/webapp.log'),
            logging.StreamHandler()
        ]
    )
    
    app.logger.info("Iniciando aplicación web NNA Sistema")
    
    # Ejecutar aplicación
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )