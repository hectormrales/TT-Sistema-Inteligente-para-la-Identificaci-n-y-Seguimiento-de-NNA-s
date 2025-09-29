# app/__init__.py
from flask import Flask
import os

def create_app():
    # Asegura que Flask busque templates en app/templates
    app = Flask(__name__, template_folder='templates')

    # Config básica (lee SECRET_KEY de variables de entorno si existe)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
    app.config['JSON_AS_ASCII'] = False        # evita \uXXXX para acentos/ñ en respuestas JSON
    app.config['PROPAGATE_EXCEPTIONS'] = True  # deja que veas tracebacks en desarrollo

    # Registrar las rutas (views)
    from . import routes
    app.register_blueprint(routes.bp)

    # Healthcheck simple
    @app.get('/health')
    def health():
        return {'status': 'ok'}, 200

    return app
