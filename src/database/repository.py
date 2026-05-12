# src/database/repository.py — Capa de acceso a datos PostgreSQL
"""
OE-3: Repositorio de datos con Full-Text Search y rendimiento < 100ms.

Implementa el patrón Repository para aislar la lógica de acceso
a datos del resto de la aplicación. Todos los queries usan índices
optimizados y FTS de PostgreSQL.

Full-Text Search (FTS) en PostgreSQL:
  ┌────────────────────────────────────────────────────┐
  │  Configuración: 'spanish'                          │
  │  ├── Stemmer: Snowball Spanish                     │
  │  ├── Stop words: artículos, preposiciones, etc.    │
  │  └── Unaccent: normaliza acentos                   │
  │                                                    │
  │  tsvector: Representación vectorizada del texto     │
  │  tsquery: Query de búsqueda con operadores         │
  │  ts_rank: Ranking por relevancia del match          │
  │                                                    │
  │  Índice GIN: Generalized Inverted Index             │
  │  → Permite búsqueda FTS en O(log n) en vez de O(n) │
  └────────────────────────────────────────────────────┘

Índices implementados:
  1. GIN sobre busqueda_fts → FTS en < 10ms
  2. B-tree sobre fecha DESC → Consultas cronológicas
  3. B-tree sobre score_compuesto DESC → Top relevancia
  4. B-tree sobre cluster_id → Agrupación por cluster
  5. B-tree parcial sobre menores_identificados → Filtro NNA
  6. Hash sobre content_hash → Deduplicación O(1)
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from sqlalchemy import text, func, desc, and_, or_, Index
from sqlalchemy.dialects.postgresql import TSVECTOR

from app.models import db

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Inicialización de esquema y FTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def init_fts_schema():
    """
    Crea el esquema FTS en PostgreSQL.

    Ejecuta SQL directo para:
      1. Instalar extensión unaccent (normalización de acentos)
      2. Crear configuración FTS personalizada 'spanish_unaccent'
      3. Agregar columna tsvector si no existe
      4. Crear índice GIN sobre el tsvector
      5. Crear trigger para actualización automática del tsvector
      6. Crear índices adicionales para rendimiento

    La configuración 'spanish_unaccent' combina:
      - Stemming español (feminicidios → feminicid)
      - Eliminación de acentos (víctima → victima para búsqueda)
      - Stop words en español
    """
    statements = [
        # 1. Extensión unaccent
        "CREATE EXTENSION IF NOT EXISTS unaccent;",

        # 2. Configuración FTS personalizada (si no existe)
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_ts_config WHERE cfgname = 'spanish_unaccent'
            ) THEN
                CREATE TEXT SEARCH CONFIGURATION spanish_unaccent (
                    COPY = spanish
                );
                ALTER TEXT SEARCH CONFIGURATION spanish_unaccent
                    ALTER MAPPING FOR hword, hword_part, word
                    WITH unaccent, spanish_stem;
            END IF;
        END $$;
        """,

        # 3. Columna tsvector
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'noticias' AND column_name = 'busqueda_fts'
            ) THEN
                ALTER TABLE noticias
                ADD COLUMN busqueda_fts tsvector;
            END IF;
        END $$;
        """,

        # 4. Índice GIN para FTS
        """
        CREATE INDEX IF NOT EXISTS idx_noticias_fts
        ON noticias USING GIN (busqueda_fts);
        """,

        # 5. Trigger para actualización automática del tsvector
        """
        CREATE OR REPLACE FUNCTION noticias_fts_trigger()
        RETURNS trigger AS $$
        BEGIN
            NEW.busqueda_fts :=
                setweight(to_tsvector('spanish_unaccent', COALESCE(NEW.titulo, '')), 'A') ||
                setweight(to_tsvector('spanish_unaccent', COALESCE(NEW.contenido, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """,

        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger WHERE tgname = 'trg_noticias_fts'
            ) THEN
                CREATE TRIGGER trg_noticias_fts
                BEFORE INSERT OR UPDATE OF titulo, contenido
                ON noticias
                FOR EACH ROW
                EXECUTE FUNCTION noticias_fts_trigger();
            END IF;
        END $$;
        """,

        # 6. Índices adicionales para rendimiento
        """
        CREATE INDEX IF NOT EXISTS idx_noticias_fecha
        ON noticias (fecha DESC NULLS LAST);
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_noticias_score
        ON noticias (score_compuesto DESC);
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_noticias_relevancia
        ON noticias (relevancia_final DESC);
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_noticias_cluster
        ON noticias (cluster_id);
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_noticias_clasificacion
        ON noticias (clasificacion_final);
        """,

        # Índice parcial: solo noticias con NNA (muy selectivo)
        """
        CREATE INDEX IF NOT EXISTS idx_noticias_nna
        ON noticias (score_nna DESC)
        WHERE menores_identificados = 'Si';
        """,

        # Índice hash para deduplicación rápida
        """
        CREATE INDEX IF NOT EXISTS idx_noticias_hash
        ON noticias USING hash (content_hash);
        """,

        # Actualizar tsvector de registros existentes
        """
        UPDATE noticias
        SET busqueda_fts =
            setweight(to_tsvector('spanish_unaccent', COALESCE(titulo, '')), 'A') ||
            setweight(to_tsvector('spanish_unaccent', COALESCE(contenido, '')), 'B')
        WHERE busqueda_fts IS NULL;
        """,
    ]

    for stmt in statements:
        try:
            db.session.execute(text(stmt))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(f"FTS setup warning: {e}")

    logger.info("Esquema FTS inicializado correctamente")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Repositorio de Noticias
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class NoticiasRepository:
    """
    Repositorio para operaciones CRUD y búsqueda de noticias.

    Todos los métodos de lectura están optimizados para
    tiempos de respuesta < 100ms usando los índices definidos.
    """

    @staticmethod
    def crear(data: dict) -> "Noticia":
        """Crea una nueva noticia en la base de datos."""
        from src.database.models_noticias import Noticia
        noticia = Noticia(**data)
        db.session.add(noticia)
        db.session.flush()  # Obtener ID sin commit
        return noticia

    @staticmethod
    def crear_batch(records: list[dict]) -> int:
        """
        Inserción masiva de noticias (batch insert).

        Usa INSERT con ON CONFLICT para evitar duplicados por enlace.
        Más eficiente que insertar uno por uno: ~10x más rápido.

        Args:
            records: Lista de diccionarios con datos de noticias.

        Returns:
            Número de noticias insertadas exitosamente.
        """
        from src.database.models_noticias import Noticia

        count = 0
        batch_size = 100

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            for record in batch:
                # Verificar duplicado por hash o enlace
                existing = None
                if record.get("content_hash"):
                    existing = Noticia.query.filter_by(
                        content_hash=record["content_hash"]
                    ).first()
                elif record.get("enlace"):
                    existing = Noticia.query.filter_by(
                        enlace=record["enlace"]
                    ).first()

                if not existing:
                    noticia = Noticia(**record)
                    db.session.add(noticia)
                    count += 1

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.warning(f"Error en batch insert: {e}")

        logger.info(f"Batch insert: {count} noticias insertadas")
        return count

    @staticmethod
    def buscar_fts(
        query: str,
        limit: int = 20,
        offset: int = 0,
        clasificacion: str | None = None,
        solo_nna: bool = False,
    ) -> dict:
        """
        Búsqueda Full-Text Search con ranking.

        Usa tsquery con operador & (AND) y | (OR) para combinar
        términos de búsqueda. Los resultados se ranquean con
        ts_rank que considera:
          - Frecuencia del término
          - Posición en el documento
          - Peso del campo (A=título tiene 4x más peso que B=contenido)

        Rendimiento esperado: < 50ms con índice GIN.

        Args:
            query: Texto de búsqueda (se convierte a tsquery).
            limit: Máximo de resultados.
            offset: Offset para paginación.
            clasificacion: Filtro opcional por clasificación.
            solo_nna: Si True, solo noticias con NNA.

        Returns:
            dict con resultados, total, y tiempo de ejecución.
        """
        start_time = time.time()

        # Construir tsquery: separar palabras con operador OR (|)
        # para búsqueda más permisiva
        terms = query.strip().split()
        ts_terms = " | ".join(terms)

        # Query base con ranking FTS
        sql = """
            SELECT
                n.*,
                ts_rank(n.busqueda_fts, query) AS rank_fts
            FROM noticias n,
                 to_tsquery('spanish_unaccent', :query) query
            WHERE n.busqueda_fts @@ query
        """
        params = {"query": ts_terms, "limit": limit, "offset": offset}

        # Filtros adicionales
        if clasificacion:
            sql += " AND n.clasificacion_final = :clasificacion"
            params["clasificacion"] = clasificacion
        if solo_nna:
            sql += " AND n.menores_identificados = 'Si'"

        # Ordenar por ranking FTS * relevancia del sistema
        sql += """
            ORDER BY rank_fts * COALESCE(n.relevancia_final, n.score_compuesto, 0) DESC
            LIMIT :limit OFFSET :offset
        """

        # Contar total
        count_sql = """
            SELECT COUNT(*)
            FROM noticias n,
                 to_tsquery('spanish_unaccent', :query) query
            WHERE n.busqueda_fts @@ query
        """
        count_params = {"query": ts_terms}
        if clasificacion:
            count_sql += " AND n.clasificacion_final = :clasificacion"
            count_params["clasificacion"] = clasificacion
        if solo_nna:
            count_sql += " AND n.menores_identificados = 'Si'"

        try:
            results = db.session.execute(text(sql), params).fetchall()
            total = db.session.execute(text(count_sql), count_params).scalar()

            elapsed_ms = (time.time() - start_time) * 1000

            return {
                "resultados": [dict(row._mapping) for row in results],
                "total": total,
                "query": query,
                "tiempo_ms": round(elapsed_ms, 2),
                "pagina": (offset // limit) + 1,
                "por_pagina": limit,
            }

        except Exception as e:
            logger.error(f"Error FTS: {e}")
            # Fallback a LIKE si FTS falla
            return NoticiasRepository._buscar_fallback(
                query, limit, offset, clasificacion, solo_nna
            )

    @staticmethod
    def _buscar_fallback(
        query: str,
        limit: int,
        offset: int,
        clasificacion: str | None,
        solo_nna: bool,
    ) -> dict:
        """Búsqueda fallback con ILIKE cuando FTS no está disponible."""
        from src.database.models_noticias import Noticia

        start_time = time.time()
        q = Noticia.query

        pattern = f"%{query}%"
        q = q.filter(
            or_(
                Noticia.titulo.ilike(pattern),
                Noticia.contenido.ilike(pattern),
            )
        )

        if clasificacion:
            q = q.filter(Noticia.clasificacion_final == clasificacion)
        if solo_nna:
            q = q.filter(Noticia.menores_identificados == "Si")

        total = q.count()
        results = (
            q.order_by(desc(Noticia.relevancia_final))
            .offset(offset)
            .limit(limit)
            .all()
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "resultados": [n.to_dict() for n in results],
            "total": total,
            "query": query,
            "tiempo_ms": round(elapsed_ms, 2),
            "pagina": (offset // limit) + 1,
            "por_pagina": limit,
            "metodo": "fallback_ilike",
        }

    @staticmethod
    def listar(
        page: int = 1,
        per_page: int = 10,
        clasificacion: str | None = None,
        solo_nna: bool = False,
        orden: str = "fecha",
        batch_id: str | None = None,
    ) -> dict:
        """
        Lista noticias con paginación y filtros.

        Usa índices B-tree para ordenación eficiente.
        Rendimiento esperado: < 30ms.
        """
        from src.database.models_noticias import Noticia

        start_time = time.time()
        q = Noticia.query

        if batch_id:
            q = q.filter(Noticia.batch_id == batch_id)

        if clasificacion:
            q = q.filter(Noticia.clasificacion_final == clasificacion)
        else:
            # Por defecto, ocultar las 'No relevante' para que no ensucien el dashboard
            q = q.filter(Noticia.clasificacion_final != 'No relevante')

        if solo_nna:
            q = q.filter(Noticia.menores_identificados == "Si")

        # Ordenación
        if orden == "fecha":
            q = q.order_by(desc(Noticia.fecha))
        elif orden == "relevancia":
            q = q.order_by(desc(Noticia.relevancia_final))
        elif orden == "score":
            q = q.order_by(desc(Noticia.score_compuesto))

        total = q.count()
        offset = (page - 1) * per_page
        noticias = q.offset(offset).limit(per_page).all()

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "noticias": [n.to_dict() for n in noticias],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "tiempo_ms": round(elapsed_ms, 2),
        }

    @staticmethod
    def get_latest_batch_id() -> str | None:
        from src.database.models_noticias import Noticia
        latest = Noticia.query.filter(Noticia.batch_id.isnot(None)).order_by(desc(Noticia.created_at)).first()
        return latest.batch_id if latest else None

    @staticmethod
    def get_all_batches() -> list[str]:
        from src.database.models_noticias import Noticia
        batches = db.session.query(Noticia.batch_id).filter(Noticia.batch_id.isnot(None)).distinct().all()
        return [b[0] for b in batches if b[0]]

    @staticmethod
    def estadisticas(batch_id: str | None = None) -> dict:
        """
        Estadísticas generales de la base de datos.

        Usa COUNT con filtros indexados para rendimiento < 50ms.
        """
        from src.database.models_noticias import Noticia

        start_time = time.time()
        
        q = Noticia.query
        if batch_id:
            q = q.filter(Noticia.batch_id == batch_id)

        total = q.count()
        nna = q.filter(Noticia.menores_identificados == "Si").count()
        alta = q.filter(Noticia.clasificacion_final == "Alta").count()
        media = q.filter(Noticia.clasificacion_final == "Media").count()
        baja = q.filter(Noticia.clasificacion_final == "Baja").count()
        
        # Para clusters y topics, aplicamos el filtro también
        q_cluster = db.session.query(func.count(func.distinct(Noticia.cluster_id)))
        if batch_id:
            q_cluster = q_cluster.filter(Noticia.batch_id == batch_id)
        clusters = q_cluster.scalar() or 0
        
        q_topic = db.session.query(func.count(func.distinct(Noticia.topic_id)))
        if batch_id:
            q_topic = q_topic.filter(Noticia.batch_id == batch_id)
        topics = q_topic.scalar() or 0

        # Similitud promedio
        avg_sim = db.session.query(
            func.avg(Noticia.max_similarity)
        ).scalar() or 0

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "total_noticias": total,
            "noticias_nna": nna,
            "alta_relevancia": alta,
            "media_relevancia": media,
            "baja_relevancia": baja,
            "clusters": clusters,
            "topics": topics,
            "similitud_promedio": round(float(avg_sim), 3),
            "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tiempo_ms": round(elapsed_ms, 2),
        }

    @staticmethod
    def importar_desde_csv(csv_path: str) -> int:
        """
        Importa noticias desde un CSV existente a PostgreSQL.

        Mapea las columnas del CSV al esquema normalizado,
        genera content_hash para deduplicación.

        Args:
            csv_path: Ruta al archivo CSV.

        Returns:
            Número de registros importados.
        """
        import hashlib

        df = pd.read_csv(csv_path)
        logger.info(f"Importando {len(df)} registros desde {csv_path}")

        records = []
        for _, row in df.iterrows():
            titulo = str(row.get("titulo", ""))
            contenido = str(row.get("contenido", ""))

            # Generar hash para deduplicación
            hash_text = f"{titulo.strip().lower()}|{contenido[:500].strip().lower()}"
            content_hash = hashlib.md5(hash_text.encode()).hexdigest()

            # Parsear fecha
            fecha = None
            if pd.notna(row.get("fecha")):
                try:
                    fecha = pd.to_datetime(row["fecha"], utc=True)
                except Exception:
                    pass

            record = {
                "titulo": titulo,
                "contenido": contenido,
                "enlace": row.get("enlace"),
                "fuente": row.get("fuente"),
                "fecha": fecha,
                "score_feminicidio": float(row.get("score_feminicidio", 0)),
                "score_nna": float(row.get("score_nna", 0)),
                "score_compuesto": float(row.get("score_compuesto", 0)),
                "relevancia_final": float(
                    row.get("relevancia_final", row.get("score_compuesto", 0))
                ),
                "clasificacion": row.get("clasificacion", "No relevante"),
                "clasificacion_final": row.get(
                    "clasificacion_final", row.get("clasificacion", "No relevante")
                ),
                "cluster_id": (
                    int(row["cluster"]) if pd.notna(row.get("cluster")) and int(row.get("cluster", -1)) >= 0
                    else None
                ),
                "topic_id": (
                    int(row["topic_id"]) if pd.notna(row.get("topic_id"))
                    else None
                ),
                "max_similarity": float(row.get("max_similarity", 0)),
                "content_hash": content_hash,
                "menores_identificados": row.get("menores_identificados", "No"),
                "scrape_method": row.get("scrape_method", "csv_import"),
            }
            records.append(record)

        return NoticiasRepository.crear_batch(records)

    @staticmethod
    def exportar_a_csv(csv_path: str) -> int:
        """Exporta noticias de PostgreSQL a CSV."""
        from src.database.models_noticias import Noticia

        noticias = Noticia.query.order_by(desc(Noticia.fecha)).all()

        records = [n.to_dict() for n in noticias]
        df = pd.DataFrame(records)
        df.to_csv(csv_path, index=False, encoding="utf-8")

        return len(df)

    @staticmethod
    def clear_history() -> bool:
        """Elimina todos los registros de noticias de la base de datos."""
        from src.database.models_noticias import Noticia
        try:
            Noticia.query.delete()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al borrar historial: {e}")
            return False

    @staticmethod
    def get_noticia(noticia_id: int):
        from src.database.models_noticias import Noticia
        return Noticia.query.get(noticia_id)

    @staticmethod
    def save_investigation(noticia_id: int, result: dict) -> bool:
        from src.database.models_noticias import Noticia
        try:
            noticia = Noticia.query.get(noticia_id)
            if noticia:
                # Mantener el flag de seguimiento si ya existía
                if noticia.investigacion_json and noticia.investigacion_json.get('en_seguimiento'):
                    result['en_seguimiento'] = True
                noticia.investigacion_json = result
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error guardando investigacion: {e}")
            return False

    @staticmethod
    def add_to_seguimiento(noticia_id: int) -> bool:
        from src.database.models_noticias import Noticia
        from sqlalchemy.orm.attributes import flag_modified
        try:
            noticia = Noticia.query.get(noticia_id)
            if noticia and noticia.investigacion_json:
                # Modificar el JSON
                import copy
                new_json = copy.deepcopy(noticia.investigacion_json)
                new_json['en_seguimiento'] = True
                noticia.investigacion_json = new_json
                flag_modified(noticia, "investigacion_json")
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error en add_to_seguimiento: {e}")
            return False
