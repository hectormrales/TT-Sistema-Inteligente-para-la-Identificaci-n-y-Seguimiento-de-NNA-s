"""
scripts/train_model.py
Script de entrenamiento del clasificador semántico BETO (v5.1).

Uso:
    python scripts/train_model.py --csv data/noticias_analyzed_simplified.csv
    python scripts/train_model.py --csv data/noticias.csv --epochs 6 --patience 3
"""
import argparse
import logging
import sys
import os

# Asegurar que el raíz del proyecto esté en el path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train_model")


def main():
    parser = argparse.ArgumentParser(description="Fine-tuning SemanticDetector BETO")
    parser.add_argument(
        "--csv",
        default="data/noticias_analyzed_simplified.csv",
        help="Ruta al CSV histórico generado por el pipeline heurístico.",
    )
    parser.add_argument("--epochs", type=int, default=4, help="Épocas máximas.")
    parser.add_argument("--patience", type=int, default=2, help="Paciencia Early Stopping.")
    parser.add_argument("--val-split", type=float, default=0.2, help="Fracción de validación.")
    parser.add_argument("--balance-ratio", type=float, default=1.5, help="Ratio balanceo neg/pos.")
    args = parser.parse_args()

    # 1. Cargar datos históricos
    logger.info("Cargando CSV: %s", args.csv)
    df = pd.read_csv(args.csv, encoding="utf-8")
    logger.info("  → %d filas cargadas. Columnas: %s", len(df), list(df.columns))

    # 2. Instanciar el detector (modo auto; advertirá si no hay modelo previo)
    from src.analysis.semantic_detector import SemanticDetector

    detector = SemanticDetector(mode="auto")

    # 3. Preparar datos de entrenamiento
    logger.info("Preparando datos de entrenamiento (etiquetado estricto)...")
    df_train = detector.prepare_training_data(df, balance_ratio=args.balance_ratio)
    logger.info(
        "  → %d muestras: %d positivas / %d negativas",
        len(df_train),
        int((df_train["etiqueta"] == 1).sum()),
        int((df_train["etiqueta"] == 0).sum()),
    )

    if len(df_train) < 20:
        logger.error("Dataset demasiado pequeño (%d muestras). Se necesitan al menos 20.", len(df_train))
        sys.exit(1)

    # 4. Fine-tuning con Early Stopping
    logger.info(
        "Iniciando fine-tuning (epochs=%d, patience=%d, val_split=%.0f%%)...",
        args.epochs, args.patience, args.val_split * 100,
    )
    metrics = detector.fine_tune(
        df=df_train,
        text_col="texto",
        label_col="etiqueta",
        val_split=args.val_split,
        epochs=args.epochs,
        early_stopping_patience=args.patience,
    )

    # 5. Resumen de resultados
    logger.info("=" * 55)
    logger.info("ENTRENAMIENTO COMPLETADO")
    logger.info("  Mejor F1 validación : %.4f", metrics["best_f1"])
    logger.info("  Precisión final     : %.4f", metrics["final_precision"])
    logger.info("  Recall final        : %.4f", metrics["final_recall"])
    logger.info("  Épocas ejecutadas   : %d", len(metrics["history"]["train_loss"]))
    logger.info("  Modelo guardado en  : models/finetuned/model.pt")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
