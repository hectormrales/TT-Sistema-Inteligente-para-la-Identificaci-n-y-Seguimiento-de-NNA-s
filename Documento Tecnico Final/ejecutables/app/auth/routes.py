# app/auth/routes.py — Rutas de autenticación
"""Login, registro y logout."""

from urllib.parse import urlparse, urljoin

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user

from app.models import db, User
from app.auth.forms import LoginForm

auth_bp = Blueprint('auth', __name__)


# ── Rutas ───────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Inicio de sesión."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Tu cuenta esta deshabilitada. Contacta al administrador.', 'danger')
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember_me.data)
            user.update_last_login()

            current_app.logger.info(
                f"Login exitoso: {user.username} desde {request.remote_addr}"
            )

            next_page = request.args.get('next')
            if next_page and _is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('main.index'))

        flash('Usuario o contraseña incorrectos.', 'danger')
        current_app.logger.warning(
            f"Login fallido para '{form.username.data}' desde {request.remote_addr}"
        )

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Cierre de sesión."""
    current_app.logger.info(f"Logout: {current_user.username}")
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))


# ── Helpers ─────────────────────────────────────────────────

def _is_safe_url(target: str) -> bool:
    """Evita redirecciones abiertas (Open Redirect)."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return (
        test_url.scheme in ('http', 'https')
        and ref_url.netloc == test_url.netloc
    )
