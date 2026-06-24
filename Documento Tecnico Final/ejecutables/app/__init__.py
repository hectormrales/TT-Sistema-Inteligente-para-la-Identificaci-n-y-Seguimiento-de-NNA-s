# app/__init__.py — Application Factory
"""
Punto central de creación de la aplicación Flask.
Uso: from app import create_app
"""

import os

from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()


# ── Diccionarios de mapeo para nombres de fuentes (OE-1) ────────
DOMAIN_NAMES = {
    'jornada.com.mx': 'La Jornada',
    'proceso.com.mx': 'Proceso',
    'elsoldemexico.com.mx': 'El Sol de México',
    'elfinanciero.com.mx': 'El Financiero',
    'excelsior.com.mx': 'Excélsior',
    'piedepagina.mx': 'Pie de Página',
    'contralinea.com.mx': 'Contralínea',
    'razon.com.mx': 'La Razón',
    'informador.mx': 'El Informador',
    'lajornadadeoriente.com.mx': 'La Jornada de Oriente',
    'cimacnoticias.com.mx': 'Cimacnoticias',
    'luchadoras.mx': 'Luchadoras',
    'eleconomista.com.mx': 'El Economista',
    'elpais.com': 'El País',
    'bbci.co.uk': 'BBC Mundo',
    'elsoldetoluca.com.mx': 'El Sol de Toluca',
    'elsoldepuebla.com.mx': 'El Sol de Puebla',
    'diariodexalapa.com.mx': 'Diario de Xalapa',
    'noroeste.com.mx': 'Noroeste',
}

SECTION_SUFFIXES = {
    '/politica': ' (Política)',
    '/estados': ' (Estados)',
    '/sociedad': ' (Sociedad)',
    '/justicia': ' (Justicia)',
    '/nacional': ' (Nacional)',
    '/seguridad': ' (Seguridad)',
    '/policiaca': ' (Policiaca)',
}


def create_app() -> Flask:
    """Crea y configura la aplicación Flask."""

    app = Flask(__name__, template_folder='templates')

    # ── Configuración ───────────────────────────────────────
    from config import Config
    app.config.from_object(Config)

    if not app.config.get('SECRET_KEY'):
        raise RuntimeError(
            "SECRET_KEY no definida. "
            "Establécela en .env o como variable de entorno."
        )

    # ── Extensiones ─────────────────────────────────────────
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    CSRFProtect(app)

    from app.models import db, User
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # ── Blueprints ──────────────────────────────────────────
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.sources.routes import sources_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(sources_bp)
    
    from app.admin import admin_bp
    app.register_blueprint(admin_bp)

    # ── Base de datos ───────────────────────────────────────
    with app.app_context():
        _init_database(app)

    return app


def _init_database(app: Flask) -> None:
    """Crea tablas, usuario admin, fuentes predeterminadas y esquema FTS."""
    from app.models import db, User, NewsSource
    from sqlalchemy import inspect, text

    # Importar modelos de noticias para que SQLAlchemy los registre
    try:
        from src.database.models_noticias import (
            Noticia, Deteccion, ClusterSemantico, Entidad,
        )
    except ImportError:
        app.logger.warning("Modelos de noticias no disponibles")

    try:
        db.create_all()
    except Exception as e:
        app.logger.warning(f"Error en create_all (posible concurrencia): {e}")

    # ── Migración: agregar columna is_predefined si no existe ──
    try:
        inspector = inspect(db.engine)
        if inspector.has_table('news_sources'):
            columns = [c['name'] for c in inspector.get_columns('news_sources')]
            if 'is_predefined' not in columns:
                db.session.execute(text(
                    'ALTER TABLE news_sources '
                    'ADD COLUMN is_predefined BOOLEAN DEFAULT FALSE NOT NULL'
                ))
                db.session.commit()
                app.logger.info("Columna 'is_predefined' agregada a news_sources")
        
        if inspector.has_table('noticias'):
            columns = [c['name'] for c in inspector.get_columns('noticias')]
            if 'investigacion_json' not in columns:
                db.session.execute(text(
                    'ALTER TABLE noticias '
                    'ADD COLUMN investigacion_json JSONB'
                ))
                db.session.commit()
                app.logger.info("Columna 'investigacion_json' agregada a noticias")

    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Error en migración (posible concurrencia): {e}")

    # ── Usuario admin ──
    try:
        admin_password = os.environ.get('ADMIN_PASSWORD', 'Admin_NNA_2026!')
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@sistema-nna.local',
                is_admin=True,
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            app.logger.info("Usuario administrador creado")
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Error creando administrador (posible concurrencia): {e}")

    # ── Fuentes predeterminadas ──
    _seed_predefined_sources(app)

    # ── Esquema FTS para noticias (OE-3) ──
    try:
        from src.database.repository import init_fts_schema
        init_fts_schema()
        app.logger.info("Esquema FTS inicializado")
    except Exception as e:
        app.logger.warning(f"FTS no inicializado (normal en primer arranque): {e}")


def _seed_predefined_sources(app: Flask) -> None:
    """Inserta las fuentes predeterminadas de config.py en la base de datos."""
    from app.models import db, NewsSource
    from config import RSS_FEEDS
    from urllib.parse import urlparse, parse_qs, unquote

    # Obtener fuentes existentes por URL y por Nombre para mapeo
    existing_sources = {s.url: s for s in NewsSource.query.all()}

    added = 0
    updated = 0
    for url in RSS_FEEDS:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')

        # Determinar nombre
        if 'news.google.com' in domain:
            qs = parse_qs(parsed.query)
            query = unquote(qs.get('q', ['búsqueda'])[0])
            name = f'Google News: {query}'
        else:
            name = DOMAIN_NAMES.get(domain, domain)
            for path_key, suffix in SECTION_SUFFIXES.items():
                if path_key in parsed.path.lower():
                    name += suffix
                    break

        if url in existing_sources:
            # Si ya existe pero el nombre cambió, actualizamos
            source = existing_sources[url]
            if source.name != name:
                source.name = name
                updated += 1
            continue
        
        # Si la URL es nueva, verificar si es una actualización de una fuente por dominio
        # (Especial para Proceso/Excelsior que cambiaron URL)
        source_by_name = NewsSource.query.filter_by(name=name, is_predefined=True).first()
        if source_by_name:
            source_by_name.url = url
            updated += 1
            continue

        # Es una fuente totalmente nueva
        source = NewsSource(
            name=name,
            url=url,
            source_type='rss',
            is_active=True,
            is_predefined=True,
            last_status='pending',
        )
        db.session.add(source)
        added += 1

    if added or updated:
        try:
            db.session.commit()
            app.logger.info(
                f"Fuentes predeterminadas: {added} nuevas, {updated} actualizadas"
            )
        except Exception as e:
            db.session.rollback()
            app.logger.warning(f"Error actualizando fuentes: {e}")
