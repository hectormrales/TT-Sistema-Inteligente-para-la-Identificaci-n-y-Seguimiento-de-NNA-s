# auth.py — Blueprint de Autenticación del Sistema NNA
"""
Rutas de autenticación: login, logout, registro.
Protección CSRF integrada vía Flask-WTF.
"""

import re
from datetime import datetime, timezone

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app
)
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, ValidationError
)

from models import db, User

# ============================================================
# Blueprint
# ============================================================
auth_bp = Blueprint('auth', __name__, template_folder='app/templates')


# ============================================================
# Formularios (WTForms + CSRF automático)
# ============================================================

class LoginForm(FlaskForm):
    """Formulario de inicio de sesión."""
    username = StringField('Usuario', validators=[
        DataRequired(message='El usuario es obligatorio.')
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message='La contraseña es obligatoria.')
    ])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Iniciar Sesión')


class RegistrationForm(FlaskForm):
    """Formulario de registro de usuarios."""
    username = StringField('Usuario', validators=[
        DataRequired(message='El usuario es obligatorio.'),
        Length(min=3, max=80, message='El usuario debe tener entre 3 y 80 caracteres.')
    ])
    email = StringField('Correo Electrónico', validators=[
        DataRequired(message='El correo es obligatorio.'),
        Email(message='Ingresa un correo electrónico válido.')
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message='La contraseña es obligatoria.'),
        Length(min=12, message='La contraseña debe tener mínimo 12 caracteres.')
    ])
    password_confirm = PasswordField('Confirmar Contraseña', validators=[
        DataRequired(message='Confirma tu contraseña.'),
        EqualTo('password', message='Las contraseñas no coinciden.')
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


# ============================================================
# Rutas
# ============================================================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Inicio de sesión."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Tu cuenta está deshabilitada. Contacta al administrador.', 'danger')
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember_me.data)
            user.update_last_login()

            current_app.logger.info(
                f"Login exitoso: {user.username} desde {request.remote_addr}"
            )

            # Redirigir a la página que el usuario intentaba visitar
            next_page = request.args.get('next')
            if next_page and _is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('index'))

        # Mensaje genérico para no revelar si el usuario existe
        flash('Usuario o contraseña incorrectos.', 'danger')
        current_app.logger.warning(
            f"Login fallido para '{form.username.data}' desde {request.remote_addr}"
        )

    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registro de nuevos usuarios."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data.lower(),
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        current_app.logger.info(
            f"Nuevo usuario registrado: {user.username}"
        )
        flash('Registro exitoso. Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Cierre de sesión."""
    current_app.logger.info(f"Logout: {current_user.username}")
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))


# ============================================================
# Helpers
# ============================================================

def _is_safe_url(target: str) -> bool:
    """Evita redirecciones abiertas (Open Redirect)."""
    from urllib.parse import urlparse, urljoin
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return (
        test_url.scheme in ('http', 'https')
        and ref_url.netloc == test_url.netloc
    )
