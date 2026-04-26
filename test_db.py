from app import create_app
from app.models import db
from src.database.models_noticias import Noticia

app = create_app()
with app.app_context():
    # Find the specific news item
    n = Noticia.query.filter(Noticia.titulo.ilike('%Sus hijos%')).first()
    if n:
        print("FOUND NEWS ITEM:")
        print(f"ID: {n.id}")
        print(f"Titulo: {n.titulo}")
        print(f"Clasificacion: '{n.clasificacion}'")
        print(f"Clasificacion Final: '{n.clasificacion_final}'")
        print(f"Menores Identificados: '{n.menores_identificados}'")
    else:
        print("NEWS ITEM NOT FOUND")
