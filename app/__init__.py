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

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # ── Base de datos ───────────────────────────────────────
    with app.app_context():
        _init_database(app)

    return app


def _init_database(app: Flask) -> None:
    """Crea tablas y usuario admin inicial si no existe."""
    from app.models import db, User

    db.create_all()

    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@sistema-nna.local',
            is_admin=True,
        )
        admin.set_password('Admin_NNA_2026!')
        db.session.add(admin)
        db.session.commit()
        app.logger.info("Usuario administrador creado (admin / Admin_NNA_2026!)")
