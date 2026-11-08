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
from src.analysis.investigator import DeepInvestigator
from src.analysis.synonyms import SynonymDictionary
from src.database.models_noticias import Noticia, ExpedienteCaso

main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

# ── Estado global de datos ──────────────────────────────────

_current_data: pd.DataFrame | None = None
_analyzer: SimplifiedNewsAnalyzer | None = None
_use_postgres: bool = False  # Se activa si la tabla noticias tiene datos

DATA_DIR = os.environ.get('DATA_DIR', 'data')
LOGS_DIR = os.environ.get('LOGS_DIR', 'logs')
DATA_FILE = os.path.join(DATA_DIR, 'noticias_analyzed_simplified.csv')


def _check_postgres() -> bool:
    """Verifica si hay datos en la base de datos relacional para listados/estadísticas."""
    global _use_postgres
    try:
        count = Noticia.query.count()
        _use_postgres = count > 0
        return _use_postgres
    except Exception:
        _use_postgres = False
        return False


def _db_is_ready() -> bool:
    """Verifica si las tablas relacionales (`noticias` / `expedientes_casos`) están operativas."""
    try:
        Noticia.query.limit(1).all()
        return True
    except Exception:
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
    import json
    import pandas as pd
    
    def safe_int(val, default=-1):
        if pd.isna(val):
            return default
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default
            
    contenido = str(row.get('contenido', ''))
    inv_raw = row.get('investigacion_json', None)
    inv_dict = None
    if isinstance(inv_raw, dict):
        inv_dict = inv_raw
    elif isinstance(inv_raw, str) and inv_raw.strip().startswith('{'):
        try:
            inv_dict = json.loads(inv_raw)
        except Exception:
            inv_dict = None

    clasificacion_final = row.get('clasificacion_final', row.get('clasificacion', 'No relevante'))
    return {
        'id': int(idx),
        'titulo': row.get('titulo', ''),
        'contenido': contenido[:280] + '...' if len(contenido) > 280 else contenido,
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
        'clasificacion': clasificacion_final,
        'clasificacion_final': clasificacion_final,
        'investigacion_json': inv_dict,
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
            try:
                stats['total_expedientes'] = ExpedienteCaso.query.count()
                stats['expedientes_en_seguimiento'] = ExpedienteCaso.query.filter_by(en_seguimiento=True).count()
            except Exception:
                stats['total_expedientes'] = 0
                stats['expedientes_en_seguimiento'] = 0
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
        return jsonify({
            'total_noticias': 0,
            'noticias_nna': 0,
            'alta_relevancia': 0,
            'media_relevancia': 0,
            'baja_relevancia': 0,
            'clusters': 0,
            'topics': 0,
            'similitud_promedio': 0.0,
            'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_expedientes': 0,
            'expedientes_en_seguimiento': 0,
            'data_source': 'empty'
        }), 200
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
            sesion_id = request.args.get('sesion_id')
            q = Noticia.query.filter(Noticia.fecha.isnot(None))
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

            rows = q.with_entities(
                Noticia.fecha,
                Noticia.clasificacion_final,
                Noticia.clasificacion,
            ).all()

            data = {}
            for r in rows:
                if not r.fecha:
                    continue
                mes = r.fecha.strftime('%Y-%m')
                cls = r.clasificacion_final or r.clasificacion or 'No relevante'
                if mes not in data:
                    data[mes] = {'Alta': 0, 'Media': 0, 'Baja': 0, 'No relevante': 0}
                data[mes][cls] = data[mes].get(cls, 0) + 1

            labels = sorted(data.keys())
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
    """Datos para agrupación semántica por Entidad y Situación de NNA."""
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
                    'label': c.etiqueta or f"Grupo Semántico {c.id}",
                    'size': c.num_documentos,
                    'terms': terms[:5]
                })

            # Si no hay registros en ClusterSemantico, construir dinámicamente desde ExpedienteCaso / Noticia
            if not data:
                expedientes = ExpedienteCaso.query.all()
                grupos = {}
                for exp in expedientes:
                    estado = exp.estado or "Ubicación por confirmar"
                    situacion = (exp.situacion_actual or "Situación por verificar")[:55]
                    label = f"{estado} — {situacion}"
                    if label not in grupos:
                        grupos[label] = {'count': 0, 'terms': set()}
                    grupos[label]['count'] += max(1, exp.num_fuentes or 1)
                    if exp.municipio and exp.municipio != 'No especificado':
                        grupos[label]['terms'].add(exp.municipio)
                    if exp.victimas and exp.victimas != 'No especificada':
                        grupos[label]['terms'].add(exp.victimas[:35])
                for idx, (lbl, info) in enumerate(sorted(grupos.items(), key=lambda x: x[1]['count'], reverse=True), start=1):
                    data.append({
                        'id': idx,
                        'label': lbl,
                        'size': info['count'],
                        'terms': list(info['terms'])[:5] or ['Caso detectado por IA']
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
    """Borra todo el historial (DB, CSVs, metadata y cache de URLs)."""
    # 1. Borrar DB (SQLAlchemy unificado para SQLite y PostgreSQL)
    db_cleared = False
    try:
        from src.database.repository import NoticiasRepository
        from app.models import SesionBusqueda, db
        db_cleared = NoticiasRepository.clear_history()
        SesionBusqueda.query.delete()
        db.session.commit()
    except Exception as e:
        logger.warning(f"Aviso limpiando base de datos: {e}")
    
    # 2. Borrar CSVs y JSONs de resultados en DATA_DIR
    import glob
    for pattern in ('*.csv', 'noticias_*.json', 'seen_urls.json'):
        for f in glob.glob(os.path.join(DATA_DIR, pattern)):
            try:
                os.remove(f)
            except Exception:
                pass
            
    # 3. Resetear variables globales
    global _current_data, _use_postgres
    _current_data = None
    _use_postgres = False
    
    return jsonify({
        'status': 'success',
        'message': 'Historial borrado correctamente. El próximo escaneo será desde cero.',
        'db_cleared': db_cleared
    })


# ── Deep Investigation ──────────────────────────────────────

_active_investigations = {}
_investigation_lock = threading.Lock()

def _run_investigation_bg(noticia_id, title, content, app):
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
    data = request.json or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL requerida'}), 400
        
    try:
        investigator = DeepInvestigator()
        result = investigator.investigate_url(url)
        
        if 'error' not in result and _db_is_ready():
            from src.database.models_noticias import db
            from src.database.repository import NoticiasRepository
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
                relevancia_final=1.0,
                clasificacion='Alta',
                clasificacion_final='Alta',
                menores_identificados='Si',
                investigacion_json=result
            )
            db.session.add(nueva_noticia)
            db.session.flush()
            try:
                NoticiasRepository.vincular_o_crear_expediente(nueva_noticia, investigacion=result)
            except Exception as exp_err:
                logging.warning(f"No se pudo vincular expediente en identify-link: {exp_err}")
            db.session.commit()
            
            result['noticia_id'] = nueva_noticia.id
            if getattr(nueva_noticia, 'expediente_id', None):
                result['expediente_id'] = nueva_noticia.expediente_id

        return jsonify(result)
    except Exception as e:
        logging.error(f"Error identificando link: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/seguimiento/casos', methods=['GET'])
@login_required
def api_seguimiento_casos():
    """Obtiene los expedientes consolidados de casos y sus bitácoras de seguimiento."""
    if _db_is_ready():
        try:
            from src.database.models_noticias import ESTADOS_SEGUIMIENTO_VALIDOS, db
            from src.database.repository import NoticiasRepository
            from sqlalchemy import desc

            # Auto-vincular noticias heredadas con investigacion_json que aún no tengan expediente_id
            noticias_huerfanas = Noticia.query.filter(
                Noticia.investigacion_json.isnot(None),
                Noticia.expediente_id.is_(None),
            ).order_by(desc(Noticia.fecha)).all()

            dirty = False
            for n in noticias_huerfanas:
                inv = n.investigacion_json or {}
                es_seg = bool(inv.get('en_seguimiento'))
                es_alta = (n.clasificacion_final or n.clasificacion) == 'Alta'
                if es_seg or es_alta:
                    exp = NoticiasRepository.vincular_o_crear_expediente(
                        n,
                        investigacion=inv,
                        marcar_seguimiento=es_seg,
                    )
                    if exp:
                        dirty = True
            if dirty:
                db.session.commit()

            estado_filtro = request.args.get('estado', 'todos').strip().lower()
            solo_seguimiento = request.args.get('solo_seguimiento', 'false').lower() == 'true'

            todos_expedientes = NoticiasRepository.listar_expedientes(
                solo_en_seguimiento=False,
                estado_seguimiento=None,
            )

            conteo_estados = {
                'todos': len(todos_expedientes),
                'en_seguimiento': sum(1 for c in todos_expedientes if c.get('en_seguimiento')),
            }
            for est in ESTADOS_SEGUIMIENTO_VALIDOS:
                conteo_estados[est] = sum(
                    1 for c in todos_expedientes if c.get('estado_seguimiento') == est
                )

            if estado_filtro == 'en_seguimiento' or solo_seguimiento:
                casos_filtrados = [c for c in todos_expedientes if c.get('en_seguimiento')]
            elif estado_filtro in ESTADOS_SEGUIMIENTO_VALIDOS:
                casos_filtrados = [
                    c for c in todos_expedientes if c.get('estado_seguimiento') == estado_filtro
                ]
            else:
                casos_filtrados = todos_expedientes

            return jsonify({
                'casos': casos_filtrados,
                'conteo_estados': conteo_estados,
                'estados_validos': list(ESTADOS_SEGUIMIENTO_VALIDOS),
            })
        except Exception as e:
            logging.error(f"Error fetching seguimiento casos: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({
            'casos': [],
            'conteo_estados': {'todos': 0, 'en_seguimiento': 0},
            'estados_validos': [
                'detectado', 'en_verificacion', 'contacto_dif_fiscalia',
                'en_acompanamiento', 'archivado',
            ],
        })


@main_bp.route('/api/seguimiento/add/<int:noticia_id>', methods=['POST'])
@login_required
def api_add_to_seguimiento(noticia_id):
    """Agrega un caso investigado a la lista de seguimiento y vincula su expediente."""
    if _db_is_ready():
        from src.database.repository import NoticiasRepository
        success = NoticiasRepository.add_to_seguimiento(noticia_id)
        if success:
            noticia = NoticiasRepository.get_noticia(noticia_id)
            return jsonify({
                'status': 'success',
                'noticia_id': noticia_id,
                'expediente_id': getattr(noticia, 'expediente_id', None),
            })
        return jsonify({
            'error': 'No se pudo agregar a seguimiento. Verifique que el caso exista y esté investigado.'
        }), 400
    return jsonify({'error': 'La base de datos no está activa.'}), 500


@main_bp.route('/api/seguimiento/expediente/<int:expediente_id>/status', methods=['POST'])
@main_bp.route('/api/seguimiento/update-status', methods=['POST'])
@login_required
def api_update_seguimiento_status(expediente_id=None):
    """Actualiza el estado de seguimiento de un expediente y/o registra una nota en la bitácora."""
    if not _db_is_ready():
        return jsonify({'error': 'La base de datos no está activa.'}), 500

    data = request.get_json(silent=True) or {}
    target_id = expediente_id or data.get('expediente_id') or data.get('id')
    if not target_id:
        return jsonify({'error': 'ID de expediente requerido'}), 400

    try:
        target_id = int(target_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'ID de expediente inválido'}), 400

    estado_seguimiento = data.get('estado_seguimiento')
    nota = data.get('nota')
    en_seguimiento = data.get('en_seguimiento')

    from flask_login import current_user
    autor = data.get('autor') or getattr(current_user, 'username', None) or 'Analista ONG'

    from src.database.repository import NoticiasRepository
    try:
        expediente_dict = NoticiasRepository.actualizar_seguimiento_expediente(
            expediente_id=target_id,
            estado_seguimiento=estado_seguimiento,
            nota=nota,
            autor=autor,
            en_seguimiento=en_seguimiento,
        )
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400

    if not expediente_dict:
        return jsonify({'error': 'No se pudo actualizar el expediente (ID o estado inválido)'}), 400

    if hasattr(expediente_dict, 'to_dict'):
        expediente_dict = expediente_dict.to_dict()

    return jsonify({
        'status': 'success',
        'expediente': expediente_dict,
    })


@main_bp.route('/api/seguimiento/export/csv', methods=['GET'])
@login_required
def api_export_seguimiento_csv():
    """Exporta los expedientes de casos a CSV (UTF-8 con BOM para Excel)."""
    if not _db_is_ready():
        return jsonify({'error': 'La base de datos no está activa.'}), 500

    try:
        from src.database.repository import NoticiasRepository
        import csv
        import io
        from flask import make_response

        solo_seg = request.args.get('solo_seguimiento', 'false').lower() == 'true'
        estado_filtro = request.args.get('estado', '').strip().lower() or None
        if estado_filtro == 'todos':
            estado_filtro = None

        expedientes = NoticiasRepository.listar_expedientes(
            solo_en_seguimiento=solo_seg,
            estado_seguimiento=estado_filtro,
        )

        output = io.StringIO()
        output.write('\ufeff')  # BOM para Excel (utf-8-sig)
        writer = csv.writer(output)

        writer.writerow([
            'ID Expediente',
            'Estado de Seguimiento',
            'En Seguimiento Activo',
            'Fecha Detección',
            'Título del Caso',
            'Entidad Federativa',
            'Municipio / Alcaldía',
            'Ubicación Completa (IA)',
            'Víctima(s) Directa(s)',
            'NNA Afectados',
            'Edades NNA',
            'Situación Actual NNA',
            'Cita Textual de Evidencia',
            'Medios de Contacto Sugeridos',
            'Núm. Fuentes Vinculadas',
            'Fuentes / Enlaces',
            'Última Nota de Bitácora',
            'Resumen Ejecutivo (IA)',
        ])

        etiquetas_estado = {
            'detectado': 'Detectado',
            'en_verificacion': 'En verificación',
            'contacto_dif_fiscalia': 'Contacto DIF / Fiscalía',
            'en_acompanamiento': 'En acompañamiento',
            'archivado': 'Archivado',
        }

        for exp in expedientes:
            inv = exp.get('investigacion_json') or {}
            notas = exp.get('notas_seguimiento') or []
            ultima_nota = ''
            if isinstance(notas, list) and notas:
                last = notas[-1]
                if isinstance(last, dict):
                    ultima_nota = f"[{last.get('fecha', '')[:10]} - {last.get('autor', '')}] {last.get('texto', '')}"
                else:
                    ultima_nota = str(last)

            fuentes = exp.get('fuentes_json') or inv.get('fuentes') or []
            if isinstance(fuentes, list):
                fuentes_str = ' | '.join(str(f) for f in fuentes if f)
            else:
                fuentes_str = str(fuentes)

            fecha_str = (exp.get('fecha') or '')[:16].replace('T', ' ') or 'Desconocida'
            estado_raw = exp.get('estado_seguimiento', 'detectado')

            writer.writerow([
                f"EXP-{exp.get('id')}",
                etiquetas_estado.get(estado_raw, estado_raw),
                'Sí' if exp.get('en_seguimiento') else 'No',
                fecha_str,
                exp.get('titulo', ''),
                exp.get('estado', 'No especificado'),
                exp.get('municipio', 'No especificado'),
                exp.get('ubicacion', inv.get('ubicacion', 'No especificada')),
                exp.get('victimas', inv.get('victimas', 'No especificada')),
                exp.get('nna_afectados', inv.get('nna_afectados', 0)),
                exp.get('edades_nna', inv.get('edades_nna', 'No especificada')),
                exp.get('situacion_actual', inv.get('situacion_actual', 'No especificada')),
                exp.get('cita_textual_evidencia', inv.get('cita_textual_evidencia', '')),
                exp.get('medios_contacto', inv.get('medios_contacto', '')),
                exp.get('num_fuentes', 1),
                fuentes_str or exp.get('enlace', ''),
                ultima_nota,
                exp.get('resumen', inv.get('resumen', '')),
            ])

        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=expedientes_seguimiento_nna.csv'
        response.headers['Content-type'] = 'text/csv; charset=utf-8'
        return response
    except Exception as e:
        logging.error(f"Error exportando seguimiento a CSV: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/seguimiento/export/pdf/<int:noticia_id>', methods=['GET'])
@login_required
def api_export_seguimiento_pdf(noticia_id):
    """Renderiza una vista optimizada para imprimir como PDF el expediente del caso."""
    if not _db_is_ready():
        return "La base de datos no está activa.", 500

    try:
        from datetime import datetime
        tipo = request.args.get('tipo', '').lower()

        expediente = None
        noticia = None

        if tipo == 'expediente':
            expediente = ExpedienteCaso.query.get(noticia_id)
        else:
            noticia = Noticia.query.get(noticia_id)
            if noticia and noticia.expediente_id:
                expediente = ExpedienteCaso.query.get(noticia.expediente_id)
            elif not noticia:
                expediente = ExpedienteCaso.query.get(noticia_id)

        if expediente:
            exp_dict = expediente.to_dict()
            inv = exp_dict.get('investigacion_json') or {}
            if not noticia:
                # Objeto ligero compatible con la plantilla PDF
                class _CasoView:
                    pass
                noticia = _CasoView()
                noticia.id = expediente.id
                noticia.titulo = expediente.titulo_caso
                noticia.fuente = f"{getattr(expediente, 'num_noticias', 1) or 1} fuente(s) verificada(s)"
                noticia.fecha = getattr(expediente, 'created_at', None)
                noticia.clasificacion = "Alta Relevancia — Expediente Consolidado"
                noticia.enlace = (expediente.fuentes_json or [''])[0] if expediente.fuentes_json else ''
            return render_template(
                'admin/pdf_case.html',
                noticia=noticia,
                expediente=expediente,
                inv=inv,
                datetime=datetime,
            )

        if not noticia or not noticia.investigacion_json:
            return "Caso no encontrado o sin investigación.", 404

        return render_template(
            'admin/pdf_case.html',
            noticia=noticia,
            expediente=None,
            inv=noticia.investigacion_json,
            datetime=datetime,
        )
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
