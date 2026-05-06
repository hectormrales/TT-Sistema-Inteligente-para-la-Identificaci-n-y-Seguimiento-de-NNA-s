import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.environ.get("POSTGRES_USER", "postgres")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
DB_NAME = os.environ.get("POSTGRES_DB", "nna_db")
DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = os.environ.get("POSTGRES_PORT", "5432")

# Si el host es nna-postgres, es probable que estemos corriendo fuera de docker
# así que usamos localhost para la migración local
if DB_HOST == "nna-postgres":
    DB_HOST = "localhost"

DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def apply_migrations():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cursor = conn.cursor()

    columns_to_add = [
        ("score_victima_indirecta", "DOUBLE PRECISION DEFAULT 0.0"),
        ("nna_victima_indirecta", "VARCHAR(5) DEFAULT 'No'"),
        ("score_caso", "DOUBLE PRECISION DEFAULT 0.0"),
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE noticias ADD COLUMN {col_name} {col_type};")
            print(f"Columna '{col_name}' añadida con éxito.")
        except psycopg2.errors.DuplicateColumn:
            print(f"La columna '{col_name}' ya existe.")
        except Exception as e:
            print(f"Error al añadir la columna '{col_name}': {e}")
            
    cursor.close()
    conn.close()

if __name__ == "__main__":
    apply_migrations()
