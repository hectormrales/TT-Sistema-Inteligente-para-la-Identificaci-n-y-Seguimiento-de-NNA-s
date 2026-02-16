# app/auth/forms.py — Formularios de autenticación
"""Formularios WTForms con protección CSRF automática."""

import re

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, ValidationError,
)

from app.models import User


class LoginForm(FlaskForm):
    """Formulario de inicio de sesión."""

    username = StringField('Usuario', validators=[
        DataRequired(message='El usuario es obligatorio.'),
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message='La contraseña es obligatoria.'),
    ])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Iniciar Sesión')


class RegistrationForm(FlaskForm):
    """Formulario de registro de usuarios."""

    username = StringField('Usuario', validators=[
        DataRequired(message='El usuario es obligatorio.'),
        Length(min=3, max=80, message='El usuario debe tener entre 3 y 80 caracteres.'),
    ])
    email = StringField('Correo Electrónico', validators=[
        DataRequired(message='El correo es obligatorio.'),
        Email(message='Ingresa un correo electrónico válido.'),
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message='La contraseña es obligatoria.'),
        Length(min=12, message='La contraseña debe tener mínimo 12 caracteres.'),
    ])
    password_confirm = PasswordField('Confirmar Contraseña', validators=[
        DataRequired(message='Confirma tu contraseña.'),
        EqualTo('password', message='Las contraseñas no coinciden.'),
    ])
    submit = SubmitField('Registrar')

    # --- Validaciones personalizadas ---

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Este nombre de usuario ya está en uso.')
        if not re.match(r'^[a-zA-Z0-9_]+$', field.data):
            raise ValidationError(
                'El usuario solo puede contener letras, números y guiones bajos.'
            )

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('Este correo electrónico ya está registrado.')

    def validate_password(self, field):
        """Política de contraseña robusta (OWASP)."""
        pwd = field.data
        errors = []
        if not re.search(r'[A-Z]', pwd):
            errors.append('al menos una mayúscula')
        if not re.search(r'[a-z]', pwd):
            errors.append('al menos una minúscula')
        if not re.search(r'\d', pwd):
            errors.append('al menos un número')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', pwd):
            errors.append('al menos un carácter especial (!@#$%^&*…)')
        if errors:
            raise ValidationError(
                'La contraseña debe contener: ' + ', '.join(errors) + '.'
            )
