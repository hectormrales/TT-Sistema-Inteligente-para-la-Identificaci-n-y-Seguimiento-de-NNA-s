# app_docker.py - Aplicación Flask optimizada para Docker
# -*- coding: utf-8 -*-
"""
Aplicación web Flask containerizada para el Sistema NNA.
Interfaz web para visualizar resultados del análisis.
"""

import os
import json
import pandas as pd
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file
from datetime import datetime
import sys
import logging

# Determinar el directorio base (Docker vs Local)
IS_DOCKER = os.path.exists('/app')
BASE_DIR = Path('/app') if IS_DOCKER else Path(__file__).resolve().parent

# Agregar el directorio actual al path
sys.path.insert(0, str(BASE_DIR))

# Intentar importar CORS, continuar si no está disponible
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("⚠️  flask-cors no instalado. CORS no habilitado.")

from src.analysis.simplified_analyzer import SimplifiedNewsAnalyzer
from src.analysis.synonym_dictionary import SynonymDictionary

# Crear aplicación Flask
template_folder = str(BASE_DIR / 'app' / 'templates')
app = Flask(__name__, template_folder=template_folder)

# Habilitar CORS si está disponible
if CORS_AVAILABLE:
    CORS(app)

# Configuración
app.config['SECRET_KEY'] = 'nna-sistema-seguro-2024'
app.config['JSON_AS_ASCII'] = False

# Variables globales
analyzer = None
current_data = None
DATA_DIR = BASE_DIR / 'data'
LOGS_DIR = BASE_DIR / 'logs'

# Crear directorios si no existen
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

def load_data():
    """Cargar datos si existen."""
    global current_data
    
    data_file = DATA_DIR / 'noticias_analyzed_simplified.csv'
    if data_file.exists():
        try:
            current_data = pd.read_csv(str(data_file), encoding='utf-8-sig')
            app.logger.info(f"Datos cargados: {len(current_data)} noticias")
            return True
        except Exception as e:
            app.logger.error(f"Error cargando datos: {e}")
            return False
    return False

def get_stats():
    """Obtener estadísticas de los datos."""
    if current_data is None:
        return None
    
    # Calcular estadísticas de duplicados
    duplicados = 0
    noticias_unicas = len(current_data)
    grupos_duplicados = 0
    
    if 'es_duplicado' in current_data.columns:
        # Contar duplicados (True o 'True' como string)
        duplicados = int(
            ((current_data['es_duplicado'] == True) | 
             (current_data['es_duplicado'] == 'True')).sum()
        )
        noticias_unicas = len(current_data) - duplicados
        
        # Contar grupos (valores >= 0 en grupo_duplicado)
        if 'grupo_duplicado' in current_data.columns:
            grupos_duplicados = int(
                (current_data['grupo_duplicado'] >= 0).sum()
            )
            # Contar grupos únicos
            if grupos_duplicados > 0:
                grupos_duplicados = int(current_data[current_data['grupo_duplicado'] >= 0]['grupo_duplicado'].nunique())
    
    return {
        'total_noticias': len(current_data),
        'noticias_nna': int((current_data['menores_identificados'] == 'Si').sum()),
        'clusters': int(current_data['cluster'].nunique()) if 'cluster' in current_data.columns else 0,
        'topics': int(current_data['topic_id'].nunique()) if 'topic_id' in current_data.columns else 0,
        'similitud_promedio': float(current_data['max_similarity'].mean()) if 'max_similarity' in current_data.columns else 0,
        'duplicados': duplicados,
        'noticias_unicas': noticias_unicas,
        'grupos_duplicados': grupos_duplicados,
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
        # Filtro mejorado: solo feminicidios con NNA (es_objetivo=True y menores_identificados=Si)
        data = data[
            (data['menores_identificados'] == 'Si') & 
            ((data['es_objetivo'] == True) | (data['es_objetivo'] == 'True'))
        ]
    
    # Ordenar por prioridad: ALTA > MEDIA > BAJA > IRRELEVANTE
    if 'prioridad' in data.columns:
        priority_order = {'ALTA': 0, 'MEDIA': 1, 'BAJA': 2, 'IRRELEVANTE': 3}
        data['_priority_num'] = data['prioridad'].map(priority_order).fillna(4)
        data = data.sort_values('_priority_num')
        data = data.drop('_priority_num', axis=1)
    
    # Paginación
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    paginated_data = data.iloc[start_idx:end_idx]
    
    # Convertir a diccionario
    noticias = []
    for idx, row in paginated_data.iterrows():
        try:
            # Manejo seguro de valores nulos y NaN
            grupo_dup = row.get('grupo_duplicado', -1)
            if pd.isna(grupo_dup) or grupo_dup == '':
                grupo_dup = -1
            
            noticia = {
                'id': int(idx),
                'titulo': str(row.get('titulo', '')),
                'contenido': str(row.get('contenido', ''))[:200] + '...' if len(str(row.get('contenido', ''))) > 200 else str(row.get('contenido', '')),
                'fecha': str(row.get('fecha', '')),
                'fuente': str(row.get('fuente', '')),
                'menores_identificados': str(row.get('menores_identificados', 'No')),
                'prioridad': str(row.get('prioridad', 'IRRELEVANTE')),
                'es_feminicidio': bool(row.get('es_feminicidio', False)) if not pd.isna(row.get('es_feminicidio')) else False,
                'es_objetivo': bool(row.get('es_objetivo', False)) if not pd.isna(row.get('es_objetivo')) else False,
                'cluster': int(row.get('cluster', -1)) if not pd.isna(row.get('cluster')) else -1,
                'topic_id': int(row.get('topic_id', -1)) if not pd.isna(row.get('topic_id')) else -1,
                'similitud': float(row.get('max_similarity', 0)) if not pd.isna(row.get('max_similarity')) else 0.0,
                'es_duplicado': bool(row.get('es_duplicado', False)) if not pd.isna(row.get('es_duplicado')) else False,
                'grupo_duplicado': int(grupo_dup),
                'titulo_original': str(row.get('titulo_original', '')) if not pd.isna(row.get('titulo_original')) else '',
                'fuente_original': str(row.get('fuente_original', '')) if not pd.isna(row.get('fuente_original')) else ''
            }
            noticias.append(noticia)
        except Exception as e:
            logger.error(f"Error procesando noticia {idx}: {e}")
            continue
    
    return jsonify({
        'noticias': noticias,
        'total': len(data),
        'page': page,
        'per_page': per_page,
        'total_pages': (len(data) + per_page - 1) // per_page
    })

@app.route('/api/search')
def api_search():
    """
    API para búsqueda inteligente de noticias.
    Busca en: título, contenido, fuente, y usa sinónimos.
    """
    if current_data is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404
    
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Query requerido'}), 400
    
    try:
        # Usar diccionario de sinónimos para búsqueda
        synonym_dict = SynonymDictionary()
        
        # Búsqueda en múltiples campos: título, contenido, fuente
        mask = (
            current_data['titulo'].str.contains(query, case=False, na=False) |
            current_data['contenido'].str.contains(query, case=False, na=False) |
            current_data['fuente'].str.contains(query, case=False, na=False)
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
        
        # Ordenar por prioridad
        if 'prioridad' in results.columns:
            priority_order = {'ALTA': 0, 'MEDIA': 1, 'BAJA': 2, 'IRRELEVANTE': 3}
            results['_priority_num'] = results['prioridad'].map(priority_order).fillna(4)
            results = results.sort_values('_priority_num')
            results = results.drop('_priority_num', axis=1)
        
        # Convertir resultados (limitar a 50)
        noticias = []
        for idx, row in results.head(50).iterrows():
            try:
                grupo_dup = row.get('grupo_duplicado', -1)
                if pd.isna(grupo_dup) or grupo_dup == '':
                    grupo_dup = -1
                
                noticia = {
                    'id': int(idx),
                    'titulo': str(row.get('titulo', '')),
                    'contenido': str(row.get('contenido', ''))[:200] + '...' if len(str(row.get('contenido', ''))) > 200 else str(row.get('contenido', '')),
                    'fecha': str(row.get('fecha', '')),
                    'fuente': str(row.get('fuente', '')),
                    'menores_identificados': str(row.get('menores_identificados', 'No')),
                    'prioridad': str(row.get('prioridad', 'IRRELEVANTE')),
                    'es_feminicidio': bool(row.get('es_feminicidio', False)) if not pd.isna(row.get('es_feminicidio')) else False,
                    'es_objetivo': bool(row.get('es_objetivo', False)) if not pd.isna(row.get('es_objetivo')) else False,
                    'cluster': int(row.get('cluster', -1)) if not pd.isna(row.get('cluster')) else -1,
                    'topic_id': int(row.get('topic_id', -1)) if not pd.isna(row.get('topic_id')) else -1,
                    'similitud': float(row.get('max_similarity', 0)) if not pd.isna(row.get('max_similarity')) else 0.0,
                    'es_duplicado': bool(row.get('es_duplicado', False)) if not pd.isna(row.get('es_duplicado')) else False,
                    'grupo_duplicado': int(grupo_dup),
                    'titulo_original': str(row.get('titulo_original', '')) if not pd.isna(row.get('titulo_original')) else '',
                    'fuente_original': str(row.get('fuente_original', '')) if not pd.isna(row.get('fuente_original')) else ''
                }
                noticias.append(noticia)
            except Exception as e:
                app.logger.error(f"Error procesando noticia {idx} en búsqueda: {e}")
                continue
        
        return jsonify({
            'query': query,
            'resultados': len(results),
            'noticias': noticias,
            'synonyms_used': list(synonyms)
        })
        
    except Exception as e:
        app.logger.error(f"Error en búsqueda: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """API para ejecutar análisis completo."""
    try:
        global analyzer, current_data
        
        app.logger.info("Iniciando análisis completo...")
        
        # Importar colector de datos
        from src.collection.data_collector import collect_all_news
        
        # Paso 1: Recolectar noticias
        app.logger.info("Paso 1: Recolectando noticias...")
        df_noticias = collect_all_news(
            use_google_news=True,
            use_historical=True
        )
        
        if df_noticias is None or len(df_noticias) == 0:
            return jsonify({
                'status': 'error',
                'message': 'No se pudieron recolectar noticias'
            }), 500
        
        app.logger.info(f"Recolectadas {len(df_noticias)} noticias")
        
        # Guardar noticias crudas
        raw_path = DATA_DIR / 'noticias.csv'
        df_noticias.to_csv(str(raw_path), index=False, encoding='utf-8-sig')
        
        # Paso 2: Ejecutar análisis ML completo
        app.logger.info("Paso 2: Ejecutando análisis ML...")
        analyzer = SimplifiedNewsAnalyzer()
        
        result_data = analyzer.run_complete_analysis(
            df_input=df_noticias,
            num_topics=8,
            eps=0.80,
            min_samples=2,
            save_intermediate=True
        )
        
        app.logger.info("Análisis completado")
        
        # Paso 3: Recargar datos analizados
        if load_data():
            stats = get_stats()
            return jsonify({
                'status': 'success',
                'message': f'Análisis completado: {len(df_noticias)} noticias recolectadas y analizadas',
                'stats': stats,
                'noticias_recolectadas': len(df_noticias),
                'noticias_nna': stats.get('noticias_nna', 0),
                'clusters': stats.get('clusters', 0),
                'topics': stats.get('topics', 0)
            })
        else:
            return jsonify({
                'status': 'warning',
                'message': 'Análisis completado pero error cargando datos'
            }), 500
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
        output_path = DATA_DIR / 'export_noticias.csv'
        current_data.to_csv(str(output_path), index=False, encoding='utf-8-sig')
        return send_file(str(output_path), as_attachment=True, download_name='noticias_nna.csv')
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
    log_file = LOGS_DIR / 'webapp.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(str(log_file)),
            logging.StreamHandler()
        ]
    )
    
    app.logger.info("Iniciando aplicación web NNA Sistema")
    app.logger.info(f"Modo: {'Docker' if IS_DOCKER else 'Local'}")
    app.logger.info(f"BASE_DIR: {BASE_DIR}")
    
    # Ejecutar aplicación
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )