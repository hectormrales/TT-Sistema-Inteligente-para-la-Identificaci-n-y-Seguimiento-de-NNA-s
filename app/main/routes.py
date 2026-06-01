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
    """Carga resultados del último análisis desde CSV."""
    global _current_data
    if os.path.exists(DATA_FILE):
        try:
            _current_data = pd.read_csv(DATA_FILE)
            logging.info(f"Datos cargados: {len(_current_data)} noticias desde análisis")
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
    import pandas as pd
    
    def safe_int(val, default=-1):
        if pd.isna(val):
            return default
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default
            
    contenido = str(row.get('contenido', ''))
    return {
        'id': int(idx),
        'titulo': row.get('titulo', ''),
        'contenido': contenido[:200] + '...' if len(contenido) > 200 else contenido,
        'fecha': row.get('fecha', ''),
        'fuente': row.get('fuente', ''),
        'enlace': row.get('enlace', ''),
        'menores_identificados': row.get('menores_identificados', 'No'),
        'cluster': safe_int(row.get('cluster', -1)),
        'topic_id': safe_int(row.get('topic_id', -1)),
        'similitud': float(row.get('max_similarity', 0)) if not pd.isna(row.get('max_similarity')) else 0.0,
        'score_feminicidio': float(row.get('score_feminicidio', 0)) if not pd.isna(row.get('score_feminicidio')) else 0.0,
        'score_nna': float(row.get('score_nna', 0)) if not pd.isna(row.get('score_nna')) else 0.0,
        'score_compuesto': float(row.get('score_compuesto', 0)) if not pd.isna(row.get('score_compuesto')) else 0.0,
        'relevancia_final': float(row.get('relevancia_final', row.get('score_compuesto', 0))) if not pd.isna(row.get('relevancia_final')) else 0.0,
        'clasificacion': row.get('clasificacion_final', row.get('clasificacion', 'No relevante')),
    }


# ── Rutas de la interfaz ───────────────────────────────────

@main_bp.route('/')
@login_required
def index():
    """Dashboard principal."""
    # Cargar datos al primer acceso si no están en memoria
    if _current_data is None:
        _load_data()
    return render_template('dashboard.html')


# ── API REST ────────────────────────────────────────────────

@main_bp.route('/api/sessions')
@login_required
def api_sessions():
    """Lista todas las sesiones de búsqueda (historial)."""
    if _check_postgres():
        try:
            from app.models import SesionBusqueda
            sessions = SesionBusqueda.query.order_by(SesionBusqueda.fecha_creacion.desc()).all()
            return jsonify({'sessions': [s.to_dict() for s in sessions]})
        except Exception as e:
            logging.error(f"Error fetching sessions: {e}")
            return jsonify({'error': str(e)}), 500
    return jsonify({'sessions': []})

@main_bp.route('/api/stats')
@login_required
def api_stats():
    """Estadísticas generales (PostgreSQL con fallback a CSV)."""
    # Intentar PostgreSQL primero
    if _check_postgres():
        try:
            from src.database.repository import NoticiasRepository
            sesion_id = request.args.get('sesion_id')
            if sesion_id == 'latest':
                from app.models import SesionBusqueda
                latest = SesionBusqueda.query.order_by(SesionBusqueda.fecha_creacion.desc()).first()
                sesion_id = latest.id if latest else None
            elif sesion_id == 'all' or not sesion_id:
                sesion_id = None
            else:
                try:
                    sesion_id = int(sesion_id)
                except ValueError:
                    sesion_id = None
                
            stats = NoticiasRepository.estadisticas(sesion_id=sesion_id)
            stats['data_source'] = 'postgresql'
            stats['current_sesion_id'] = sesion_id or 'all'
            return jsonify(stats)
        except Exception as e:
            logging.warning(f"Fallback a CSV: {e}")

    # Fallback a CSV
    if _current_data is None:
        _load_data()
    stats = _get_stats()
    if stats is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404
    stats['data_source'] = 'csv'
    return jsonify(stats)


@main_bp.route('/api/noticias')
@login_required
def api_noticias():
    """Listado paginado de noticias con filtros de relevancia."""
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = max(1, min(int(request.args.get('per_page', 10)), 100))
    except (ValueError, TypeError):
        per_page = 10
    only_nna = request.args.get('only_nna', 'false').lower() == 'true'
    clasificacion = request.args.get('clasificacion', '').strip()
    orden = request.args.get('orden', 'fecha')
    sesion_id = request.args.get('sesion_id')

    # Intentar PostgreSQL primero
    if _check_postgres():
        try:
            from src.database.repository import NoticiasRepository
            if sesion_id == 'latest':
                from app.models import SesionBusqueda
                latest = SesionBusqueda.query.order_by(SesionBusqueda.fecha_creacion.desc()).first()
                sesion_id = latest.id if latest else None
            elif sesion_id == 'all' or not sesion_id:
                sesion_id = None
            else:
                try:
                    sesion_id = int(sesion_id)
                except ValueError:
                    sesion_id = None
                
            result = NoticiasRepository.listar(
                page=page,
                per_page=per_page,
                clasificacion=clasificacion or None,
                solo_nna=only_nna,
                orden=orden,
                sesion_id=sesion_id,
            )
            result['data_source'] = 'postgresql'
            result['current_sesion_id'] = sesion_id or 'all'
            return jsonify(result)
        except Exception as e:
            logging.warning(f"PostgreSQL fallback: {e}")

    # Fallback a CSV
    if _current_data is None:
        _load_data()
    if _current_data is None:
        return jsonify({'error': 'No hay datos disponibles'}), 404

    data = _current_data.copy()

    if only_nna:
        data = data[data['menores_identificados'] == 'Si']

    if clasificacion:
        col = 'clasificacion_final' if 'clasificacion_final' in data.columns else 'clasificacion'
        if col in data.columns:
            data = data[data[col] == clasificacion]
    else:
        # Por defecto, ocultar las 'No relevante'
        col = 'clasificacion_final' if 'clasificacion_final' in data.columns else 'clasificacion'
        if col in data.columns:
            data = data[data[col] != 'No relevante']

    # Determinar ordenamiento: fecha (más reciente) o relevancia (más alta)
    sort_col = 'relevancia_final' if 'relevancia_final' in data.columns else 'score_compuesto'

    if orden == 'relevancia' and sort_col in data.columns:
        data = data.sort_values(sort_col, ascending=False)
    elif 'fecha' in data.columns:
        try:
            data['_fecha_sort'] = pd.to_datetime(data['fecha'], errors='coerce', utc=True)
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
            sesion_id = request.args.get('sesion_id')
            if sesion_id and sesion_id != 'all':
                if sesion_id == 'latest':
                    from app.models import SesionBusqueda
                    latest = SesionBusqueda.query.order_by(SesionBusqueda.fecha_creacion.desc()).first()
                    sesion_id = latest.id if latest else None
                else:
                    try:
                        sesion_id = int(sesion_id)
                    except ValueError:
                        sesion_id = None
            else:
                sesion_id = None

            result = NoticiasRepository.buscar_fts(
                query=query,
                limit=limit,
                clasificacion=clasificacion,
                solo_nna=solo_nna,
                sesion_id=sesion_id,
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


import threading

# ── Estado del análisis en background ──────────────────────
_analysis_status = {
    'running': False,
    'last_run': None,
    'last_result': None,
    'error': None,
}
_analysis_lock = threading.Lock()


def _run_analysis_background(enable_semantic, enable_bertopic, enable_postgres, start_date, end_date, scraper_type, app, sesion_id=None):
    """Ejecuta el pipeline completo en background (hilo separado)."""
    global _analysis_status
    try:
        with app.app_context():
            analyzer = SimplifiedNewsAnalyzer()
            analyzer.run_complete_analysis(
                num_topics=5,
                n_clusters=4,
                save_intermediate=False,
                enable_semantic=enable_semantic,
                enable_bertopic=enable_bertopic,
                enable_postgres=enable_postgres,
                start_date=start_date,
                end_date=end_date,
                scraper_type=scraper_type,
                sesion_id=sesion_id,
            )

            # Recargar datos después del análisis
            _load_data()
            stats = _get_stats()

        with _analysis_lock:
            _analysis_status.update({
                'running': False,
                'last_run': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'last_result': stats,
                'error': None,
            })
        logging.info("Análisis background completado exitosamente")

    except Exception as e:
        logging.error(f"Error en análisis background: {e}")
        with _analysis_lock:
            _analysis_status.update({
                'running': False,
                'error': str(e),
            })


@main_bp.route('/api/analyze')
@login_required
def api_analyze():
    """Ejecuta el pipeline completo (scraping + análisis) en background."""
    global _analysis_status

    with _analysis_lock:
        if _analysis_status['running']:
            return jsonify({
                'status': 'already_running',
                'message': 'Ya hay un análisis en ejecución. Consulta /api/analyze/status',
            })

    # Parámetros opcionales del request
    enable_semantic = request.args.get('semantic', 'true').lower() == 'true'
    enable_bertopic = request.args.get('bertopic', 'true').lower() == 'true'
    enable_postgres = request.args.get('postgres', 'true').lower() == 'true'
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    scraper_type = request.args.get('scraper', 'all')
    
    from app.models import db, SesionBusqueda
    
    # Crear la nueva sesión
    nombre_sesion = f"Búsqueda: {datetime.now().strftime('%d/%b/%Y %H:%M')}"
    nueva_sesion = SesionBusqueda(
        nombre_descriptivo=nombre_sesion,
        parametros_busqueda={
            'start_date': start_date,
            'end_date': end_date,
            'scraper_type': scraper_type
        }
    )
    db.session.add(nueva_sesion)
    db.session.commit()
    sesion_id = nueva_sesion.id

    with _analysis_lock:
        _analysis_status.update({
            'running': True,
            'error': None,
            'last_result': None,
        })

    # Obtener la app Flask actual para pasarla al hilo de fondo
    from flask import current_app
    app = current_app._get_current_object()

    # Lanzar en hilo de fondo (daemon=True para que muera con el worker)
    thread = threading.Thread(
        target=_run_analysis_background,
        args=(enable_semantic, enable_bertopic, enable_postgres, start_date, end_date, scraper_type, app, sesion_id),
        daemon=True,
    )
    thread.start()

    return jsonify({
        'status': 'started',
        'sesion_id': sesion_id,
        'message': 'Recolección y análisis iniciados. Consulta /api/analyze/status para ver el progreso.',
    })


@main_bp.route('/api/analyze/status')
@login_required
def api_analyze_status():
    """Estado del análisis en background."""
    with _analysis_lock:
        status = _analysis_status.copy()
    return jsonify(status)


@main_bp.route('/api/export/csv/raw')
@login_required
def api_export_raw_csv():
    """Exporta los datos crudos recolectados antes del filtrado."""
    raw_path = os.path.join(DATA_DIR, 'noticias_raw.csv')
    if not os.path.exists(raw_path):
        return jsonify({'error': 'No hay datos crudos disponibles'}), 404
    try:
        return send_file(raw_path, as_attachment=True, download_name='noticias_scraper_raw.csv')
    except Exception as e:
        return jsonify({'error': f'Error exportando: {e}'}), 500


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
    """Datos para gráfico temporal filtrado (Alta vs Media)."""
    if _check_postgres():
        try:
            from src.database.models_noticias import Noticia
            from sqlalchemy import func
            sesion_id = request.args.get('sesion_id')
            q = Noticia.query
            if sesion_id and sesion_id != 'all':
                if sesion_id == 'latest':
                    from app.models import SesionBusqueda
                    latest = SesionBusqueda.query.order_by(SesionBusqueda.fecha_creacion.desc()).first()
                    if latest:
                        q = q.filter(Noticia.sesion_id == latest.id)
                else:
                    try:
                        q = q.filter(Noticia.sesion_id == int(sesion_id))
                    except ValueError:
                        pass
            
            results = (
                q.with_entities(
                    func.to_char(Noticia.fecha, 'YYYY-MM').label('mes'),
                    Noticia.clasificacion,
                    func.count().label('count'),
                )
                .filter(Noticia.fecha.isnot(None))
                .group_by(func.to_char(Noticia.fecha, 'YYYY-MM'), Noticia.clasificacion)
                .order_by(func.to_char(Noticia.fecha, 'YYYY-MM'))
                .all()
            )
            
            data = {}
            for r in results:
                if r.mes not in data:
                    data[r.mes] = {'Alta': 0, 'Media': 0, 'Baja': 0, 'No relevante': 0}
                data[r.mes][r.clasificacion] = r.count
                
            labels = list(data.keys())
            return jsonify({
                'labels': labels,
                'alta': [data[m].get('Alta', 0) for m in labels],
                'media': [data[m].get('Media', 0) for m in labels]
            })
        except Exception as e:
            logging.warning(f"Charts temporal PG error: {e}")
            return jsonify({'labels': [], 'alta': [], 'media': []})
    return jsonify({'labels': [], 'alta': [], 'media': []})


@main_bp.route('/api/charts/relevancia')
@login_required
def api_charts_relevancia():
    """Datos para gráfico de distribución de relevancia (Legacy)."""
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
            return jsonify({'alta': 0, 'media': 0, 'baja': 0, 'no_relevante': 0})
    return jsonify({'alta': 0, 'media': 0, 'baja': 0, 'no_relevante': 0})

@main_bp.route('/api/charts/topics')
@login_required
def api_charts_topics():
    """Datos para gráfico de burbujas BERTopic."""
    if _check_postgres():
        try:
            from src.database.models_noticias import ClusterSemantico
            sesion_id = request.args.get('sesion_id')
            q = ClusterSemantico.query.filter(ClusterSemantico.es_outlier == False)
            if sesion_id and sesion_id != 'all':
                if sesion_id == 'latest':
                    from app.models import SesionBusqueda
                    latest = SesionBusqueda.query.order_by(SesionBusqueda.fecha_creacion.desc()).first()
                    if latest:
                        q = q.filter(ClusterSemantico.sesion_id == latest.id)
                else:
                    try:
                        q = q.filter(ClusterSemantico.sesion_id == int(sesion_id))
                    except ValueError:
                        pass
            clusters = q.all()
            data = []
            for c in clusters:
                terms = c.terminos_principales or []
                if isinstance(terms, dict):
                    terms = list(terms.keys())
                elif isinstance(terms, list) and len(terms) > 0 and isinstance(terms[0], list):
                    terms = [t[0] for t in terms]
                data.append({
                    'id': c.id,
                    'label': c.etiqueta or f"Tópico {c.id}",
                    'size': c.num_documentos,
                    'terms': terms[:5]
                })
            return jsonify({'topics': data})
        except Exception as e:
            logging.warning(f"Charts topics PG error: {e}")
            return jsonify({'topics': []})
    return jsonify({'topics': []})


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
            sesion_id = request.args.get('sesion_id')
            q = Noticia.query
            if sesion_id and sesion_id != 'all':
                if sesion_id == 'latest':
                    from app.models import SesionBusqueda
                    latest = SesionBusqueda.query.order_by(SesionBusqueda.fecha_creacion.desc()).first()
                    if latest:
                        q = q.filter(Noticia.sesion_id == latest.id)
                else:
                    try:
                        q = q.filter(Noticia.sesion_id == int(sesion_id))
                    except ValueError:
                        pass
            
            noticias = q.with_entities(
                Noticia.titulo, Noticia.contenido, Noticia.clasificacion
            ).all()
            
            result_alta = {}
            result_media = {}
            
            for estado, pattern in ESTADOS.items():
                alta_count = sum(1 for n in noticias if n.clasificacion == 'Alta' and re.search(pattern, f"{n.titulo} {n.contenido}", re.IGNORECASE))
                media_count = sum(1 for n in noticias if n.clasificacion == 'Media' and re.search(pattern, f"{n.titulo} {n.contenido}", re.IGNORECASE))
                
                if alta_count > 0 or media_count > 0:
                    result_alta[estado] = alta_count
                    result_media[estado] = media_count
                    
            # Ordenar por Alta DESC, luego Media DESC
            sorted_estados = sorted(result_alta.keys(), key=lambda x: (result_alta[x], result_media[x]), reverse=True)[:15]
            
            return jsonify({
                'labels': sorted_estados,
                'alta': [result_alta[e] for e in sorted_estados],
                'media': [result_media[e] for e in sorted_estados],
            })
        except Exception as e:
            logging.warning(f"Charts estados PG error: {e}")
            return jsonify({'labels': [], 'alta': [], 'media': []})
    return jsonify({'labels': [], 'alta': [], 'media': []})


@main_bp.route('/api/charts/fuentes')
@login_required
def api_charts_fuentes():
    """Top fuentes ordenadas por Tasa de Alta Relevancia."""
    if _check_postgres():
        try:
            from src.database.models_noticias import Noticia
            from sqlalchemy import func, case
            sesion_id = request.args.get('sesion_id')
            q = Noticia.query
            if sesion_id and sesion_id != 'all':
                if sesion_id == 'latest':
                    from app.models import SesionBusqueda
                    latest = SesionBusqueda.query.order_by(SesionBusqueda.fecha_creacion.desc()).first()
                    if latest:
                        q = q.filter(Noticia.sesion_id == latest.id)
                else:
                    try:
                        q = q.filter(Noticia.sesion_id == int(sesion_id))
                    except ValueError:
                        pass

            results = (
                q.with_entities(
                    Noticia.fuente,
                    func.count().label('total'),
                    func.sum(case((Noticia.clasificacion == 'Alta', 1), else_=0)).label('alta_count')
                )
                .filter(Noticia.fuente.isnot(None))
                .group_by(Noticia.fuente)
                .having(func.count() >= 3)
                .all()
            )
            
            processed = []
            for r in results:
                pct = (r.alta_count / r.total) * 100 if r.total > 0 else 0
                processed.append({
                    'fuente': r.fuente,
                    'total': r.total,
                    'alta': r.alta_count,
                    'pct': pct
                })
                
            processed.sort(key=lambda x: x['pct'], reverse=True)
            top_10 = processed[:10]
            
            return jsonify({
                'labels': [p['fuente'] for p in top_10],
                'values': [p['pct'] for p in top_10],
                'totals': [p['total'] for p in top_10]
            })
        except Exception as e:
            logging.warning(f"Charts fuentes PG error: {e}")
            return jsonify({'labels': [], 'values': [], 'totals': []})
    return jsonify({'labels': [], 'values': [], 'totals': []})


@main_bp.route('/health')
def health_check():
    """Health check para Docker (sin autenticación)."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'data_loaded': _current_data is not None,
        'data_size': len(_current_data) if _current_data is not None else 0,
    })


@main_bp.route('/api/history/clear', methods=['POST'])
@login_required
def api_clear_history():
    """Borra todo el historial (DB, CSVs y cache de URLs)."""
    # 1. Borrar DB
    db_cleared = False
    if _check_postgres():
        from src.database.repository import NoticiasRepository
        db_cleared = NoticiasRepository.clear_history()
    
    # 2. Borrar CSVs
    import glob
    csv_files = glob.glob(os.path.join(DATA_DIR, '*.csv'))
    for f in csv_files:
        try:
            os.remove(f)
        except Exception:
            pass
            
    # 3. Borrar cache de URLs para que el scraper vuelva a bajar todo
    seen_urls_path = os.path.join(DATA_DIR, 'seen_urls.json')
    if os.path.exists(seen_urls_path):
        try:
            os.remove(seen_urls_path)
        except Exception:
            pass
            
    # 4. Resetear variable global
    global _current_data
    _current_data = None
    
    return jsonify({
        'status': 'success',
        'message': 'Historial borrado correctamente. El próximo escaneo será desde cero.',
        'db_cleared': db_cleared
    })


# ── Deep Investigation ──────────────────────────────────────

_active_investigations = {}
_investigation_lock = threading.Lock()

def _run_investigation_bg(noticia_id, title, content, app):
    from src.analysis.investigator import DeepInvestigator
    from src.database.repository import NoticiasRepository
    with app.app_context():
        try:
            investigator = DeepInvestigator()
            result = investigator.investigate(title, content)
            
            # Guardar en base de datos
            NoticiasRepository.save_investigation(noticia_id, result)
            
            with _investigation_lock:
                _active_investigations[str(noticia_id)] = {
                    'status': 'done',
                    'result': result
                }
        except Exception as e:
            logging.error(f"Error en investigación bg: {e}")
            with _investigation_lock:
                _active_investigations[str(noticia_id)] = {
                    'status': 'error',
                    'error': str(e)
                }

@main_bp.route('/api/investigate/<int:noticia_id>', methods=['POST'])
@login_required
def api_investigate(noticia_id):
    from src.database.repository import NoticiasRepository
    noticia = NoticiasRepository.get_noticia(noticia_id)
    if not noticia:
        return jsonify({'error': 'Noticia no encontrada'}), 404
        
    # Check if already investigated
    if noticia.investigacion_json:
        return jsonify({
            'status': 'done',
            'result': noticia.investigacion_json
        })
        
    with _investigation_lock:
        status_info = _active_investigations.get(str(noticia_id))
        if status_info and status_info.get('status') == 'running':
            return jsonify({'status': 'running'})
            
        _active_investigations[str(noticia_id)] = {'status': 'running'}
        
    from flask import current_app
    app = current_app._get_current_object()
    t = threading.Thread(target=_run_investigation_bg, args=(noticia_id, noticia.titulo, noticia.contenido, app))
    t.start()
    
    return jsonify({'status': 'started'})

@main_bp.route('/api/investigate/status/<int:noticia_id>', methods=['GET'])
@login_required
def api_investigate_status(noticia_id):
    from src.database.repository import NoticiasRepository
    with _investigation_lock:
        status_info = _active_investigations.get(str(noticia_id))
        if not status_info:
            noticia = NoticiasRepository.get_noticia(noticia_id)
            if noticia and noticia.investigacion_json:
                return jsonify({'status': 'done', 'result': noticia.investigacion_json})
            return jsonify({'status': 'not_started'})
        return jsonify(status_info)

@main_bp.route('/api/identify-link', methods=['POST'])
@login_required
def api_identify_link():
    """Identifica un caso a partir de un link externo, investigando en la web."""
    data = request.json
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL requerida'}), 400
        
    from src.analysis.investigator import DeepInvestigator
    try:
        investigator = DeepInvestigator()
        result = investigator.investigate_url(url)
        
        if 'error' not in result and _check_postgres():
            from src.database.models_noticias import Noticia, db
            from datetime import datetime
            
            # Obtener el título, o usar el resumen/URL si no está disponible
            title = result.get('titulo', 'Noticia Externa (Identificación Manual)')
            if title == 'Noticia Externa (Identificación Manual)' and 'resumen' in result:
                title = result['resumen'][:100] + "..."
                
            nueva_noticia = Noticia(
                titulo=title,
                enlace=url,
                fecha=datetime.utcnow(),
                fuente='Investigación Manual',
                contenido=result.get('resumen', ''),
                score_feminicidio=1.0,
                score_nna=1.0,
                score_compuesto=1.0,
                clasificacion='Alta',
                investigacion_json=result
            )
            db.session.add(nueva_noticia)
            db.session.commit()
            
            result['noticia_id'] = nueva_noticia.id

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error identificando link: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/seguimiento/casos', methods=['GET'])
@login_required
def api_seguimiento_casos():
    """Obtiene todos los casos que han sido agregados a seguimiento."""
    if _check_postgres():
        try:
            from src.database.models_noticias import Noticia
            from sqlalchemy import desc, text
            
            # Filtrar en Python para evitar problemas de compatibilidad de dialectos SQL con JSON
            noticias_raw = Noticia.query.filter(
                Noticia.investigacion_json.isnot(None)
            ).order_by(desc(Noticia.fecha)).all()
            
            resultados = []
            for n in noticias_raw:
                inv = n.investigacion_json
                if inv and inv.get('en_seguimiento') is True:
                    dict_n = n.to_dict()
                    dict_n['investigacion_json'] = inv
                    resultados.append(dict_n)
                
            return jsonify({'casos': resultados})
        except Exception as e:
            logging.error(f"Error fetching seguimiento casos: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        # Fallback a un mock o vacío si no hay DB
        return jsonify({'casos': []})

@main_bp.route('/api/seguimiento/add/<int:noticia_id>', methods=['POST'])
@login_required
def api_add_to_seguimiento(noticia_id):
    """Agrega un caso investigado a la lista de seguimiento."""
    if _check_postgres():
        from src.database.repository import NoticiasRepository
        success = NoticiasRepository.add_to_seguimiento(noticia_id)
        if success:
            return jsonify({'status': 'success'})
        return jsonify({'error': 'No se pudo agregar a seguimiento. Verifique que el caso exista y esté investigado.'}), 400
    return jsonify({'error': 'La base de datos no está activa.'}), 500

@main_bp.route('/api/seguimiento/export/csv', methods=['GET'])
@login_required
def api_export_seguimiento_csv():
    """Exporta los casos en seguimiento a CSV con las columnas limpias e información de investigación."""
    if not _check_postgres():
        return jsonify({'error': 'La base de datos no está activa.'}), 500
        
    try:
        from src.database.models_noticias import Noticia
        from sqlalchemy import desc
        import csv
        import io
        from flask import make_response
        
        noticias_raw = Noticia.query.filter(
            Noticia.investigacion_json.isnot(None)
        ).order_by(desc(Noticia.fecha)).all()
        
        noticias = [n for n in noticias_raw if n.investigacion_json and n.investigacion_json.get('en_seguimiento') is True]
        
        output = io.StringIO()
        output.write('\ufeff')  # BOM para Excel (utf-8-sig)
        writer = csv.writer(output)
        
        # Headers
        writer.writerow([
            'ID Noticia', 'Fecha', 'Título', 'Ubicación (IA)', 'Víctimas Directas (IA)', 
            'NNA Afectados (IA)', 'Edades NNA (IA)', 'Situación Actual NNA (IA)', 
            'Score Feminicidio', 'Score NNA', 'Score Compuesto', 'Enlace Original', 'Resumen (IA)'
        ])
        
        for n in noticias:
            inv = n.investigacion_json or {}
            
            # Limpiar eded_nna
            edades = inv.get('edades_nna', inv.get('edades', 'No especificada'))
            if isinstance(edades, list):
                edades = ', '.join(map(str, edades))
            elif isinstance(edades, dict):
                edades = ', '.join(map(str, edades.values()))
                
            victimas = inv.get('victimas', 'No especificadas')
            if isinstance(victimas, list):
                victimas = ', '.join(map(str, victimas))
                
            writer.writerow([
                n.id,
                n.fecha.strftime('%Y-%m-%d %H:%M') if n.fecha else 'Desconocida',
                n.titulo,
                inv.get('ubicacion', 'No especificada'),
                victimas,
                inv.get('nna_afectados', inv.get('ninos_afectados', 0)),
                edades,
                inv.get('situacion_actual', 'No especificada'),
                round(n.score_feminicidio * 100, 1) if n.score_feminicidio else 0,
                round(n.score_nna * 100, 1) if n.score_nna else 0,
                round(n.score_compuesto * 100, 1) if n.score_compuesto else 0,
                n.enlace,
                inv.get('resumen_abstracto', inv.get('resumen', ''))
            ])
            
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=seguimiento_casos_nna.csv'
        response.headers['Content-type'] = 'text/csv; charset=utf-8'
        return response
    except Exception as e:
        logging.error(f"Error exportando seguimiento a CSV: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/seguimiento/export/pdf/<int:noticia_id>', methods=['GET'])
@login_required
def api_export_seguimiento_pdf(noticia_id):
    """Renderiza una vista optimizada para imprimir como PDF el expediente del caso."""
    if not _check_postgres():
        return "La base de datos no está activa.", 500
        
    try:
        from src.database.models_noticias import Noticia
        from datetime import datetime
        noticia = Noticia.query.get(noticia_id)
        
        if not noticia or not noticia.investigacion_json:
            return "Caso no encontrado o sin investigación.", 404
            
        return render_template('admin/pdf_case.html', 
                             noticia=noticia, 
                             inv=noticia.investigacion_json,
                             datetime=datetime)
    except Exception as e:
        logging.error(f"Error generando vista de PDF: {e}")
        return str(e), 500



# ── Errores ─────────────────────────────────────────────────

@main_bp.app_errorhandler(404)
def not_found(_error):
    return jsonify({'error': 'Endpoint no encontrado'}), 404


@main_bp.app_errorhandler(500)
def internal_error(_error):
    return jsonify({'error': 'Error interno del servidor'}), 500
