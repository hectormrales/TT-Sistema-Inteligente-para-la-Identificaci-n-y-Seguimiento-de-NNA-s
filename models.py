# models.py — Modelos de base de datos del Sistema NNA
"""
Modelo de Usuario con hashing Argon2 para máxima seguridad.
Argon2id es el ganador del Password Hashing Competition y la
recomendación actual de OWASP para almacenamiento de contraseñas.
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Instancia global de SQLAlchemy (se vincula a la app en app_docker.py)
db = SQLAlchemy()

# Configuración de Argon2id (parámetros OWASP recomendados)
ph = PasswordHasher(
    time_cost=3,         # Iteraciones
    memory_cost=65536,   # 64 MB de memoria
    parallelism=4,       # Hilos paralelos
    hash_len=32,         # Longitud del hash
    salt_len=16,         # Longitud del salt
)


class User(UserMixin, db.Model):
    """
    Modelo de usuario para autenticación.
    
    Campos:
        id           — Identificador único (PK).
        username     — Nombre de usuario, único e indexado.
        email        — Correo electrónico, único.
        password_hash — Hash Argon2id de la contraseña.
        is_active    — Si la cuenta está habilitada.
        is_admin     — Si el usuario tiene permisos de administrador.
        created_at   — Fecha de creación de la cuenta.
        last_login   — Último inicio de sesión exitoso.
    """

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(
        db.String(80), unique=True, nullable=False, index=True
    )
    email = db.Column(
        db.String(120), unique=True, nullable=False, index=True
    )
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_login = db.Column(db.DateTime, nullable=True)

    # ------------------------------------------------------------------
    # Contraseñas
    # ------------------------------------------------------------------

    def set_password(self, password: str) -> None:
        """Hashea la contraseña con Argon2id y la almacena."""
        self.password_hash = ph.hash(password)

    def check_password(self, password: str) -> bool:
        """
        Verifica la contraseña contra el hash almacenado.
        Si Argon2 detecta que los parámetros cambiaron, re-hashea
        automáticamente (rehash transparente).
        """
        try:
            valid = ph.verify(self.password_hash, password)
            # Re-hash si los parámetros de Argon2 cambiaron
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

    # ------------------------------------------------------------------
    # Representación
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f'<User {self.username}>'
