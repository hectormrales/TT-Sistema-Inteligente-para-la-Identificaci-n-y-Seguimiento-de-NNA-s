# app/__init__.py
from flask import Flask

def create_app():
    app = Flask(__name__)
    # Aquí puedes añadir configuraciones, como una SECRET_KEY
    app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'

    # Registrar las rutas (views)
    from . import routes
    app.register_blueprint(routes.bp)

    return app