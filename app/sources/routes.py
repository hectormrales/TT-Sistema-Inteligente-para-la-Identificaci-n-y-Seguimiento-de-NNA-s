# app/sources/routes.py — API y vistas de gestión de fuentes de noticias
"""
Blueprint para CRUD de fuentes de noticias.
Permite agregar, editar, eliminar, activar/desactivar y probar fuentes.
Cada fuente se almacena en la base de datos y es usada por el collector.
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user

from app.models import db, NewsSource
from src.collection.scraper import DynamicScraper

sources_bp = Blueprint('sources', __name__, url_prefix='/fuentes')

logger = logging.getLogger(__name__)


# ── Vistas HTML ─────────────────────────────────────────────

@sources_bp.route('/')
@login_required
def index():
    """Página de gestión de fuentes."""
    return render_template('sources.html')


# ── API REST ────────────────────────────────────────────────

@sources_bp.route('/api/sources', methods=['GET'])
@login_required
def list_sources():
    """Lista todas las fuentes de noticias."""
    sources = NewsSource.query.order_by(NewsSource.created_at.desc()).all()
    return jsonify({
        'sources': [s.to_dict() for s in sources],
        'total': len(sources),
        'active': sum(1 for s in sources if s.is_active),
    })


@sources_bp.route('/api/sources', methods=['POST'])
@login_required
def add_source():
    """Agrega una nueva fuente de noticias."""
    data = request.get_json(silent=True) or {}

    url = data.get('url', '').strip()
    name = data.get('name', '').strip()
    source_type = data.get('source_type', 'auto').strip()
    notes = data.get('notes', '').strip()

    if not url:
        return jsonify({'error': 'La URL es obligatoria'}), 400

    # Validar URL básica
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'La URL debe comenzar con http:// o https://'}), 400

    # Verificar duplicado
    existing = NewsSource.query.filter_by(url=url).first()
    if existing:
        return jsonify({'error': 'Esta URL ya existe como fuente'}), 409

    # Si no dio nombre, generar uno del dominio
    if not name:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        name = parsed.netloc.replace('www.', '')

    # Validar source_type
    valid_types = ('auto', 'rss', 'sitemap', 'html')
    if source_type not in valid_types:
        source_type = 'auto'

    try:
        source = NewsSource(
            name=name,
            url=url,
            source_type=source_type,
            is_active=True,
            added_by=current_user.id,
            notes=notes,
            last_status='pending',
        )
        db.session.add(source)
        db.session.commit()

        logger.info(f"Fuente agregada: {name} ({url}) por {current_user.username}")
        return jsonify({
            'status': 'success',
            'message': f'Fuente "{name}" agregada correctamente',
            'source': source.to_dict(),
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error agregando fuente: {e}")
        return jsonify({'error': f'Error al agregar fuente: {str(e)}'}), 500


@sources_bp.route('/api/sources/<int:source_id>', methods=['PUT'])
@login_required
def update_source(source_id: int):
    """Actualiza una fuente existente."""
    source = db.session.get(NewsSource, source_id)
    if not source:
        return jsonify({'error': 'Fuente no encontrada'}), 404

    data = request.get_json(silent=True) or {}

    if 'name' in data:
        source.name = data['name'].strip()
    if 'url' in data:
        new_url = data['url'].strip()
        # Verificar que no sea duplicado
        existing = NewsSource.query.filter(
            NewsSource.url == new_url,
            NewsSource.id != source_id,
        ).first()
        if existing:
            return jsonify({'error': 'Esa URL ya está registrada'}), 409
        source.url = new_url
    if 'source_type' in data:
        source.source_type = data['source_type'].strip()
    if 'is_active' in data:
        source.is_active = bool(data['is_active'])
    if 'notes' in data:
        source.notes = data['notes'].strip()

    try:
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Fuente actualizada',
            'source': source.to_dict(),
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error actualizando: {str(e)}'}), 500


@sources_bp.route('/api/sources/<int:source_id>', methods=['DELETE'])
@login_required
def delete_source(source_id: int):
    """Elimina una fuente de noticias (solo personalizadas)."""
    source = db.session.get(NewsSource, source_id)
    if not source:
        return jsonify({'error': 'Fuente no encontrada'}), 404

    if source.is_predefined:
        return jsonify({
            'error': 'No se puede eliminar una fuente predeterminada del sistema. '
                     'Puedes desactivarla en su lugar.',
        }), 403

    name = source.name
    try:
        db.session.delete(source)
        db.session.commit()
        logger.info(f"Fuente eliminada: {name} por {current_user.username}")
        return jsonify({
            'status': 'success',
            'message': f'Fuente "{name}" eliminada',
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error eliminando: {str(e)}'}), 500


@sources_bp.route('/api/sources/<int:source_id>/toggle', methods=['POST'])
@login_required
def toggle_source(source_id: int):
    """Activa o desactiva una fuente."""
    source = db.session.get(NewsSource, source_id)
    if not source:
        return jsonify({'error': 'Fuente no encontrada'}), 404

    source.is_active = not source.is_active
    db.session.commit()

    estado = 'activada' if source.is_active else 'desactivada'
    return jsonify({
        'status': 'success',
        'message': f'Fuente "{source.name}" {estado}',
        'is_active': source.is_active,
    })


@sources_bp.route('/api/sources/<int:source_id>/test', methods=['POST'])
@login_required
def test_source(source_id: int):
    """
    Prueba una fuente: detecta su tipo, verifica robots.txt,
    y extrae un artículo de prueba.
    """
    source = db.session.get(NewsSource, source_id)
    if not source:
        return jsonify({'error': 'Fuente no encontrada'}), 404

    try:
        scraper = DynamicScraper(test_mode=True)
        probe = scraper.probe_url(source.url)

        # Intentar extraer algunos artículos (más para dar mejor prueba)
        method = source.source_type if source.source_type != 'auto' else 'auto'
        articles = scraper.scrape_source(source.url, method=method, max_articles=5)

        # Actualizar información de la fuente
        source.last_scraped = datetime.now(timezone.utc)
        source.crawl_delay = probe.get('crawl_delay')
        stealth_mode = probe.get('stealth_mode', False)

        if articles:
            source.last_status = 'ok'
            source.last_error = None
            source.articles_found = len(articles)
            # Auto-detectar tipo si es 'auto'
            if source.source_type == 'auto':
                detected_method = probe.get('recommended_method', 'html')
                # Si el artículo se obtuvo via stealth, marcar como html
                if stealth_mode and detected_method in ('none', 'blocked'):
                    detected_method = 'html'
                source.source_type = detected_method
        elif probe.get('can_scrape') is False:
            source.last_status = 'blocked'
            source.last_error = 'Bloqueado por robots.txt y sin acceso stealth'
        else:
            source.last_status = 'warning'
            source.last_error = 'No se encontraron artículos (la fuente es accesible pero no se detectaron noticias)'

        db.session.commit()
        scraper.close()

        return jsonify({
            'status': 'success',
            'probe': {
                'source_type': probe.get('source_type'),
                'can_scrape': probe.get('can_scrape', True),
                'stealth_mode': stealth_mode,
                'robots_txt': probe.get('robots', {}).get('has_robots', False),
                'crawl_delay': probe.get('crawl_delay'),
                'rss_feeds': probe.get('rss_feeds', []),
                'sitemaps': probe.get('sitemaps', []),
                'recommended_method': probe.get('recommended_method'),
            },
            'articles_found': len(articles),
            'sample_articles': [
                {
                    'titulo': a.get('titulo', '')[:100],
                    'contenido': a.get('contenido', '')[:200],
                    'enlace': a.get('enlace', ''),
                }
                for a in articles[:3]
            ],
            'source': source.to_dict(),
        })

    except Exception as e:
        source.last_status = 'error'
        source.last_error = str(e)[:200]
        db.session.commit()
        logger.error(f"Error probando fuente {source.name}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error al probar la fuente: {str(e)}',
        }), 500


@sources_bp.route('/api/sources/probe', methods=['POST'])
@login_required
def probe_url():
    """
    Sondea una URL antes de agregarla como fuente.
    No la guarda en la base de datos, solo detecta el tipo.
    """
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL requerida'}), 400
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'URL inválida'}), 400

    try:
        scraper = DynamicScraper()
        probe = scraper.probe_url(url)

        return jsonify({
            'status': 'success',
            'probe': {
                'url': url,
                'source_type': probe.get('source_type'),
                'can_scrape': probe.get('can_scrape', True),
                'robots_txt': probe.get('robots', {}).get('has_robots', False),
                'crawl_delay': probe.get('crawl_delay'),
                'rss_feeds': probe.get('rss_feeds', []),
                'sitemaps': probe.get('sitemaps', []),
                'recommended_method': probe.get('recommended_method'),
            },
        })
    except Exception as e:
        return jsonify({'error': f'Error al sondear URL: {str(e)}'}), 500
