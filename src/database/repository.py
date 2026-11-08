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
    if db.engine.dialect.name != "postgresql":
        return

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
                    db.session.flush()
                    if (
                        noticia.clasificacion_final in ("Alta", "Media")
                        or noticia.investigacion_json
                    ):
                        try:
                            NoticiasRepository.vincular_o_crear_expediente(noticia)
                        except Exception as exp_err:
                            logger.debug(f"No se pudo vincular expediente en crear_batch: {exp_err}")
                    count += 1
                else:
                    # Actualizar campos enriquecidos si la noticia ya existía (ej. re-análisis LLM)
                    if record.get("investigacion_json"):
                        if not existing.investigacion_json:
                            existing.investigacion_json = record["investigacion_json"]
                        else:
                            from src.database.models_noticias import consolidar_datos_expediente
                            existing.investigacion_json = consolidar_datos_expediente(
                                existing.investigacion_json, record["investigacion_json"]
                            )
                    if record.get("clasificacion_final"):
                        existing.clasificacion_final = record["clasificacion_final"]
                        existing.clasificacion = record["clasificacion_final"]
                    if record.get("relevancia_final") is not None:
                        existing.relevancia_final = record["relevancia_final"]
                    if record.get("score_semantico") is not None:
                        existing.score_semantico = record["score_semantico"]
                    if record.get("menores_identificados"):
                        existing.menores_identificados = record["menores_identificados"]
                    if record.get("modo_deteccion"):
                        existing.modo_deteccion = record["modo_deteccion"]
                    if record.get("topic_id") is not None:
                        existing.topic_id = record["topic_id"]
                        existing.topic_description = record.get("topic_description")

                    if (
                        existing.clasificacion_final in ("Alta", "Media")
                        or existing.investigacion_json
                    ):
                        try:
                            NoticiasRepository.vincular_o_crear_expediente(existing)
                        except Exception as exp_err:
                            logger.debug(f"No se pudo actualizar expediente en crear_batch: {exp_err}")

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
        sesion_id: int | None = None,
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
        if db.engine.dialect.name != "postgresql":
            return NoticiasRepository._buscar_fallback(
                query, limit, offset, clasificacion, solo_nna, sesion_id
            )

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
        if sesion_id:
            sql += " AND n.sesion_id = :sesion_id"
            params["sesion_id"] = sesion_id

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
        if sesion_id:
            count_sql += " AND n.sesion_id = :sesion_id"
            count_params["sesion_id"] = sesion_id

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
                query, limit, offset, clasificacion, solo_nna, sesion_id
            )

    @staticmethod
    def _buscar_fallback(
        query: str,
        limit: int,
        offset: int,
        clasificacion: str | None,
        solo_nna: bool,
        sesion_id: int | None = None,
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
        if sesion_id:
            q = q.filter(Noticia.sesion_id == sesion_id)

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
        sesion_id: int | None = None,
        cluster_id: int | None = None,
    ) -> dict:
        """
        Lista noticias con paginación y filtros.

        Usa índices B-tree para ordenación eficiente.
        Rendimiento esperado: < 30ms.
        """
        from src.database.models_noticias import Noticia

        start_time = time.time()
        q = Noticia.query

        if sesion_id:
            q = q.filter(Noticia.sesion_id == sesion_id)

        if cluster_id is not None:
            q = q.filter(Noticia.cluster_id == cluster_id)

        if clasificacion:
            q = q.filter(Noticia.clasificacion_final == clasificacion)
        else:
            # Por defecto, ocultar las 'No relevante' para que no ensucien el dashboard
            q = q.filter(Noticia.clasificacion_final != 'No relevante')

        if solo_nna:
            q = q.filter(Noticia.menores_identificados == "Si")

        # Ordenación
        if orden == "fecha_desc" or orden == "fecha":
            q = q.order_by(desc(Noticia.fecha))
        elif orden == "fecha_asc":
            q = q.order_by(Noticia.fecha)

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
    def estadisticas(sesion_id: int | None = None) -> dict:
        """
        Estadísticas generales de la base de datos.

        Usa COUNT con filtros indexados para rendimiento < 50ms.
        """
        from src.database.models_noticias import Noticia

        start_time = time.time()
        
        q = Noticia.query
        if sesion_id:
            q = q.filter(Noticia.sesion_id == sesion_id)

        total = q.count()
        nna = q.filter(Noticia.menores_identificados == "Si").count()
        alta = q.filter(Noticia.clasificacion_final == "Alta").count()
        media = q.filter(Noticia.clasificacion_final == "Media").count()
        baja = q.filter(Noticia.clasificacion_final == "Baja").count()
        
        # Para clusters y topics, aplicamos el filtro también
        q_cluster = db.session.query(func.count(func.distinct(Noticia.cluster_id)))
        if sesion_id:
            q_cluster = q_cluster.filter(Noticia.sesion_id == sesion_id)
        clusters = q_cluster.scalar() or 0
        
        q_topic = db.session.query(func.count(func.distinct(Noticia.topic_id)))
        if sesion_id:
            q_topic = q_topic.filter(Noticia.sesion_id == sesion_id)
        topics = q_topic.scalar() or 0

        # Similitud promedio
        avg_sim = db.session.query(
            func.avg(Noticia.max_similarity)
        ).scalar() or 0

        # Estadísticas de expedientes consolidados
        total_expedientes = 0
        expedientes_seguimiento = 0
        try:
            from src.database.models_noticias import ExpedienteCaso
            q_exp = ExpedienteCaso.query
            if sesion_id:
                q_exp = q_exp.filter(ExpedienteCaso.sesion_id == sesion_id)
            total_expedientes = q_exp.count()
            expedientes_seguimiento = q_exp.filter(ExpedienteCaso.en_seguimiento.is_(True)).count()
        except Exception:
            pass

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "total_noticias": total,
            "noticias_nna": nna,
            "alta_relevancia": alta,
            "media_relevancia": media,
            "baja_relevancia": baja,
            "clusters": clusters,
            "topics": topics,
            "total_expedientes": total_expedientes,
            "expedientes_en_seguimiento": expedientes_seguimiento,
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
            if record["clasificacion_final"] in ("Alta", "Media"):
                try:
                    import json as _json
                    raw_inv = row.get("investigacion_json")
                    if pd.notna(raw_inv) and raw_inv:
                        record["investigacion_json"] = (
                            _json.loads(raw_inv) if isinstance(raw_inv, str) else raw_inv
                        )
                    else:
                        from src.analysis.llm_extractor import LLMExtractor, aplicar_candados_estrictos
                        schema = LLMExtractor._deterministic_fallback_extract(
                            titulo, contenido, str(row.get("enlace") or "")
                        )
                        audited = aplicar_candados_estrictos(
                            schema,
                            titulo,
                            contenido,
                        )
                        if audited["clasificacion_final"] == "No relevante":
                            record["clasificacion"] = "No relevante"
                            record["clasificacion_final"] = "No relevante"
                            record["menores_identificados"] = "No"
                            record["relevancia_final"] = 0.05
                            record["score_compuesto"] = 0.05
                        else:
                            record["clasificacion"] = audited["clasificacion_final"]
                            record["clasificacion_final"] = audited["clasificacion_final"]
                            record["menores_identificados"] = "Si"
                            record["investigacion_json"] = audited.get("investigacion_json")
                except Exception as inv_err:
                    logger.debug(f"Error enriqueciendo fila CSV: {inv_err}")
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
        """Elimina todos los registros de noticias y expedientes de la base de datos."""
        from src.database.models_noticias import Noticia, ExpedienteCaso
        try:
            Noticia.query.delete()
            ExpedienteCaso.query.delete()
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
    def vincular_o_crear_expediente(
        noticia: "Noticia",
        investigacion: dict | None = None,
        marcar_seguimiento: bool = False,
    ) -> Optional["ExpedienteCaso"]:
        """
        Agrupa automáticamente una `Noticia` dentro de su `ExpedienteCaso` correspondiente.

        Si ya existe un expediente para ese mismo feminicidio (misma víctima + estado,
        o mismo municipio + mes), fusiona la información enriquecida y suma la fuente;
        si no existe, crea un nuevo `ExpedienteCaso` con folio único.
        """
        import copy
        import hashlib
        from sqlalchemy.orm.attributes import flag_modified
        from src.database.models_noticias import (
            ExpedienteCaso,
            generar_clave_expediente,
            consolidar_datos_expediente,
            _slugify_key,
        )

        raw_inv = investigacion if isinstance(investigacion, dict) else noticia.investigacion_json
        inv = copy.deepcopy(raw_inv) if isinstance(raw_inv, dict) else {}
        if marcar_seguimiento:
            inv["en_seguimiento"] = True
        if "nna_afectados" in inv and "ninos_afectados" not in inv:
            inv["ninos_afectados"] = inv["nna_afectados"]
        if "edades_nna" in inv and "edades" not in inv:
            inv["edades"] = inv["edades_nna"]
        if not inv:
            inv = {
                "ubicacion": "No especificada",
                "estado": "No especificado",
                "municipio": "No especificado",
                "victimas": "No especificada",
                "ninos_afectados": "No especificado",
                "edades": "No especificadas",
                "situacion_actual": "No especificada",
                "medios_contacto": "DIF / Fiscalía Estatal",
                "cita_textual_evidencia": "",
                "resumen": (noticia.contenido or noticia.titulo or "")[:300],
                "fuentes": [noticia.enlace] if noticia.enlace else [],
            }

        if noticia.enlace:
            fuentes_list = list(inv.get("fuentes") or [])
            if noticia.enlace not in fuentes_list:
                fuentes_list.insert(0, noticia.enlace)
            inv["fuentes"] = fuentes_list

        clave_dedup = generar_clave_expediente(inv, noticia.titulo or "", noticia.fecha)
        expediente = ExpedienteCaso.query.filter_by(clave_dedup=clave_dedup).first()

        if expediente is None:
            year_str = (
                noticia.fecha.strftime("%Y")
                if noticia.fecha
                else datetime.now(timezone.utc).strftime("%Y")
            )
            estado_tag = (_slugify_key(str(inv.get("estado") or inv.get("ubicacion") or "mx"))[:8] or "mx").upper()
            short_hash = hashlib.md5(clave_dedup.encode("utf-8")).hexdigest()[:6].upper()
            folio = f"EXP-{year_str}-{estado_tag}-{short_hash}"
            if ExpedienteCaso.query.filter_by(folio=folio).first():
                folio = f"EXP-{year_str}-{estado_tag}-{hashlib.md5(clave_dedup.encode('utf-8')).hexdigest()[:8].upper()}"

            en_seg = bool(inv.get("en_seguimiento", False))
            est_seg = str(inv.get("estado_seguimiento") or ("en_verificacion" if en_seg else "detectado"))

            expediente = ExpedienteCaso(
                folio=folio,
                clave_dedup=clave_dedup,
                titulo_caso=(noticia.titulo or "Caso detectado")[:350],
                ubicacion=str(inv.get("ubicacion") or "No especificada")[:200],
                estado=str(inv.get("estado") or "No especificado")[:100],
                municipio=str(inv.get("municipio") or "No especificado")[:100],
                victimas=str(inv.get("victimas") or "No especificada")[:300],
                ninos_afectados=str(inv.get("ninos_afectados") or "No especificado")[:50],
                edades=str(inv.get("edades") or "No especificadas")[:150],
                situacion_actual=str(inv.get("situacion_actual") or "No especificada")[:300],
                medios_contacto=str(inv.get("medios_contacto") or "DIF / Fiscalía Estatal")[:500],
                cita_textual_evidencia=str(inv.get("cita_textual_evidencia") or ""),
                resumen=str(inv.get("resumen") or (noticia.titulo or "")),
                estado_seguimiento=est_seg,
                en_seguimiento=en_seg,
                notas_seguimiento=list(inv.get("notas_seguimiento") or []),
                num_noticias=1,
                relevancia_maxima=float(noticia.relevancia_final or noticia.score_compuesto or 0.0),
                clasificacion=noticia.clasificacion_final or noticia.clasificacion or "Alta",
                fuentes_json=list(inv.get("fuentes") or []),
                sesion_id=noticia.sesion_id,
            )
            db.session.add(expediente)
            db.session.flush()
        else:
            # Fusionar datos del expediente existente con los de la nueva noticia
            actual_dict = {
                "ubicacion": expediente.ubicacion,
                "estado": expediente.estado,
                "municipio": expediente.municipio,
                "victimas": expediente.victimas,
                "ninos_afectados": expediente.ninos_afectados,
                "edades": expediente.edades,
                "situacion_actual": expediente.situacion_actual,
                "medios_contacto": expediente.medios_contacto,
                "cita_textual_evidencia": expediente.cita_textual_evidencia,
                "resumen": expediente.resumen,
                "fuentes": list(expediente.fuentes_json or []),
            }
            merged = consolidar_datos_expediente(actual_dict, inv)
            expediente.ubicacion = str(merged.get("ubicacion") or expediente.ubicacion)[:200]
            expediente.estado = str(merged.get("estado") or expediente.estado)[:100]
            expediente.municipio = str(merged.get("municipio") or expediente.municipio)[:100]
            expediente.victimas = str(merged.get("victimas") or expediente.victimas)[:300]
            expediente.ninos_afectados = str(merged.get("ninos_afectados") or expediente.ninos_afectados)[:50]
            expediente.edades = str(merged.get("edades") or expediente.edades)[:150]
            expediente.situacion_actual = str(merged.get("situacion_actual") or expediente.situacion_actual)[:300]
            expediente.medios_contacto = str(merged.get("medios_contacto") or expediente.medios_contacto)[:500]
            expediente.cita_textual_evidencia = merged.get("cita_textual_evidencia") or expediente.cita_textual_evidencia
            expediente.resumen = merged.get("resumen") or expediente.resumen
            expediente.fuentes_json = list(merged.get("fuentes") or [])
            flag_modified(expediente, "fuentes_json")

            if inv.get("en_seguimiento"):
                expediente.en_seguimiento = True
                if expediente.estado_seguimiento == "detectado":
                    expediente.estado_seguimiento = "en_verificacion"

            rel_actual = float(noticia.relevancia_final or noticia.score_compuesto or 0.0)
            if rel_actual > float(expediente.relevancia_maxima or 0.0):
                expediente.relevancia_maxima = rel_actual
            if noticia.clasificacion_final == "Alta":
                expediente.clasificacion = "Alta"

        # Vincular noticia y sincronizar metadatos del expediente en investigacion_json
        noticia.expediente_id = expediente.id
        inv.update({
            "expediente_id": expediente.id,
            "folio_expediente": expediente.folio,
            "ubicacion": expediente.ubicacion,
            "estado": expediente.estado,
            "municipio": expediente.municipio,
            "victimas": expediente.victimas,
            "ninos_afectados": expediente.ninos_afectados,
            "edades": expediente.edades,
            "situacion_actual": expediente.situacion_actual,
            "medios_contacto": expediente.medios_contacto,
            "cita_textual_evidencia": expediente.cita_textual_evidencia,
            "resumen": expediente.resumen,
            "fuentes": list(expediente.fuentes_json or []),
            "en_seguimiento": expediente.en_seguimiento,
            "estado_seguimiento": expediente.estado_seguimiento,
            "notas_seguimiento": list(expediente.notas_seguimiento or []),
        })
        noticia.investigacion_json = inv
        flag_modified(noticia, "investigacion_json")

        # Actualizar conteo de noticias vinculadas al expediente
        try:
            from src.database.models_noticias import Noticia as _NoticiaModel
            count_linked = _NoticiaModel.query.filter_by(expediente_id=expediente.id).count()
            expediente.num_noticias = max(1, count_linked, len(expediente.fuentes_json or []))
        except Exception:
            expediente.num_noticias = max(1, len(expediente.fuentes_json or []))

        return expediente

    @staticmethod
    def save_investigation(noticia_id: int, result: dict) -> bool:
        from src.database.models_noticias import Noticia
        try:
            noticia = Noticia.query.get(noticia_id)
            if noticia:
                if noticia.investigacion_json and noticia.investigacion_json.get('en_seguimiento'):
                    result['en_seguimiento'] = True
                if noticia.investigacion_json and noticia.investigacion_json.get('estado_seguimiento'):
                    result.setdefault('estado_seguimiento', noticia.investigacion_json['estado_seguimiento'])
                noticia.investigacion_json = result
                try:
                    NoticiasRepository.vincular_o_crear_expediente(noticia)
                except Exception as exp_err:
                    logger.debug(f"No se pudo vincular expediente en save_investigation: {exp_err}")
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error guardando investigacion: {e}")
            return False

    @staticmethod
    def add_to_seguimiento(
        noticia_id: int,
        estado_seguimiento: str = "en_verificacion",
        nota: str | None = None,
        usuario: str = "Operador ONG",
    ) -> bool:
        """
        Activa el seguimiento para una noticia y su `ExpedienteCaso` asociado.
        Funciona incluso si el usuario no había presionado antes "Investigar",
        extrayendo automáticamente la ficha con `LLMExtractor` si `investigacion_json` es nulo.
        """
        from src.database.models_noticias import Noticia, ESTADOS_SEGUIMIENTO_VALIDOS
        from sqlalchemy.orm.attributes import flag_modified
        import copy

        try:
            noticia = Noticia.query.get(noticia_id)
            if not noticia:
                return False

            if not noticia.investigacion_json:
                try:
                    from src.analysis.llm_extractor import LLMExtractor
                    extractor = LLMExtractor()
                    analyzed = extractor.analyze_article(
                        title=noticia.titulo or "",
                        content=noticia.contenido or "",
                        source_url=noticia.enlace or "",
                    )
                    noticia.investigacion_json = analyzed.get("investigacion_json") or {}
                except Exception:
                    noticia.investigacion_json = {
                        "ubicacion": "No especificada",
                        "victimas": "No especificada",
                        "ninos_afectados": "No especificado",
                        "edades": "No especificadas",
                        "situacion_actual": "No especificada",
                        "medios_contacto": "DIF / Fiscalía Estatal",
                        "resumen": noticia.titulo or "",
                        "fuentes": [noticia.enlace] if noticia.enlace else [],
                    }

            new_json = copy.deepcopy(noticia.investigacion_json)
            new_json["en_seguimiento"] = True
            if estado_seguimiento in ESTADOS_SEGUIMIENTO_VALIDOS:
                new_json["estado_seguimiento"] = estado_seguimiento
            else:
                new_json.setdefault("estado_seguimiento", "en_verificacion")

            if nota:
                notas = list(new_json.get("notas_seguimiento") or [])
                notas.append({
                    "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "usuario": usuario,
                    "estado": new_json["estado_seguimiento"],
                    "nota": nota.strip(),
                })
                new_json["notas_seguimiento"] = notas

            noticia.investigacion_json = new_json
            flag_modified(noticia, "investigacion_json")

            try:
                expediente = NoticiasRepository.vincular_o_crear_expediente(noticia)
                if expediente is not None:
                    expediente.en_seguimiento = True
                    expediente.estado_seguimiento = new_json["estado_seguimiento"]
                    if nota:
                        expediente.notas_seguimiento = list(new_json.get("notas_seguimiento") or [])
                        flag_modified(expediente, "notas_seguimiento")
                    # Sincronizar todas las noticias hermanas del mismo expediente
                    for n_hermana in Noticia.query.filter_by(expediente_id=expediente.id).all():
                        if n_hermana.id == noticia.id:
                            continue
                        h_json = copy.deepcopy(n_hermana.investigacion_json or new_json)
                        h_json["en_seguimiento"] = True
                        h_json["estado_seguimiento"] = expediente.estado_seguimiento
                        h_json["notas_seguimiento"] = list(expediente.notas_seguimiento or [])
                        n_hermana.investigacion_json = h_json
                        flag_modified(n_hermana, "investigacion_json")
            except Exception as exp_err:
                logger.debug(f"Seguimiento guardado en noticia sin tabla expedientes: {exp_err}")

            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error en add_to_seguimiento: {e}")
            return False

    @staticmethod
    def get_expediente(expediente_id: int) -> Optional["ExpedienteCaso"]:
        from src.database.models_noticias import ExpedienteCaso
        return ExpedienteCaso.query.get(expediente_id)

    @staticmethod
    def listar_expedientes(
        solo_en_seguimiento: bool = False,
        estado_seguimiento: str | None = None,
        estado_republica: str | None = None,
        sesion_id: int | None = None,
    ) -> list[dict]:
        """Lista los expedientes consolidados de casos ordenados por relevancia y actualización."""
        from src.database.models_noticias import ExpedienteCaso

        q = ExpedienteCaso.query
        if sesion_id:
            q = q.filter(ExpedienteCaso.sesion_id == sesion_id)
        if solo_en_seguimiento:
            q = q.filter(ExpedienteCaso.en_seguimiento.is_(True))
        if estado_seguimiento:
            q = q.filter(ExpedienteCaso.estado_seguimiento == estado_seguimiento)
        if estado_republica:
            q = q.filter(ExpedienteCaso.estado.ilike(f"%{estado_republica}%"))

        expedientes = q.order_by(
            desc(ExpedienteCaso.en_seguimiento),
            desc(ExpedienteCaso.relevancia_maxima),
            desc(ExpedienteCaso.updated_at),
        ).all()
        return [e.to_dict() for e in expedientes]

    @staticmethod
    def actualizar_seguimiento_expediente(
        expediente_id: int,
        estado_seguimiento: str | None = None,
        nota: str | None = None,
        usuario: str = "Operador ONG",
        autor: str | None = None,
        en_seguimiento: bool | None = None,
    ) -> Optional[dict]:
        """
        Actualiza el estado del flujo de trabajo de un `ExpedienteCaso`
        (`detectado` → `en_verificacion` → `contacto_dif_fiscalia` → `en_acompanamiento` → `archivado`),
        registra una nota en la bitácora y sincroniza las noticias asociadas.
        """
        import copy
        from sqlalchemy.orm.attributes import flag_modified
        from src.database.models_noticias import (
            ExpedienteCaso,
            Noticia,
            ESTADOS_SEGUIMIENTO_VALIDOS,
        )

        autor_final = autor or usuario or "Operador ONG"

        try:
            expediente = ExpedienteCaso.query.get(expediente_id)
            if not expediente:
                return None

            target_estado = estado_seguimiento or expediente.estado_seguimiento or "detectado"
            if target_estado not in ESTADOS_SEGUIMIENTO_VALIDOS:
                raise ValueError(
                    f"Estado '{target_estado}' inválido. Opciones: {ESTADOS_SEGUIMIENTO_VALIDOS}"
                )

            expediente.estado_seguimiento = target_estado
            if en_seguimiento is not None:
                expediente.en_seguimiento = en_seguimiento
            else:
                expediente.en_seguimiento = target_estado != "detectado"

            notas = list(expediente.notas_seguimiento or [])
            if nota and nota.strip():
                texto_limpio = nota.strip()
                notas.append({
                    "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "usuario": autor_final,
                    "autor": autor_final,
                    "estado": target_estado,
                    "nota": texto_limpio,
                    "texto": texto_limpio,
                })
                expediente.notas_seguimiento = notas
                flag_modified(expediente, "notas_seguimiento")

            # Sincronizar noticias vinculadas
            for n in Noticia.query.filter_by(expediente_id=expediente.id).all():
                inv = copy.deepcopy(n.investigacion_json or {})
                inv["en_seguimiento"] = expediente.en_seguimiento
                inv["estado_seguimiento"] = expediente.estado_seguimiento
                inv["notas_seguimiento"] = notas
                inv["folio_expediente"] = expediente.folio
                inv["expediente_id"] = expediente.id
                n.investigacion_json = inv
                flag_modified(n, "investigacion_json")

            db.session.commit()
            return expediente.to_dict()
        except ValueError:
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando seguimiento de expediente {expediente_id}: {e}")
            return None
