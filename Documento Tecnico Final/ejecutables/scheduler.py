#!/usr/bin/env python3
# scheduler.py — Servicio de recolección y análisis programado (v5.0 TT2)
"""
Ejecuta recolección RSS y análisis NLP en intervalos regulares.
Uso:
    python scheduler.py              → planificador automático
    python scheduler.py collect      → solo recolección
    python scheduler.py analyze      → solo análisis (con semántica)
    python scheduler.py analyze_basic → análisis sin BETO/BERTopic
    python scheduler.py full         → ciclo completo una vez
    python scheduler.py historical   → recolección histórica 2023-2026 (OE-2)
    python scheduler.py migrate_csv  → migrar CSV existente a PostgreSQL (OE-3)
"""

import os
import sys
import time
from datetime import datetime

import pandas as pd
import schedule

from src.analysis.analyzer import SimplifiedNewsAnalyzer
from src.collection.collector import collect_all_news
from src.analysis.dedup import NewsDeduplicator


DATA_DIR = os.environ.get('DATA_DIR', 'data')
DATA_FILE = os.path.join(DATA_DIR, 'noticias.csv')


def _log(message: str):
    """Log con timestamp."""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] {message}")


def collect_news():
    """Recolecta noticias y agrega al CSV acumulado."""
    try:
        _log("Iniciando recolección de noticias...")
        df_new = collect_all_news()

        if df_new.empty:
            _log("No se recolectaron noticias nuevas")
            return

        _log(f"Recolectadas {len(df_new)} noticias")

        if os.path.exists(DATA_FILE):
            df_existing = pd.read_csv(DATA_FILE)
            df_new = pd.concat([df_existing, df_new], ignore_index=True)

            # Deduplicación avanzada cross-site
            dedup = NewsDeduplicator(
                title_threshold=0.70,
                content_threshold=0.80,
            )
            pre = len(df_new)
            df_new = dedup.deduplicate(df_new, keep='best')
            post = len(df_new)
            _log(f"Deduplicación: {pre} → {post} ({pre - post} eliminados)")

        os.makedirs(DATA_DIR, exist_ok=True)
        df_new.to_csv(DATA_FILE, index=False)
        _log(f"Datos guardados en {DATA_FILE}")

    except Exception as e:
        _log(f"Error en recolección: {e}")


def analyze_news():
    """Ejecuta el pipeline completo de análisis (v5.0 con semántica)."""
    try:
        if not os.path.exists(DATA_FILE):
            _log("No hay datos para analizar")
            return

        _log("Iniciando análisis completo v5.0...")

        # Crear contexto Flask para que step_11 pueda persistir a PostgreSQL
        from app import create_app
        app = create_app()
        with app.app_context():
            analyzer = SimplifiedNewsAnalyzer()
            df = analyzer.run_complete_analysis(
                enable_semantic=True,
                enable_bertopic=True,
                enable_postgres=True,
            )

            if df is not None and not df.empty:
                df.to_csv(DATA_FILE, index=False)
                nna = (df['menores_identificados'] == 'Si').sum()
                pct = nna / len(df) * 100 if len(df) > 0 else 0
                _log(f"Análisis completado: {len(df)} noticias, {nna} NNA ({pct:.1f}%)")

    except Exception as e:
        _log(f"Error en análisis: {e}")


def analyze_news_basic():
    """Análisis básico sin BETO/BERTopic (rápido, sin GPU)."""
    try:
        if not os.path.exists(DATA_FILE):
            _log("No hay datos para analizar")
            return

        _log("Iniciando análisis básico (sin semántica)...")
        analyzer = SimplifiedNewsAnalyzer()
        df = analyzer.run_complete_analysis(
            enable_semantic=False,
            enable_bertopic=False,
            enable_postgres=True,
        )

        if df is not None and not df.empty:
            df.to_csv(DATA_FILE, index=False)
            _log(f"Análisis básico completado: {len(df)} noticias")

    except Exception as e:
        _log(f"Error en análisis básico: {e}")


def collect_historical():
    """OE-2: Recolección histórica de noticias 2023-2026."""
    try:
        from src.collection.historical_scraper import HistoricalCollector

        _log("Iniciando recolección histórica (2023-2026)...")
        collector = HistoricalCollector()
        results = collector.collect_all()

        if results is not None and not results.empty:
            historical_path = os.path.join(DATA_DIR, 'noticias_historical.csv')
            results.to_csv(historical_path, index=False)
            _log(f"Recolectadas {len(results)} noticias históricas → {historical_path}")

            # Agregar al CSV principal
            if os.path.exists(DATA_FILE):
                df_existing = pd.read_csv(DATA_FILE)
                combined = pd.concat([df_existing, results], ignore_index=True)

                dedup = NewsDeduplicator(title_threshold=0.70, content_threshold=0.80)
                pre = len(combined)
                combined = dedup.deduplicate(combined, keep='best')
                _log(f"Deduplicación: {pre} → {len(combined)}")
                combined.to_csv(DATA_FILE, index=False)
            else:
                results.to_csv(DATA_FILE, index=False)

    except Exception as e:
        _log(f"Error en recolección histórica: {e}")


def migrate_csv_to_postgres():
    """OE-3: Migra datos del CSV existente a PostgreSQL."""
    try:
        from app import create_app
        from src.database.repository import NoticiasRepository, init_fts_schema

        csv_path = os.path.join(DATA_DIR, 'noticias_analyzed_simplified.csv')
        if not os.path.exists(csv_path):
            csv_path = DATA_FILE
        if not os.path.exists(csv_path):
            _log("No hay CSV para migrar")
            return

        _log(f"Migrando {csv_path} a PostgreSQL...")

        app = create_app()
        with app.app_context():
            init_fts_schema()
            count = NoticiasRepository.importar_desde_csv(csv_path)
            _log(f"Migración completada: {count} noticias insertadas en PostgreSQL")

    except Exception as e:
        _log(f"Error en migración: {e}")


def run_full_cycle():
    """Recolección + análisis."""
    _log("Iniciando ciclo completo")
    collect_news()
    time.sleep(2)
    analyze_news()
    _log("Ciclo completo terminado")


def start_scheduler():
    """Planificador: recolección cada 6 h, análisis cada 12 h."""
    _log("Planificador automático iniciado")
    _log("Próxima recolección en 6h, próximo análisis en 12h")
    _log("(No se ejecuta ciclo al arrancar — usa 'full' para ejecución inmediata)")
    schedule.every(6).hours.do(collect_news)
    schedule.every(12).hours.do(analyze_news)

    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            _log("Planificador detenido")
            break
        except Exception as e:
            _log(f"Error en planificador: {e}")
            time.sleep(60)


# ── CLI ─────────────────────────────────────────────────────

COMMANDS = {
    'collect': collect_news,
    'analyze': analyze_news,
    'analyze_basic': analyze_news_basic,
    'full': run_full_cycle,
    'historical': collect_historical,
    'migrate_csv': migrate_csv_to_postgres,
    'schedule': start_scheduler,
}

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'schedule'
    fn = COMMANDS.get(cmd)
    if fn:
        fn()
    else:
        _log(f"Comando desconocido: {cmd}")
        _log(f"Comandos disponibles: {', '.join(COMMANDS)}")
