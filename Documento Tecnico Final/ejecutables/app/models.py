# app/models.py — Modelos de base de datos del Sistema NNA
"""
Modelo de Usuario con hashing Argon2id (ganador de la Password Hashing
Competition y recomendación actual de OWASP).
"""

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Instancia global de SQLAlchemy — se vincula a la app en create_app()
db = SQLAlchemy()

# Configuración Argon2id (parámetros OWASP recomendados)
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,   # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


class User(UserMixin, db.Model):
    """Modelo de usuario para autenticación."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_login = db.Column(db.DateTime, nullable=True)

    # --- Contraseñas ---

    def set_password(self, password: str) -> None:
        """Hashea la contraseña con Argon2id."""
        self.password_hash = ph.hash(password)

    def check_password(self, password: str) -> bool:
        """Verifica la contraseña; re-hashea si los parámetros cambiaron."""
        try:
            valid = ph.verify(self.password_hash, password)
            if valid and ph.check_needs_rehash(self.password_hash):
                self.password_hash = ph.hash(password)
                db.session.commit()
            return valid
        except VerifyMismatchError:
            return False

    def update_last_login(self) -> None:
        """Registra la fecha/hora del último login exitoso."""
        self.last_login = datetime.now(timezone.utc)
        db.session.commit()

    def __repr__(self) -> str:
        return f'<User {self.username}>'


class NewsSource(db.Model):
    """Modelo para fuentes de noticias gestionadas por el usuario."""

    __tablename__ = 'news_sources'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), unique=True, nullable=False)
    source_type = db.Column(
        db.String(20), nullable=False, default='auto',
        comment='auto | rss | sitemap | html',
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_predefined = db.Column(db.Boolean, default=False, nullable=False)
    added_by = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=True,
    )
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_scraped = db.Column(db.DateTime, nullable=True)
    last_status = db.Column(
        db.String(30), default='pending',
        comment='pending | ok | error | blocked',
    )
    last_error = db.Column(db.Text, nullable=True)
    articles_found = db.Column(db.Integer, default=0)
    crawl_delay = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Relación con usuario
    owner = db.relationship('User', backref=db.backref('sources', lazy='dynamic'))

    def to_dict(self) -> dict:
        """Serializa la fuente a diccionario."""
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'source_type': self.source_type,
            'is_active': self.is_active,
            'is_predefined': self.is_predefined,
            'added_by': self.added_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_scraped': self.last_scraped.isoformat() if self.last_scraped else None,
            'last_status': self.last_status,
            'last_error': self.last_error,
            'articles_found': self.articles_found,
            'crawl_delay': self.crawl_delay,
            'notes': self.notes,
        }

    def __repr__(self) -> str:
        return f'<NewsSource {self.name} ({self.source_type})>'


class SesionBusqueda(db.Model):
    """Modelo de sesión de recolección/workspace para aislamiento de datos."""

    __tablename__ = 'sesiones_busqueda'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_descriptivo = db.Column(db.String(200), nullable=False)
    fecha_creacion = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    parametros_busqueda = db.Column(db.JSON, nullable=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'nombre_descriptivo': self.nombre_descriptivo,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            'parametros_busqueda': self.parametros_busqueda,
        }

    def __repr__(self) -> str:
        return f'<SesionBusqueda {self.nombre_descriptivo}>'
