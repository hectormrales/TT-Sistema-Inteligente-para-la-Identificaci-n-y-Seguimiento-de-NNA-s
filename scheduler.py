#!/usr/bin/env python3
# scheduler.py — Servicio de recolección y análisis programado
"""
Ejecuta recolección RSS y análisis NLP en intervalos regulares.
Uso:
    python scheduler.py              → planificador automático
    python scheduler.py collect      → solo recolección
    python scheduler.py analyze      → solo análisis
    python scheduler.py full         → ciclo completo una vez
"""

import os
import sys
import time
from datetime import datetime

import pandas as pd
import schedule

from src.analysis.analyzer import SimplifiedNewsAnalyzer
from src.collection.collector import collect_all_news


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
            df_new.drop_duplicates(subset=['titulo', 'contenido'], keep='last', inplace=True)

        os.makedirs(DATA_DIR, exist_ok=True)
        df_new.to_csv(DATA_FILE, index=False)
        _log(f"Datos guardados en {DATA_FILE}")

    except Exception as e:
        _log(f"Error en recolección: {e}")


def analyze_news():
    """Ejecuta el pipeline completo de análisis."""
    try:
        if not os.path.exists(DATA_FILE):
            _log("No hay datos para analizar")
            return

        _log("Iniciando análisis completo...")
        analyzer = SimplifiedNewsAnalyzer()
        df = analyzer.run_complete_analysis()

        if df is not None and not df.empty:
            df.to_csv(DATA_FILE, index=False)
            nna = (df['menores_identificados'] == 'Si').sum()
            pct = nna / len(df) * 100 if len(df) > 0 else 0
            _log(f"Análisis completado: {len(df)} noticias, {nna} NNA ({pct:.1f}%)")

    except Exception as e:
        _log(f"Error en análisis: {e}")


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
    schedule.every(6).hours.do(collect_news)
    schedule.every(12).hours.do(analyze_news)

    run_full_cycle()

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
    'full': run_full_cycle,
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
