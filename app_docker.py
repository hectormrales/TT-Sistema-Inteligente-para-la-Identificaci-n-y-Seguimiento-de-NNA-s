# app_docker.py - Aplicación Flask optimizada para Docker
"""
Aplicación web Flask containerizada para el Sistema NNA.
Interfaz web para visualizar resultados del análisis.
"""

import os
import json
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file
from datetime import datetime
import sys

# Agregar el directorio actual al path
sys.path.append('/app')

from src.analysis.simplified_analyzer import S@app.route('/api/analyze/advanced', methods=['POST'])
def api_analyze_advanced():
    """API para ejecutar análisis con scraper avanzado"""
    try:
        global analyzer, current_data
        
        # Primero ejecutar recolección avanzada de datos
        from src.collection.advanced_scraper import collect_with_advanced_scraper
        app.logger.info("Iniciando recolección avanzada de datos...")
        collect_with_advanced_scraper()
        
        # Crear analizador después de tener los datos
        analyzer = SimplifiedNewsAnalyzer(use_smart_collector=False)
        
        # Ejecutar análisis sobre los datos ya recolectados
        result_data = analyzer.run_complete_analysis(
            num_topics=5,
            n_clusters=4,
            save_intermediate=False
        )er
from src.analysis.synonym_dictionary import SynonymDictionary
from src.collection.smart_data_collector import SmartDataCollector
from src.collection.advanced_scraper import AdvancedScraper, SourceManager

# Crear aplicación Flask
app = Flask(__name__, template_folder='/app/app/templates')

# Configuración
app.config['SECRET_KEY'] = 'nna-sistema-seguro-2024'
app.config['JSON_AS_ASCII'] = False

# Variables globales
analyzer = None
current_data = None
smart_collector = SmartDataCollector()
source_manager = SourceManager()
advanced_scraper = AdvancedScraper()

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
    """API para ejecutar análisis tradicional."""
    try:
        global analyzer, current_data
        
        # Crear analizador tradicional
        analyzer = SimplifiedNewsAnalyzer(use_smart_collector=False)
        
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
                'message': 'Análisis tradicional completado exitosamente',
                'stats': get_stats(),
                'type': 'traditional'
            })
        else:
            return jsonify({'error': 'Análisis completado pero error cargando datos'}), 500
            
    except Exception as e:
        app.logger.error(f"Error en análisis: {e}")
        return jsonify({'error': f'Error ejecutando análisis: {str(e)}'}), 500

@app.route('/api/analyze/smart')
def api_analyze_smart():
    """API para ejecutar análisis inteligente."""
    try:
        global analyzer, current_data
        
        # Obtener parámetros
        threshold = float(request.args.get('threshold', 0.3))
        
        # Crear analizador inteligente
        analyzer = SimplifiedNewsAnalyzer(use_smart_collector=True)
        
        # Ejecutar análisis
        result_data = analyzer.run_complete_analysis(
            num_topics=5,
            n_clusters=4,
            save_intermediate=False
        )
        
        # Recargar datos
        if load_data():
            stats = get_stats()
            
            # Agregar estadísticas específicas del recolector inteligente
            if 'relevancia_nna' in current_data.columns:
                stats['relevancia_promedio'] = float(current_data['relevancia_nna'].mean())
                stats['articulos_alta_relevancia'] = int((current_data['relevancia_nna'] > 0.5).sum())
            
            if 'procesado_completo' in current_data.columns:
                stats['contenido_completo'] = int(current_data['procesado_completo'].sum())
                stats['eficiencia_red'] = f"{(1 - stats['contenido_completo'] / stats['total_noticias']) * 100:.1f}% menos peticiones"
            
            return jsonify({
                'status': 'success',
                'message': 'Análisis inteligente completado exitosamente',
                'stats': stats,
                'type': 'smart',
                'threshold_used': threshold
            })
        else:
            return jsonify({'error': 'Análisis completado pero error cargando datos'}), 500
            
    except Exception as e:
        app.logger.error(f"Error en análisis inteligente: {e}")
        return jsonify({'error': f'Error ejecutando análisis inteligente: {str(e)}'}), 500

@app.route('/api/robots-check')
def api_robots_check():
    """API para verificar robots.txt de las fuentes."""
    try:
        import config
        
        results = []
        for rss_url in config.RSS_FEEDS:
            can_crawl = smart_collector.check_robots_txt(rss_url)
            delay = smart_collector.get_crawl_delay(rss_url)
            
            from urllib.parse import urlparse
            domain = urlparse(rss_url).netloc
            
            results.append({
                'url': rss_url,
                'domain': domain,
                'allowed': can_crawl,
                'delay': delay,
                'status': '✅ Permitido' if can_crawl else '⚠️ Bloqueado'
            })
        
        allowed_count = sum(1 for r in results if r['allowed'])
        
        return jsonify({
            'sources': results,
            'summary': {
                'total_sources': len(results),
                'allowed_sources': allowed_count,
                'blocked_sources': len(results) - allowed_count,
                'compliance_rate': f"{(allowed_count / len(results)) * 100:.1f}%"
            }
        })
        
    except Exception as e:
        app.logger.error(f"Error verificando robots.txt: {e}")
        return jsonify({'error': f'Error verificando robots.txt: {str(e)}'}), 500

# ===== APIs DE GESTIÓN DE FUENTES =====

@app.route('/api/sources', methods=['GET'])
def api_get_sources():
    """Obtener todas las fuentes configuradas"""
    try:
        sources = source_manager.sources
        
        # Enriquecer con estadísticas
        for source_id, source in sources.items():
            config = source.get('scraping_config', {})
            source['stats'] = {
                'last_success': config.get('last_success'),
                'error_count': config.get('error_count', 0),
                'status': 'active' if source.get('enabled') and config.get('error_count', 0) < 5 else 'inactive'
            }
        
        return jsonify({
            'sources': sources,
            'total': len(sources),
            'enabled': len([s for s in sources.values() if s.get('enabled', True)])
        })
        
    except Exception as e:
        app.logger.error(f"Error obteniendo fuentes: {e}")
        return jsonify({'error': f'Error obteniendo fuentes: {str(e)}'}), 500

@app.route('/api/sources', methods=['POST'])
def api_add_source():
    """Agregar nueva fuente"""
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        required_fields = ['source_id', 'name', 'url']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Campo requerido: {field}'}), 400
        
        source_id = data['source_id']
        name = data['name']
        url = data['url']
        source_type = data.get('type', 'rss')
        
        # Verificar que no existe
        if source_id in source_manager.sources:
            return jsonify({'error': 'La fuente ya existe'}), 409
        
        # Agregar fuente
        success = source_manager.add_source(source_id, name, url, source_type)
        
        if success:
            return jsonify({
                'message': 'Fuente agregada exitosamente',
                'source_id': source_id
            }), 201
        else:
            return jsonify({'error': 'Error agregando fuente'}), 500
            
    except Exception as e:
        app.logger.error(f"Error agregando fuente: {e}")
        return jsonify({'error': f'Error agregando fuente: {str(e)}'}), 500

@app.route('/api/sources/<source_id>', methods=['PUT'])
def api_update_source(source_id):
    """Actualizar fuente existente"""
    try:
        data = request.get_json()
        
        if source_id not in source_manager.sources:
            return jsonify({'error': 'Fuente no encontrada'}), 404
        
        # Actualizar fuente
        success = source_manager.update_source(source_id, **data)
        
        if success:
            return jsonify({
                'message': 'Fuente actualizada exitosamente',
                'source': source_manager.sources[source_id]
            })
        else:
            return jsonify({'error': 'Error actualizando fuente'}), 500
            
    except Exception as e:
        app.logger.error(f"Error actualizando fuente: {e}")
        return jsonify({'error': f'Error actualizando fuente: {str(e)}'}), 500

@app.route('/api/sources/<source_id>', methods=['DELETE'])
def api_delete_source(source_id):
    """Eliminar fuente"""
    try:
        if source_id not in source_manager.sources:
            return jsonify({'error': 'Fuente no encontrada'}), 404
        
        success = source_manager.delete_source(source_id)
        
        if success:
            return jsonify({'message': 'Fuente eliminada exitosamente'})
        else:
            return jsonify({'error': 'Error eliminando fuente'}), 500
            
    except Exception as e:
        app.logger.error(f"Error eliminando fuente: {e}")
        return jsonify({'error': f'Error eliminando fuente: {str(e)}'}), 500

@app.route('/api/sources/<source_id>/test', methods=['POST'])
def api_test_source(source_id):
    """Probar una fuente específica"""
    try:
        if source_id not in source_manager.sources:
            return jsonify({'error': 'Fuente no encontrada'}), 404
        
        # Probar scraping de la fuente
        articles = advanced_scraper.scrape_source(source_id)
        
        source = source_manager.sources[source_id]
        
        return jsonify({
            'message': f'Prueba completada para {source["name"]}',
            'articles_found': len(articles),
            'source_status': 'success' if articles else 'no_content',
            'sample_articles': articles[:3] if articles else []
        })
        
    except Exception as e:
        app.logger.error(f"Error probando fuente: {e}")
        return jsonify({'error': f'Error probando fuente: {str(e)}'}), 500

@app.route('/api/sources/<source_id>/config', methods=['PUT'])
def api_update_source_config(source_id):
    """Actualizar configuración de scraping de una fuente"""
    try:
        data = request.get_json()
        
        if source_id not in source_manager.sources:
            return jsonify({'error': 'Fuente no encontrada'}), 404
        
        # Actualizar configuración de scraping
        config_updates = {}
        allowed_configs = ['technique', 'delay', 'user_agent', 'headers', 'selector']
        
        for key in allowed_configs:
            if key in data:
                config_updates[f'config_{key}'] = data[key]
        
        if config_updates:
            success = source_manager.update_source(source_id, **config_updates)
            
            if success:
                return jsonify({
                    'message': 'Configuración actualizada exitosamente',
                    'config': source_manager.sources[source_id]['scraping_config']
                })
            else:
                return jsonify({'error': 'Error actualizando configuración'}), 500
        else:
            return jsonify({'error': 'No hay configuraciones válidas para actualizar'}), 400
            
    except Exception as e:
        app.logger.error(f"Error actualizando configuración: {e}")
        return jsonify({'error': f'Error actualizando configuración: {str(e)}'}), 500

@app.route('/api/analyze/advanced')
def api_analyze_advanced():
    """API para ejecutar análisis con scraper avanzado"""
    try:
        global analyzer, current_data
        
        # Crear analizador que use el scraper avanzado
        analyzer = SimplifiedNewsAnalyzer(use_smart_collector=False)
        
        # Reemplazar la función de recolección
        from src.collection.advanced_scraper import collect_with_advanced_scraper
        analyzer.step_1_collect_data = lambda: collect_with_advanced_scraper()
        
        # Ejecutar análisis
        result_data = analyzer.run_complete_analysis(
            num_topics=5,
            n_clusters=4,
            save_intermediate=False
        )
        
        # Recargar datos
        if load_data():
            stats = get_stats()
            
            # Agregar estadísticas de fuentes
            sources = source_manager.get_enabled_sources()
            stats['sources_used'] = len(sources)
            stats['sources_active'] = len([s for s in sources.values() if s['scraping_config']['error_count'] < 5])
            
            return jsonify({
                'status': 'success',
                'message': 'Análisis avanzado completado exitosamente',
                'stats': stats,
                'type': 'advanced',
                'sources_summary': {
                    'total': len(source_manager.sources),
                    'enabled': len(sources),
                    'active': stats['sources_active']
                }
            })
        else:
            return jsonify({'error': 'Análisis completado pero error cargando datos'}), 500
            
    except Exception as e:
        app.logger.error(f"Error en análisis avanzado: {e}")
        return jsonify({'error': f'Error ejecutando análisis avanzado: {str(e)}'}), 500

@app.route('/api/collect', methods=['POST'])
def api_collect_only():
    """API para solo ejecutar recolección de datos"""
    try:
        from src.collection.advanced_scraper import collect_with_advanced_scraper
        app.logger.info("Iniciando recolección de datos...")
        
        # Ejecutar recolección
        articles_collected = collect_with_advanced_scraper()
        
        # Recargar datos
        if load_data():
            stats = get_stats()
            return jsonify({
                'status': 'success',
                'message': f'Recolección completada. {len(articles_collected) if articles_collected else 0} artículos recolectados.',
                'stats': stats,
                'type': 'collection'
            })
        else:
            return jsonify({'error': 'Recolección completada pero error cargando datos'}), 500
            
    except Exception as e:
        app.logger.error(f"Error en recolección: {e}")
        return jsonify({'error': f'Error ejecutando recolección: {str(e)}'}), 500

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