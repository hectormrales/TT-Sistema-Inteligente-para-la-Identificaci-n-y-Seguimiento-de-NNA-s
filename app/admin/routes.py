# app/admin/routes.py
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.models import db, User
from app.admin import admin_bp
import re

def admin_required(f):
    """Decorador para asegurar que el usuario actual es administrador."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/create', methods=['POST'])
@login_required
@admin_required
def create_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == 'on'
    is_active = request.form.get('is_active') == 'on'

    if not username or not email or not password:
        flash('Todos los campos son obligatorios.', 'danger')
        return redirect(url_for('admin.users'))

    if User.query.filter_by(username=username).first():
        flash('El usuario ya existe.', 'danger')
        return redirect(url_for('admin.users'))

    if User.query.filter_by(email=email.lower()).first():
        flash('El correo ya está registrado.', 'danger')
        return redirect(url_for('admin.users'))

    user = User(
        username=username,
        email=email.lower(),
        is_admin=is_admin,
        is_active=is_active
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash('Usuario creado exitosamente.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/edit/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('admin.users'))

    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    
    # Prevenir que el admin se quite sus propios permisos por accidente
    if user.id == current_user.id:
        is_admin = True
        is_active = True
    else:
        is_admin = request.form.get('is_admin') == 'on'
        is_active = request.form.get('is_active') == 'on'

    if not username or not email:
        flash('Usuario y correo son obligatorios.', 'danger')
        return redirect(url_for('admin.users'))

    # Check si el nuevo username o email ya existen en otro usuario
    existing_username = User.query.filter_by(username=username).first()
    if existing_username and existing_username.id != user.id:
        flash('El nombre de usuario ya está en uso.', 'danger')
        return redirect(url_for('admin.users'))

    existing_email = User.query.filter_by(email=email.lower()).first()
    if existing_email and existing_email.id != user.id:
        flash('El correo ya está en uso.', 'danger')
        return redirect(url_for('admin.users'))

    user.username = username
    user.email = email.lower()
    user.is_admin = is_admin
    user.is_active = is_active

    if password:
        user.set_password(password)

    db.session.commit()
    flash('Usuario actualizado exitosamente.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('No puedes eliminar tu propia cuenta.', 'danger')
        return redirect(url_for('admin.users'))

    user = db.session.get(User, user_id)
    if not user:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('admin.users'))

    db.session.delete(user)
    db.session.commit()
    flash('Usuario eliminado permanentemente.', 'success')
    return redirect(url_for('admin.users'))
