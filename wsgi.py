# wsgi.py — Punto de entrada de la aplicación web Flask
"""
Ejecutar directamente:  python wsgi.py
Producción (Docker):    gunicorn wsgi:app -b 0.0.0.0:5000
"""

import logging
import os

from app import create_app

# Configurar logging
log_dir = os.environ.get('LOGS_DIR', 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'webapp.log')),
        logging.StreamHandler(),
    ],
)

# Crear la aplicación primero, luego cargar datos CSV dentro del app context
app = create_app()
with app.app_context():
    from app.main.routes import _load_data
    _load_data()

if __name__ == '__main__':
    app.logger.info("Iniciando aplicación web NNA Sistema")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
