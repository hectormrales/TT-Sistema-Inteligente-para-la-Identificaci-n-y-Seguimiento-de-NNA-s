#!/usr/bin/env python3
# scripts/run_analysis_only.py
"""
Script de desarrollo: ejecuta el pipeline de análisis completo sobre un CSV
existente, saltando la fase de scraping (que puede tardar ~30 horas).

Uso dentro del contenedor Docker:
    docker exec -it nna-webapp python scripts/run_analysis_only.py
    docker exec -it nna-webapp python scripts/run_analysis_only.py --csv /app/data/noticias_analyzed_simplified.csv
    docker exec -it nna-webapp python scripts/run_analysis_only.py --csv /app/data/noticias_raw.csv --skip-postgres

Uso local (con virtualenv activado):
    python scripts/run_analysis_only.py --csv data/noticias_analyzed_simplified.csv

Pasos ejecutados (en orden):
    1. Carga directa del CSV (sin scraper)
    2. Deduplicación  (Hash → Jaccard → SimHash → TF-IDF coseno)
    3. Vectorización TF-IDF + similitud coseno
    4. Búsqueda mejorada con sinónimos
    5. Detección semántica con BETO  (SemanticDetector)
    6. Clustering semántico BERTopic
    7. Guardado CSV resultados
    8. Persistencia en PostgreSQL  (opcional, omitir con --skip-postgres)
"""

import argparse
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# ── 1. Configuración de logging ANTES de importar cualquier módulo propio ──────
# Formato detallado para desarrollo: timestamp + nivel + módulo + mensaje.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),          # consola (captura stack traces)
    ],
    force=True,                                     # sobreescribe config del framework
)
# Suprimir spam de librerías de terceros
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("torch").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("bertopic").setLevel(logging.WARNING)
logging.getLogger("umap").setLevel(logging.WARNING)
logging.getLogger("hdbscan").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("filelock").setLevel(logging.WARNING)

logger = logging.getLogger("run_analysis_only")

# ── 2. Asegurar que la raíz del proyecto esté en sys.path ─────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent   # .../TT-Sistema-...
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    logger.debug("PROJECT_ROOT añadido a sys.path: %s", PROJECT_ROOT)

# ── 3. Argparse ────────────────────────────────────────────────────────────────

DEFAULT_CSV = os.environ.get(
    "ANALYSIS_INPUT_CSV",
    "/app/data/noticias_analyzed_simplified.csv",  # ruta por defecto en Docker
)

parser = argparse.ArgumentParser(
    description="Pipeline de análisis NNA — sin scraping",
    formatter_class=argparse.RawTextHelpFormatter,
)
parser.add_argument(
    "--csv",
    default=DEFAULT_CSV,
    metavar="RUTA",
    help=(
        "Ruta al CSV de entrada con noticias crudas o pre-analizadas.\n"
        f"Por defecto: {DEFAULT_CSV}\n"
        "También puede ser controlada por la variable ANALYSIS_INPUT_CSV."
    ),
)
parser.add_argument(
    "--skip-postgres",
    action="store_true",
    default=False,
    help="Omite la persistencia en PostgreSQL (útil si no hay DB disponible).",
)
parser.add_argument(
    "--skip-bertopic",
    action="store_true",
    default=False,
    help="Omite el clustering BERTopic (más rápido para depurar solo BETO/dedup).",
)
parser.add_argument(
    "--skip-semantic",
    action="store_true",
    default=False,
    help="Omite la detección semántica BETO (prueba rápida de dedup/clustering).",
)
parser.add_argument(
    "--detector-mode",
    choices=["auto", "finetuned", "zero_shot", "hybrid"],
    default=None,
    metavar="MODO",
    help=(
        "Fuerza el modo del SemanticDetector.\n"
        "Si se omite, respeta DETECTOR_MODE del entorno (default: fine-tuned)."
    ),
)
parser.add_argument(
    "--limit",
    type=int,
    default=None,
    metavar="N",
    help="Limita el análisis a las primeras N filas (útil para pruebas rápidas).",
)
args = parser.parse_args()


# ── 4. Override DETECTOR_MODE si se pasó por CLI ──────────────────────────────
if args.detector_mode:
    os.environ["DETECTOR_MODE"] = args.detector_mode
    logger.info("DETECTOR_MODE forzado a: %s", args.detector_mode)


# ── 5. Carga del Flask app context (necesario para PostgreSQL) ─────────────────

def _get_app_context():
    """Crea y devuelve el contexto de la aplicación Flask."""
    try:
        from app import create_app
        flask_app = create_app()
        return flask_app
    except Exception as exc:
        logger.warning(
            "No se pudo crear el contexto Flask (%s). "
            "PostgreSQL no estará disponible.", exc
        )
        return None


# ── 6. Función principal ───────────────────────────────────────────────────────

def main():
    separador = "=" * 65

    print(separador)
    print("  PIPELINE DE ANÁLISIS NNA — MODO DESARROLLO (sin scraping)")
    print(separador)

    batch_id = datetime.now().strftime("DEV_ANALYSIS_%Y%m%d_%H%M%S")
    print(f"  Batch ID : {batch_id}")
    print(f"  CSV      : {args.csv}")
    print(f"  Postgres : {'DESACTIVADO (--skip-postgres)' if args.skip_postgres else 'ACTIVADO'}")
    print(f"  BERTopic : {'DESACTIVADO (--skip-bertopic)' if args.skip_bertopic else 'ACTIVADO'}")
    print(f"  BETO     : {'DESACTIVADO (--skip-semantic)' if args.skip_semantic else 'ACTIVADO'}")
    if args.limit:
        print(f"  Límite   : {args.limit} filas")
    print(separador)

    # ── PASO 0: Validar CSV ────────────────────────────────────────────────
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        # Si es relativa, resolverla desde PROJECT_ROOT
        csv_path = str(PROJECT_ROOT / csv_path)

    if not os.path.exists(csv_path):
        logger.error(
            "CSV no encontrado: %s\n"
            "Sugerencia: pasa la ruta completa con --csv /app/data/tu_archivo.csv",
            csv_path,
        )
        sys.exit(1)

    # ── PASO 1: Carga directa del CSV (SIN scraper) ────────────────────────
    print("\n[PASO 1/7] Cargando CSV de entrada...")
    try:
        import pandas as pd

        df_raw = pd.read_csv(csv_path, low_memory=False)
        logger.info("CSV cargado: %d filas × %d columnas", len(df_raw), len(df_raw.columns))

        if args.limit:
            df_raw = df_raw.head(args.limit)
            logger.info("Limitado a %d filas (--limit).", args.limit)

        if df_raw.empty:
            logger.error("El CSV está vacío. Abortando.")
            sys.exit(1)

        # Garantizar columnas mínimas que el analyzer espera
        _ensure_columns(df_raw)

        print(f"  ✓ {len(df_raw)} noticias cargadas desde {csv_path}")
        print(f"  Columnas disponibles: {list(df_raw.columns)}")

    except Exception:
        logger.error("Error al cargar el CSV:")
        traceback.print_exc()
        sys.exit(1)

    # ── Construir el analyzer e inyectar el DataFrame ──────────────────────
    print("\n[PASO 2/7] Inicializando SimplifiedNewsAnalyzer...")
    try:
        from src.analysis.analyzer import SimplifiedNewsAnalyzer
        analyzer = SimplifiedNewsAnalyzer()
        analyzer.df_original = df_raw.copy()
        analyzer.current_batch_id = batch_id
        print("  ✓ Analyzer inicializado")
    except Exception:
        logger.error("Error al inicializar el analyzer:")
        traceback.print_exc()
        sys.exit(1)

    # ── PASO 2: Vectorización TF-IDF + deduplicación coseno ───────────────
    print("\n[PASO 3/7] Vectorización TF-IDF + similitud coseno + deduplicación...")
    try:
        import numpy as np
        n_antes = len(analyzer.df_original)
        analyzer.step_3_vectorize_text()
        analyzer.step_6_similarity_analysis()   # incluye NewsDeduplicator
        n_despues = len(analyzer.df_processed)
        print(f"  ✓ Deduplicación: {n_antes} → {n_despues} noticias "
              f"({n_antes - n_despues} eliminadas)")
    except Exception:
        logger.error("Error en deduplicación/vectorización:")
        traceback.print_exc()
        sys.exit(1)

    # ── PASO 3: Búsqueda mejorada (paso 8, rápido) ────────────────────────
    print("\n[PASO 4/7] Configurando búsqueda con sinónimos (paso 8)...")
    try:
        analyzer.step_8_enhanced_search_setup()
        print("  ✓ Diccionario de sinónimos guardado")
    except Exception:
        logger.warning("step_8 falló (no crítico): %s", traceback.format_exc())

    # ── PASO 4: Detección semántica BETO (paso 9) ─────────────────────────
    if not args.skip_semantic:
        print("\n[PASO 5/7] Detección semántica con BETO (paso 9)...")
        try:
            analyzer.step_9_semantic_detection()
            _print_semantic_summary(analyzer.df_processed)
        except Exception:
            logger.error("Error en detección semántica BETO:")
            traceback.print_exc()
            # No abortamos: podemos seguir con los scores que haya
            logger.warning("Continuando sin scores semánticos actualizados...")
    else:
        print("\n[PASO 5/7] BETO omitido (--skip-semantic)")

    # ── PASO 5: Clustering BERTopic (paso 10) ─────────────────────────────
    if not args.skip_bertopic:
        print("\n[PASO 6/7] Clustering BERTopic (paso 10)...")
        try:
            analyzer.step_10_bertopic_clustering()
            print("  ✓ Clustering completado")
        except Exception:
            logger.error("Error en BERTopic:")
            traceback.print_exc()
            logger.warning("Continuando sin clustering semántico...")
    else:
        print("\n[PASO 6/7] BERTopic omitido (--skip-bertopic)")

    # ── PASO 6: Guardar CSV resultados ────────────────────────────────────
    print("\n[PASO 7/7] Guardando resultados en CSV...")
    try:
        analyzer.save_final_results()
        print("  ✓ CSV guardado exitosamente")
    except Exception:
        logger.error("Error al guardar CSV:")
        traceback.print_exc()

    # ── PASO 7: Persistencia PostgreSQL (opcional) ────────────────────────
    if not args.skip_postgres:
        print("\n[PASO 8/8] Persistencia en PostgreSQL (paso 11)...")
        flask_app = _get_app_context()
        if flask_app:
            try:
                with flask_app.app_context():
                    analyzer.step_11_persist_to_postgres()
                    print("  ✓ Datos persistidos en PostgreSQL")
            except Exception:
                logger.error("Error al persistir en PostgreSQL:")
                traceback.print_exc()
        else:
            logger.warning(
                "PostgreSQL omitido: contexto Flask no disponible. "
                "Use --skip-postgres para silenciar este aviso."
            )
    else:
        print("\n[PASO 8/8] PostgreSQL omitido (--skip-postgres)")

    # ── Resumen final ──────────────────────────────────────────────────────
    print(f"\n{separador}")
    print(f"  ✅  ANÁLISIS COMPLETADO — Batch: {batch_id}")
    _print_final_summary(analyzer.df_processed if analyzer.df_processed is not None
                         else analyzer.df_original)
    print(separador)


# ── Utilidades ─────────────────────────────────────────────────────────────────

def _ensure_columns(df):
    """Garantiza columnas mínimas que el pipeline espera."""
    defaults = {
        "titulo": "",
        "contenido": "",
        "fuente": "Desconocida",
        "fecha": None,
        "menores_identificados": "No",
        "clasificacion": "No relevante",
        "score_feminicidio": 0.0,
        "score_nna": 0.0,
        "score_compuesto": 0.0,
        "score_victima_indirecta": 0.0,
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
            logger.debug("Columna '%s' añadida con valor por defecto: %s", col, default)


def _print_semantic_summary(df):
    """Imprime métricas de la detección semántica al final del paso 9."""
    if df is None or "score_semantico" not in df.columns:
        return
    import numpy as np
    scores = df["score_semantico"].dropna().astype(float)
    alta = (df.get("clasificacion_final", df.get("clasificacion", "")) == "Alta").sum()
    media = (df.get("clasificacion_final", df.get("clasificacion", "")) == "Media").sum()
    baja = (df.get("clasificacion_final", df.get("clasificacion", "")) == "Baja").sum()
    no_rel = (df.get("clasificacion_final", df.get("clasificacion", "")) == "No relevante").sum()
    print(
        f"  ✓ Score semántico promedio: {scores.mean():.4f} | "
        f"Alta={alta} | Media={media} | Baja={baja} | No relevante={no_rel}"
    )


def _print_final_summary(df):
    """Imprime tabla resumen del resultado final."""
    if df is None or df.empty:
        print("  [!] DataFrame vacío — sin estadísticas disponibles")
        return

    total = len(df)
    nna = int((df.get("menores_identificados", "") == "Si").sum())
    col_clf = "clasificacion_final" if "clasificacion_final" in df.columns else "clasificacion"
    alta = int((df[col_clf] == "Alta").sum())
    media = int((df[col_clf] == "Media").sum())
    baja = int((df[col_clf] == "Baja").sum())
    no_rel = int((df[col_clf] == "No relevante").sum())

    print(f"  Total noticias analizadas : {total}")
    print(f"  Mencionan NNA             : {nna}")
    print(f"  Alta relevancia           : {alta}")
    print(f"  Media relevancia          : {media}")
    print(f"  Baja relevancia           : {baja}")
    print(f"  No relevante              : {no_rel}")

    if "score_semantico" in df.columns:
        avg_sem = df["score_semantico"].dropna().astype(float).mean()
        print(f"  Score semántico promedio  : {avg_sem:.4f}")

    if "topic_description" in df.columns:
        n_topics = df["topic_description"].nunique()
        print(f"  Tópicos BERTopic          : {n_topics}")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrumpido por el usuario (Ctrl+C).")
        sys.exit(130)
    except Exception:
        logger.critical("Error no manejado — stack trace completo:")
        traceback.print_exc()
        sys.exit(1)
