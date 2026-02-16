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
