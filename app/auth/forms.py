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
