from app import create_app
from src.database.repository import NoticiasRepository
import json
import re

app = create_app()
with app.app_context():
    r = NoticiasRepository.listar(page=1)
    text = json.dumps(r)
    matches = re.findall(r'"[a-zA-Z0-9_]+":\s*NaN', text)
    print("Found NaN keys:", matches)
