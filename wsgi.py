# wsgi.py — Punto de entrada de la aplicación web Flask
"""
Ejecutar directamente:  python wsgi.py
Producción (Docker):    gunicorn wsgi:app -b 0.0.0.0:5000
"""

import logging
import os

from app import create_app
from app.main.routes import _load_data

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.environ.get('LOGS_DIR', 'logs'), 'webapp.log')),
        logging.StreamHandler(),
    ],
)

# Cargar datos existentes al inicio
_load_data()

# Crear la aplicación
app = create_app()

if __name__ == '__main__':
    app.logger.info("Iniciando aplicación web NNA Sistema")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
