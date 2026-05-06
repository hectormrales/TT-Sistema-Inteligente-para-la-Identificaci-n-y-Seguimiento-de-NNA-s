from app import create_app
from app.models import db
from src.database.models_noticias import Noticia

app = create_app()

with app.app_context():
    # 1. Count ALL Alta
    alta_count = Noticia.query.filter(Noticia.clasificacion_final == 'Alta').count()
    print(f"Total Alta: {alta_count}")
    
    # 2. Count ALL NNA = 'Si'
    nna_count = Noticia.query.filter(Noticia.menores_identificados == 'Si').count()
    print(f"Total NNA='Si': {nna_count}")
    
    # 3. Count BOTH
    both_count = Noticia.query.filter(Noticia.clasificacion_final == 'Alta', Noticia.menores_identificados == 'Si').count()
    print(f"Total BOTH: {both_count}")
    
    # 4. What about lowercase 'alta'?
    both_lower_count = Noticia.query.filter(Noticia.clasificacion_final == 'alta', Noticia.menores_identificados == 'Si').count()
    print(f"Total BOTH (lowercase alta): {both_lower_count}")
    
    # 5. Look at the exact value of clasificacion_final for a row with NNA='Si'
    sample = Noticia.query.filter(Noticia.menores_identificados == 'Si').first()
    if sample:
        print(f"Sample NNA='Si' clasificacion_final: '{sample.clasificacion_final}'")
    else:
        print("No sample found")
