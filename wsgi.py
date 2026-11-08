# wsgi.py — Punto de entrada de la aplicación web Flask
"""
Ejecutar directamente:  python wsgi.py
Producción (Docker):    gunicorn wsgi:app -b 0.0.0.0:5000
"""

import logging
import os
import sys

# Garantizar salida UTF-8 en consolas de Windows (evita UnicodeEncodeError en cp1252)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from app import create_app

# Configurar logging con UTF-8 explícito
log_dir = os.environ.get('LOGS_DIR', 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'webapp.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
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
