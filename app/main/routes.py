# app/main/routes.py — Dashboard y API REST
"""
Rutas del dashboard interactivo y endpoints de la API.
Todas las rutas (excepto /health) requieren autenticación.

v5.0 TT2: Soporte dual CSV/PostgreSQL con FTS.
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
_use_postgres: bool = False  # Se activa si la tabla noticias tiene datos

DATA_DIR = os.environ.get('DATA_DIR', 'data')
LOGS_DIR = os.environ.get('LOGS_DIR', 'logs')
DATA_FILE = os.path.join(DATA_DIR, 'noticias_analyzed_simplified.csv')


def _check_postgres() -> bool:
    """Verifica si hay datos en PostgreSQL para usar FTS."""
    global _use_postgres
    try:
        from src.database.models_noticias import Noticia
        count = Noticia.query.count()
        _use_postgres = count > 0
        return _use_postgres
    except Exception:
        _use_postgres = False
        return False


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
    """Estadísticas generales (PostgreSQL con fallback a CSV)."""
    # Intentar PostgreSQL primero
    if _check_postgres():
        try:
            from src.database.repository import NoticiasRepository
            stats = NoticiasRepository.estadisticas()
            stats['data_source'] = 'postgresql'
            return jsonify(stats)
        except Exception as e:
            logging.warning(f"Fallback a CSV: {e}")

    # Fallback a CSV
    stats = _get_stats()
    if stats is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404
    stats['data_source'] = 'csv'
    return jsonify(stats)


@main_bp.route('/api/noticias')
@login_required
def api_noticias():
    """Listado paginado de noticias con filtros de relevancia."""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    only_nna = request.args.get('only_nna', 'false').lower() == 'true'
    clasificacion = request.args.get('clasificacion', '').strip()
    orden = request.args.get('orden', 'fecha')

    # Intentar PostgreSQL primero
    if _check_postgres():
        try:
            from src.database.repository import NoticiasRepository
            result = NoticiasRepository.listar(
                page=page,
                per_page=per_page,
                clasificacion=clasificacion or None,
                solo_nna=only_nna,
                orden=orden,
            )
            result['data_source'] = 'postgresql'
            return jsonify(result)
        except Exception as e:
            logging.warning(f"PostgreSQL fallback: {e}")

    # Fallback a CSV
    if _current_data is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404

    data = _current_data.copy()

    if only_nna:
        data = data[data['menores_identificados'] == 'Si']

    if clasificacion:
        col = 'clasificacion_final' if 'clasificacion_final' in data.columns else 'clasificacion'
        if col in data.columns:
            data = data[data[col] == clasificacion]

    # Determinar columna de ordenamiento de respaldo
    sort_col = 'relevancia_final' if 'relevancia_final' in data.columns else 'score_compuesto'

    # Ordenar por fecha (más reciente primero)
    if 'fecha' in data.columns:
        try:
            data['_fecha_sort'] = pd.to_datetime(data['fecha'], errors='coerce')
            data = data.sort_values('_fecha_sort', ascending=False, na_position='last')
            data = data.drop(columns=['_fecha_sort'])
        except Exception:
            if sort_col in data.columns:
                data = data.sort_values(sort_col, ascending=False)
    elif sort_col in data.columns:
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
    """Búsqueda de noticias con FTS PostgreSQL o sinónimos CSV."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Query requerido'}), 400

    # Intentar FTS en PostgreSQL primero
    if _check_postgres():
        try:
            from src.database.repository import NoticiasRepository
            clasificacion = request.args.get('clasificacion', '').strip() or None
            solo_nna = request.args.get('only_nna', 'false').lower() == 'true'
            limit = int(request.args.get('limit', 20))

            result = NoticiasRepository.buscar_fts(
                query=query,
                limit=limit,
                clasificacion=clasificacion,
                solo_nna=solo_nna,
            )
            result['data_source'] = 'postgresql_fts'
            return jsonify(result)
        except Exception as e:
            logging.warning(f"FTS fallback: {e}")

    # Fallback a búsqueda CSV con sinónimos
    if _current_data is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404

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
    """Ejecuta el pipeline completo de análisis (v5.0 TT2)."""
    try:
        global _analyzer
        _analyzer = SimplifiedNewsAnalyzer()

        # Parámetros opcionales del request
        enable_semantic = request.args.get('semantic', 'true').lower() == 'true'
        enable_bertopic = request.args.get('bertopic', 'true').lower() == 'true'
        enable_postgres = request.args.get('postgres', 'true').lower() == 'true'

        _analyzer.run_complete_analysis(
            num_topics=5,
            n_clusters=4,
            save_intermediate=False,
            enable_semantic=enable_semantic,
            enable_bertopic=enable_bertopic,
            enable_postgres=enable_postgres,
        )

        if _load_data():
            return jsonify({
                'status': 'success',
                'message': 'Análisis v5.0 completado exitosamente',
                'stats': _get_stats(),
                'features': {
                    'semantic_detection': enable_semantic,
                    'bertopic_clustering': enable_bertopic,
                    'postgresql_persistence': enable_postgres,
                },
            })
        return jsonify({'error': 'Análisis completado pero error cargando datos'}), 500
    except Exception as e:
        logging.error(f"Error en análisis: {e}")
        return jsonify({'error': f'Error ejecutando análisis: {e}'}), 500


@main_bp.route('/api/export/csv')
@login_required
def api_export_csv():
    """Exporta los datos analizados como CSV."""
    # Intentar desde PostgreSQL primero
    if _check_postgres():
        try:
            from src.database.repository import NoticiasRepository
            export_path = os.path.join(DATA_DIR, 'export_noticias.csv')
            NoticiasRepository.exportar_a_csv(export_path)
            return send_file(export_path, as_attachment=True, download_name='noticias_nna.csv')
        except Exception as e:
            logging.warning(f"Export PostgreSQL fallback: {e}")

    if _current_data is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404
    try:
        export_path = os.path.join(DATA_DIR, 'export_noticias.csv')
        _current_data.to_csv(export_path, index=False, encoding='utf-8')
        return send_file(export_path, as_attachment=True, download_name='noticias_nna.csv')
    except Exception as e:
        return jsonify({'error': f'Error exportando: {e}'}), 500


@main_bp.route('/api/charts/temporal')
@login_required
def api_charts_temporal():
    """Datos para gráfico temporal: noticias por mes."""
    if _check_postgres():
        try:
            from src.database.models_noticias import Noticia
            from sqlalchemy import func
            results = (
                Noticia.query
                .with_entities(
                    func.to_char(Noticia.fecha_publicacion, 'YYYY-MM').label('mes'),
                    func.count().label('total'),
                )
                .filter(Noticia.fecha_publicacion.isnot(None))
                .group_by(func.to_char(Noticia.fecha_publicacion, 'YYYY-MM'))
                .order_by(func.to_char(Noticia.fecha_publicacion, 'YYYY-MM'))
                .all()
            )
            return jsonify({
                'labels': [r.mes for r in results],
                'total': [r.total for r in results],
                'nna': [],
            })
        except Exception as e:
            logging.warning(f"Charts temporal PG error: {e}")

    # Fallback a CSV
    if _current_data is None:
        return jsonify({'labels': [], 'total': [], 'nna': []})

    df = _current_data.copy()
    if 'fecha' not in df.columns:
        return jsonify({'labels': [], 'total': [], 'nna': []})

    df['_fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    df = df.dropna(subset=['_fecha'])
    df['_mes'] = df['_fecha'].dt.strftime('%Y-%m')
    grouped = df.groupby('_mes').agg(
        total=('_mes', 'size'),
        nna=('menores_identificados', lambda x: (x == 'Si').sum()),
    ).reset_index().sort_values('_mes')

    return jsonify({
        'labels': grouped['_mes'].tolist(),
        'total': grouped['total'].tolist(),
        'nna': grouped['nna'].astype(int).tolist(),
    })


@main_bp.route('/api/charts/relevancia')
@login_required
def api_charts_relevancia():
    """Datos para gráfico de distribución de relevancia."""
    if _check_postgres():
        try:
            from src.database.models_noticias import Noticia
            from sqlalchemy import func
            results = (
                Noticia.query
                .with_entities(
                    Noticia.clasificacion,
                    func.count().label('count'),
                )
                .group_by(Noticia.clasificacion)
                .all()
            )
            data = {r.clasificacion: r.count for r in results}
            return jsonify({
                'alta': data.get('Alta', 0),
                'media': data.get('Media', 0),
                'baja': data.get('Baja', 0),
                'no_relevante': data.get('No relevante', 0),
            })
        except Exception as e:
            logging.warning(f"Charts relevancia PG error: {e}")

    if _current_data is None:
        return jsonify({'alta': 0, 'media': 0, 'baja': 0, 'no_relevante': 0})

    col = 'clasificacion_final' if 'clasificacion_final' in _current_data.columns else 'clasificacion'
    if col not in _current_data.columns:
        return jsonify({'alta': 0, 'media': 0, 'baja': 0, 'no_relevante': 0})

    counts = _current_data[col].value_counts()
    return jsonify({
        'alta': int(counts.get('Alta', 0)),
        'media': int(counts.get('Media', 0)),
        'baja': int(counts.get('Baja', 0)),
        'no_relevante': int(counts.get('No relevante', 0)),
    })


@main_bp.route('/api/charts/estados')
@login_required
def api_charts_estados():
    """Datos para gráfico de distribución geográfica por estado de México."""
    import re

    ESTADOS = {
        'Aguascalientes': r'\baguascalientes\b',
        'Baja California': r'\bbaja\s+california\b',
        'Campeche': r'\bcampeche\b',
        'Chiapas': r'\bchiapas\b',
        'Chihuahua': r'\bchihuahua\b',
        'CDMX': r'\bcdmx\b|\bciudad\s+de\s+m[eé]xico\b|\biztapalapa\b|\btl[aá]huac\b',
        'Coahuila': r'\bcoahuila\b',
        'Colima': r'\bcolima\b',
        'Durango': r'\bdurango\b',
        'Estado de México': r'\bestado\s+de\s+m[eé]xico\b|\becatepec\b|\bneza\b|\btlalnepantla\b',
        'Guanajuato': r'\bguanajuato\b|\bcelaya\b|\birapuato\b|\ble[oó]n\b',
        'Guerrero': r'\bguerrero\b|\bacapulco\b|\bchilpancingo\b|\biguala\b',
        'Hidalgo': r'\bhidalgo\b|\bpachuca\b',
        'Jalisco': r'\bjalisco\b|\bguadalajara\b|\bzapopan\b',
        'Michoacán': r'\bmichoacán\b',
        'Morelos': r'\bmorelos\b|\bcuernavaca\b',
        'Nayarit': r'\bnayarit\b|\btepic\b',
        'Nuevo León': r'\bnuevo\s+le[oó]n\b|\bmonterrey\b',
        'Oaxaca': r'\boaxaca\b',
        'Puebla': r'\bpuebla\b',
        'Querétaro': r'\bquer[eé]taro\b',
        'Quintana Roo': r'\bquintana\s+roo\b|\bcancún\b',
        'San Luis Potosí': r'\bsan\s+luis\s+potos[ií]\b',
        'Sinaloa': r'\bsinaloa\b|\bculiac[aá]n\b|\bmazatl[aá]n\b',
        'Sonora': r'\bsonora\b|\bhermosillo\b',
        'Tabasco': r'\btabasco\b|\bvillahermosa\b',
        'Tamaulipas': r'\btamaulipas\b|\breynosa\b|\bmatamoros\b|\bnuevo\s+laredo\b',
        'Tlaxcala': r'\btlaxcala\b',
        'Veracruz': r'\bveracruz\b|\bxalapa\b|\bcoatzacoalcos\b',
        'Yucatán': r'\byucat[aá]n\b|\bm[eé]rida\b',
        'Zacatecas': r'\bzacatecas\b',
    }

    # Obtener datos
    if _check_postgres():
        try:
            from src.database.models_noticias import Noticia
            noticias = Noticia.query.with_entities(
                Noticia.titulo, Noticia.contenido
            ).all()
            textos = [f"{n.titulo} {n.contenido or ''}" for n in noticias]
        except Exception:
            textos = []
    elif _current_data is not None:
        textos = (
            _current_data['titulo'].fillna('') + ' ' +
            _current_data.get('contenido', pd.Series(dtype=str)).fillna('')
        ).tolist()
    else:
        textos = []

    # Contar menciones por estado
    result = {}
    for estado, pattern in ESTADOS.items():
        count = sum(1 for t in textos if re.search(pattern, t, re.IGNORECASE))
        if count > 0:
            result[estado] = count

    # Ordenar por frecuencia descendente, top 15
    sorted_result = dict(sorted(result.items(), key=lambda x: x[1], reverse=True)[:15])

    return jsonify({
        'labels': list(sorted_result.keys()),
        'values': list(sorted_result.values()),
    })


@main_bp.route('/api/charts/fuentes')
@login_required
def api_charts_fuentes():
    """Top 10 fuentes por número de noticias."""
    if _check_postgres():
        try:
            from src.database.models_noticias import Noticia
            from sqlalchemy import func
            results = (
                Noticia.query
                .with_entities(
                    Noticia.fuente,
                    func.count().label('count'),
                )
                .group_by(Noticia.fuente)
                .order_by(func.count().desc())
                .limit(10)
                .all()
            )
            return jsonify({
                'labels': [r.fuente or 'Desconocida' for r in results],
                'values': [r.count for r in results],
            })
        except Exception as e:
            logging.warning(f"Charts fuentes PG error: {e}")

    if _current_data is None:
        return jsonify({'labels': [], 'values': []})

    counts = _current_data['fuente'].value_counts().head(10)
    return jsonify({
        'labels': counts.index.tolist(),
        'values': counts.values.tolist(),
    })


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
