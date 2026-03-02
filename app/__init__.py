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

    db.create_all()

    # ── Migración: agregar columna is_predefined si no existe ──
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

    # ── Usuario admin ──
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

    existing_urls = {s.url for s in NewsSource.query.all()}

    # Mapeo de dominios a nombres legibles
    DOMAIN_NAMES = {
        'jornada.com.mx': 'La Jornada',
        'proceso.com.mx': 'Proceso',
        'aristeguinoticias.com': 'Aristegui Noticias',
        'animalpolitico.com': 'Animal Político',
        'sinembargo.mx': 'Sin Embargo',
        'elsoldemexico.com.mx': 'El Sol de México',
        'elfinanciero.com.mx': 'El Financiero',
        'eluniversal.com.mx': 'El Universal',
        'milenio.com': 'Milenio',
        'excelsior.com.mx': 'Excélsior',
        'reporteindigo.com': 'Reporte Índigo',
        'piedepagina.mx': 'Pie de Página',
        'contralinea.com.mx': 'Contralínea',
        'sdpnoticias.com': 'SDP Noticias',
        'debate.com.mx': 'El Debate',
        'razon.com.mx': 'La Razón',
        'elheraldodemexico.com': 'El Heraldo de México',
        'informador.mx': 'El Informador',
        'zocalo.com.mx': 'Zócalo',
        'lajornadadeoriente.com.mx': 'La Jornada de Oriente',
        'cimacnoticias.com.mx': 'CIMAC Noticias',
        'luchadoras.mx': 'Luchadoras',
        'eleconomista.com.mx': 'El Economista',
        'elpais.com': 'El País México',
        'bbc.com': 'BBC Mundo',
        'elsoldetoluca.com.mx': 'El Sol de Toluca',
        'elsoldepuebla.com.mx': 'El Sol de Puebla',
        'diariodexalapa.com.mx': 'Diario de Xalapa',
        'noroeste.com.mx': 'Noroeste',
    }

    SECTION_SUFFIXES = {
        '/politica': ' – Política',
        '/estados': ' – Estados',
        '/sociedad': ' – Sociedad',
    }

    added = 0
    for url in RSS_FEEDS:
        if url in existing_urls:
            continue

        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')

        # Google News → nombre especial
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

    if added:
        db.session.commit()
        app.logger.info(
            f"Fuentes predeterminadas sembradas: {added} nuevas"
        )
