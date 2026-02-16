# app/main/routes.py — Dashboard y API REST
"""
Rutas del dashboard interactivo y endpoints de la API.
Todas las rutas (excepto /health) requieren autenticación.
"""

import os
import logging
from datetime import datetime

import pandas as pd
from flask import Blueprint, render_template, jsonify, request, send_file
from flask_login import login_required

from src.analysis.analyzer import SimplifiedNewsAnalyzer
from src.analysis.synonyms import SynonymDictionary

main_bp = Blueprint('main', __name__)

# ── Estado global de datos ──────────────────────────────────

_current_data: pd.DataFrame | None = None
_analyzer: SimplifiedNewsAnalyzer | None = None

DATA_DIR = os.environ.get('DATA_DIR', 'data')
LOGS_DIR = os.environ.get('LOGS_DIR', 'logs')
DATA_FILE = os.path.join(DATA_DIR, 'noticias_analyzed_simplified.csv')


def _load_data() -> bool:
    """Carga datos analizados desde CSV."""
    global _current_data
    if os.path.exists(DATA_FILE):
        try:
            _current_data = pd.read_csv(DATA_FILE)
            return True
        except Exception as e:
            logging.error(f"Error cargando datos: {e}")
    return False


def _safe_col(df: pd.DataFrame, col: str, default=0):
    """Devuelve el valor de una columna o un default si no existe."""
    if col in df.columns:
        return df[col]
    return default


def _get_stats() -> dict | None:
    """Devuelve estadísticas resumidas de los datos cargados."""
    if _current_data is None:
        return None
    df = _current_data
    total = len(df)

    nna = int((df['menores_identificados'] == 'Si').sum()) if 'menores_identificados' in df.columns else 0

    # Clasificación de relevancia
    if 'clasificacion_final' in df.columns:
        alta = int((df['clasificacion_final'] == 'Alta').sum())
        media = int((df['clasificacion_final'] == 'Media').sum())
        baja = int((df['clasificacion_final'] == 'Baja').sum())
    elif 'clasificacion' in df.columns:
        alta = int((df['clasificacion'] == 'Alta').sum())
        media = int((df['clasificacion'] == 'Media').sum())
        baja = int((df['clasificacion'] == 'Baja').sum())
    else:
        alta = media = baja = 0

    return {
        'total_noticias': total,
        'noticias_nna': nna,
        'alta_relevancia': alta,
        'media_relevancia': media,
        'baja_relevancia': baja,
        'clusters': int(df['cluster'].nunique()) if 'cluster' in df.columns else 0,
        'topics': int(df['topic_id'].nunique()) if 'topic_id' in df.columns else 0,
        'similitud_promedio': float(df['max_similarity'].mean()) if 'max_similarity' in df.columns else 0,
        'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def _row_to_dict(idx, row) -> dict:
    """Convierte una fila del DataFrame a diccionario para la API."""
    contenido = str(row.get('contenido', ''))
    return {
        'id': int(idx),
        'titulo': row.get('titulo', ''),
        'contenido': contenido[:200] + '...' if len(contenido) > 200 else contenido,
        'fecha': row.get('fecha', ''),
        'fuente': row.get('fuente', ''),
        'enlace': row.get('enlace', ''),
        'menores_identificados': row.get('menores_identificados', 'No'),
        'cluster': int(row.get('cluster', -1)),
        'topic_id': int(row.get('topic_id', -1)),
        'similitud': float(row.get('max_similarity', 0)),
        'score_feminicidio': float(row.get('score_feminicidio', 0)),
        'score_nna': float(row.get('score_nna', 0)),
        'score_compuesto': float(row.get('score_compuesto', 0)),
        'relevancia_final': float(row.get('relevancia_final', row.get('score_compuesto', 0))),
        'clasificacion': row.get('clasificacion_final', row.get('clasificacion', 'No relevante')),
    }


# ── Rutas de la interfaz ───────────────────────────────────

@main_bp.route('/')
@login_required
def index():
    """Dashboard principal."""
    return render_template('dashboard.html')


# ── API REST ────────────────────────────────────────────────

@main_bp.route('/api/stats')
@login_required
def api_stats():
    """Estadísticas generales."""
    stats = _get_stats()
    if stats is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404
    return jsonify(stats)


@main_bp.route('/api/noticias')
@login_required
def api_noticias():
    """Listado paginado de noticias con filtros de relevancia."""
    if _current_data is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    only_nna = request.args.get('only_nna', 'false').lower() == 'true'
    clasificacion = request.args.get('clasificacion', '').strip()  # Alta, Media, Baja

    data = _current_data.copy()

    if only_nna:
        data = data[data['menores_identificados'] == 'Si']

    if clasificacion:
        col = 'clasificacion_final' if 'clasificacion_final' in data.columns else 'clasificacion'
        if col in data.columns:
            data = data[data[col] == clasificacion]

    # Ordenar por relevancia
    sort_col = 'relevancia_final' if 'relevancia_final' in data.columns else 'score_compuesto'
    if sort_col in data.columns:
        data = data.sort_values(sort_col, ascending=False)

    start = (page - 1) * per_page
    paginated = data.iloc[start:start + per_page]

    noticias = [_row_to_dict(idx, row) for idx, row in paginated.iterrows()]

    return jsonify({
        'noticias': noticias,
        'total': len(data),
        'page': page,
        'per_page': per_page,
        'total_pages': (len(data) + per_page - 1) // per_page,
    })


@main_bp.route('/api/search')
@login_required
def api_search():
    """Búsqueda de noticias con expansión de sinónimos."""
    if _current_data is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404

    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Query requerido'}), 400

    try:
        synonym_dict = SynonymDictionary()
        mask = (
            _current_data['titulo'].str.contains(query, case=False, na=False)
            | _current_data['contenido'].str.contains(query, case=False, na=False)
        )

        for synonym in synonym_dict.get_synonyms(query):
            if synonym != query:
                mask = mask | (
                    _current_data['titulo'].str.contains(synonym, case=False, na=False)
                    | _current_data['contenido'].str.contains(synonym, case=False, na=False)
                )

        results = _current_data[mask]
        noticias = [_row_to_dict(idx, row) for idx, row in results.head(20).iterrows()]

        return jsonify({
            'query': query,
            'resultados': len(results),
            'noticias': noticias,
            'synonyms_used': list(synonym_dict.get_synonyms(query)),
        })
    except Exception as e:
        logging.error(f"Error en búsqueda: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@main_bp.route('/api/analyze')
@login_required
def api_analyze():
    """Ejecuta el pipeline completo de análisis."""
    try:
        global _analyzer
        _analyzer = SimplifiedNewsAnalyzer()
        _analyzer.run_complete_analysis(num_topics=5, n_clusters=4, save_intermediate=False)

        if _load_data():
            return jsonify({
                'status': 'success',
                'message': 'Análisis completado exitosamente',
                'stats': _get_stats(),
            })
        return jsonify({'error': 'Análisis completado pero error cargando datos'}), 500
    except Exception as e:
        logging.error(f"Error en análisis: {e}")
        return jsonify({'error': f'Error ejecutando análisis: {e}'}), 500


@main_bp.route('/api/export/csv')
@login_required
def api_export_csv():
    """Exporta los datos analizados como CSV."""
    if _current_data is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404
    try:
        export_path = os.path.join(DATA_DIR, 'export_noticias.csv')
        _current_data.to_csv(export_path, index=False, encoding='utf-8')
        return send_file(export_path, as_attachment=True, download_name='noticias_nna.csv')
    except Exception as e:
        return jsonify({'error': f'Error exportando: {e}'}), 500


@main_bp.route('/health')
def health_check():
    """Health check para Docker (sin autenticación)."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'data_loaded': _current_data is not None,
        'data_size': len(_current_data) if _current_data is not None else 0,
    })


# ── Errores ─────────────────────────────────────────────────

@main_bp.app_errorhandler(404)
def not_found(_error):
    return jsonify({'error': 'Endpoint no encontrado'}), 404


@main_bp.app_errorhandler(500)
def internal_error(_error):
    return jsonify({'error': 'Error interno del servidor'}), 500
