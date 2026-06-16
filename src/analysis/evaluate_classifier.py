

import argparse
import os
import sys
import logging
import numpy as np
import pandas as pd
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
    cohen_kappa_score,
)

# ── Configuración de logging ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Cálculo del Kappa de Cohen
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calcular_kappa(df: pd.DataFrame) -> float:
    """
    Calcula el Kappa de Cohen entre los dos anotadores humanos.

    Interpreta el nivel según la escala de Landis y Koch (1977):
        κ < 0.20  → Leve (no aceptable para publicación académica)
        0.20–0.40 → Regular
        0.40–0.60 → Moderado
        0.60–0.80 → Sustancial ✓ (aceptable)
        0.80–1.00 → Casi perfecto ✓✓

    Returns:
        Valor de κ en [−1, 1].
    """
    a1 = df["label_a1"].values
    a2 = df["label_a2"].values
    kappa = cohen_kappa_score(a1, a2)

    sep = "=" * 55
    print(f"\n{sep}")
    print("ACUERDO ENTRE ANOTADORES — Kappa de Cohen")
    print(sep)
    print(f"  Noticias evaluadas : {len(df)}")
    print(f"  Acuerdo exacto     : {(a1 == a2).sum()} / {len(df)} ({(a1 == a2).mean()*100:.1f}%)")
    print(f"  κ de Cohen         : {kappa:.4f}")

    if kappa < 0.20:
        nivel = "Leve — conjunto de prueba NO confiable"
    elif kappa < 0.40:
        nivel = "Regular"
    elif kappa < 0.60:
        nivel = "Moderado"
    elif kappa < 0.80:
        nivel = "Sustancial ✓"
    else:
        nivel = "Casi perfecto ✓✓"

    print(f"  Nivel de acuerdo   : {nivel}")
    print(sep)
    return kappa


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Evaluación del clasificador
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def evaluar_clasificador(
    df: pd.DataFrame,
    kappa: float,
    pred_col: str | None = None,
) -> dict:
    """
    Evalúa el clasificador BETO sobre el conjunto de prueba.

    Modos de operación:
      1. pred_col=None  → carga SemanticDetector (requiere torch/BETO).
                          Usar dentro de Docker o entorno con GPU.
      2. pred_col='col' → lee predicciones ya calculadas de esa columna
                          del CSV (valores: 'Alta', 'Media', 'Baja' o 1/0).
                          NO necesita torch. Útil en entorno local sin GPU.

    Solo se evalúan noticias donde AMBOS anotadores coinciden (consenso).

    Returns:
        dict con precisión, recall, f1, fp_rate, kappa, matriz de confusión.
    """
    y_true: list[int] = []
    y_pred: list[int] = []
    disputadas = 0

    sep = "=" * 55

    # ── Modo A: predicciones desde columna del CSV (sin torch) ────────────
    if pred_col is not None:
        if pred_col not in df.columns:
            logger.error(
                "La columna '%s' no existe en el CSV. Columnas disponibles: %s",
                pred_col, list(df.columns),
            )
            sys.exit(1)
        print(f"\n{sep}")
        print(f"MODO: predicciones desde columna '{pred_col}'")
        print(f"EVALUANDO CLASIFICADOR — {len(df)} noticias en test set")
        print(sep)

        for _, row in df.iterrows():
            nid = row.get("id_noticia", "?")
            a1  = int(row["label_a1"])
            a2  = int(row["label_a2"])
            if a1 != a2:
                disputadas += 1
                print(f"  [SKIP] ID {nid}: anotadores en desacuerdo (a1={a1}, a2={a2})")
                continue
            gold = a1

            raw_pred = row[pred_col]

            # Manejar NaN: noticia sin clasificar → tratar como Baja (pred=0)
            if raw_pred is None or (not isinstance(raw_pred, str) and pd.isna(raw_pred)):
                pred = 0
                print(f"  [NaN] ID {nid}: clasificacion vacía → pred=0 (Baja)  gold={gold}")
            elif isinstance(raw_pred, str):
                pred = 1 if raw_pred.strip().lower() == "alta" else 0
            else:
                pred = int(raw_pred)

            estado = "✓" if gold == pred else "✗"
            print(f"  [{estado}] ID {nid}: gold={gold}  pred={pred}  cls={raw_pred}")
            y_true.append(gold)
            y_pred.append(pred)

    # ── Modo B: inferencia en tiempo real con SemanticDetector (torch) ────
    else:
        print(f"\n{sep}")
        print(f"MODO: inferencia en tiempo real con BETO")
        print(f"EVALUANDO CLASIFICADOR — {len(df)} noticias en test set")
        print(sep)

        try:
            from src.analysis.semantic_detector import SemanticDetector
        except ImportError:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
            from src.analysis.semantic_detector import SemanticDetector

        detector = SemanticDetector(mode="auto")

        for _, row in df.iterrows():
            nid = row.get("id_noticia", "?")
            a1  = int(row["label_a1"])
            a2  = int(row["label_a2"])
            if a1 != a2:
                disputadas += 1
                print(f"  [SKIP] ID {nid}: anotadores en desacuerdo (a1={a1}, a2={a2})")
                continue
            gold = a1

            texto = f"{row.get('titulo', '')} {row.get('contenido', '')}"
            try:
                resultado     = detector.predict(texto)
                clasificacion = resultado.get("clasificacion", "Baja")
            except Exception as exc:
                logger.warning("Error al clasificar ID %s: %s", nid, exc)
                clasificacion = "Baja"

            pred   = 1 if clasificacion == "Alta" else 0
            estado = "✓" if gold == pred else "✗"
            print(
                f"  [{estado}] ID {nid}: gold={gold}  pred={pred}  cls={clasificacion}"
            )
            y_true.append(gold)
            y_pred.append(pred)

    if not y_true:
        logger.error("No hay noticias con consenso para evaluar. Abortando.")
        sys.exit(1)

    y_true_np = np.array(y_true)
    y_pred_np = np.array(y_pred)

    # ── Métricas ──────────────────────────────────────────────
    precision = precision_score(y_true_np, y_pred_np, zero_division=0)
    recall    = recall_score(y_true_np, y_pred_np, zero_division=0)
    f1        = f1_score(y_true_np, y_pred_np, zero_division=0)
    cm        = confusion_matrix(y_true_np, y_pred_np, labels=[0, 1])

    vn, fp_count = int(cm[0, 0]), int(cm[0, 1])
    fn, vp       = int(cm[1, 0]), int(cm[1, 1])
    fp_rate = fp_count / (vn + fp_count) if (vn + fp_count) > 0 else 0.0

    print(f"\n{sep}")
    print("MÉTRICAS DEL CLASIFICADOR")
    print(sep)
    print(f"  Noticias evaluadas (consenso) : {len(y_true)}")
    print(f"  Noticias excluidas (disputa)  : {disputadas}")
    print(f"  Precisión                     : {precision:.4f}  ({precision*100:.1f}%)")
    print(f"  Recall (sensibilidad)         : {recall:.4f}  ({recall*100:.1f}%)")
    print(f"  F1-Score                      : {f1:.4f}")
    print(f"  Tasa de Falsos Positivos      : {fp_rate*100:.1f}%")
    print(f"  κ de Cohen (anotadores)       : {kappa:.4f}")
    print()
    print("  Matriz de confusión:")
    print("                  Pred=0 (neg)  Pred=1 (pos)")
    print(f"  Gold=0 (neg)       {vn:5d}         {fp_count:5d}   ← FP = {fp_count}")
    print(f"  Gold=1 (pos)       {fn:5d}         {vp:5d}   ← FN = {fn}")
    print()
    print("  Reporte completo:")
    print(
        classification_report(
            y_true_np, y_pred_np,
            target_names=["No relevante", "Alta relevancia"],
            zero_division=0,
        )
    )
    print(sep)

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fp_rate": fp_rate,
        "kappa": kappa,
        "cm": cm,
        "n_total": len(y_true),
        "n_disputadas": disputadas,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Exportación de tablas LaTeX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def exportar_latex(metricas: dict, output_path: str = "metricas_clasificador.tex") -> None:
    """
    Genera código LaTeX con la tabla de métricas y la matriz de confusión,
    listo para insertar en 8Resultados.tex.
    """
    p  = metricas["precision"]
    r  = metricas["recall"]
    f1 = metricas["f1"]
    fp = metricas["fp_rate"]
    k  = metricas["kappa"]
    cm = metricas["cm"]
    n  = metricas["n_total"]
    nd = metricas["n_disputadas"]

    vn, fp_c = int(cm[0, 0]), int(cm[0, 1])
    fn, vp   = int(cm[1, 0]), int(cm[1, 1])

    # Determinar nivel de kappa para el texto
    if k >= 0.80:
        nivel_kappa = "casi perfecto"
    elif k >= 0.60:
        nivel_kappa = "sustancial"
    elif k >= 0.40:
        nivel_kappa = "moderado"
    else:
        nivel_kappa = "regular"

    latex = f"""\
% ══════════════════════════════════════════════════════════════
%  Código generado automáticamente por evaluate_classifier.py
%  Insertar en 8Resultados.tex dentro de \\section{{Evaluación...}}
% ══════════════════════════════════════════════════════════════

\\subsection{{Evaluación sobre conjunto de prueba etiquetado}}
\\label{{subsec:res_metricas_clasificador}}

Para validar el desempeño del clasificador escalonado sobre datos \\textbf{{no vistos
durante el fine-tuning}}, se construyó un conjunto de prueba de $n={n}$ noticias
seleccionadas aleatoriamente del corpus de producción, excluyendo explícitamente
las instancias utilizadas en el entrenamiento del prototipo~4.
Las noticias fueron etiquetadas de forma independiente por dos anotadores
siguiendo un protocolo de codificación binaria:\\
etiqueta $1$ para casos fácticos de orfandad por feminicidio y etiqueta $0$
para cualquier otro contenido.
{f"De los ${n + nd}$ artículos originales, ${nd}$ fueron excluidos por falta de acuerdo entre anotadores." if nd > 0 else ""}
El acuerdo inter-anotador se midió mediante el coeficiente $\\kappa$ de
Cohen~\\cite{{cohen1960coefficient}}, obteniéndose $\\kappa = {k:.2f}$, valor
que corresponde a un nivel de acuerdo \\textit{{{nivel_kappa}}} según la escala
de Landis y Koch~\\cite{{landis1977measurement}}.

\\vspace{{0.5cm}}
\\begin{{table}}[htbp]
\\centering
\\caption{{Métricas de evaluación del clasificador BETO escalonado sobre el conjunto de prueba
etiquetado ($n = {n}$ noticias con consenso de anotadores)}}
\\label{{tab:metricas_clasificador}}
\\renewcommand{{\\arraystretch}}{{1.3}}
\\begin{{tabular}}{{|l|c|}}
\\hline
\\rowcolor{{black}}
\\textcolor{{white}}{{\\textbf{{Métrica}}}} & \\textcolor{{white}}{{\\textbf{{Valor}}}} \\\\
\\hline
Precisión (VP / VP+FP) & {p:.2f} \\\\
\\hline
Recall --- sensibilidad (VP / VP+FN) & {r:.2f} \\\\
\\hline
F1-Score & {f1:.2f} \\\\
\\hline
Tasa de Falsos Positivos & {fp*100:.1f}\\% \\\\
\\hline
$\\kappa$ de Cohen (acuerdo inter-anotador) & {k:.2f} \\\\
\\hline
\\end{{tabular}}
\\end{{table}}
\\vspace{{0.4cm}}

\\vspace{{0.5cm}}
\\begin{{table}}[htbp]
\\centering
\\caption{{Matriz de confusión del clasificador BETO escalonado (conjunto de prueba, $n={n}$)}}
\\label{{tab:confusion_matrix}}
\\renewcommand{{\\arraystretch}}{{1.4}}
\\begin{{tabular}}{{|l|c|c|}}
\\hline
\\rowcolor{{black}}
 & \\textcolor{{white}}{{\\textbf{{Predicción: No relevante}}}} &
   \\textcolor{{white}}{{\\textbf{{Predicción: Alta relevancia}}}} \\\\
\\hline
\\textbf{{Gold: No relevante}} & {vn} (Verdadero Negativo) & {fp_c} (Falso Positivo) \\\\
\\hline
\\textbf{{Gold: Alta relevancia}} & {fn} (Falso Negativo) & {vp} (Verdadero Positivo) \\\\
\\hline
\\end{{tabular}}
\\end{{table}}
\\vspace{{0.4cm}}
"""

    print(f"\n{'='*55}")
    print(f"CÓDIGO LaTeX → {output_path}")
    print("="*55)
    print(latex)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(latex)
    print(f"→ Guardado en {output_path}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. Punto de entrada
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Evaluación formal del clasificador BETO sobre un conjunto de prueba "
            "etiquetado por dos anotadores. Calcula Kappa de Cohen, Precisión, "
            "Recall, F1 y Matriz de Confusión, y exporta tablas LaTeX."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  # Modo A — predicciones desde columna del CSV (sin torch, funciona local):\n"
            "  python evaluate_classifier.py --test_csv test_labels.csv --from_col clasificacion\n"
            "\n"
            "  # Modo B — inferencia en tiempo real con BETO (requiere Docker/torch):\n"
            "  python evaluate_classifier.py --test_csv test_labels.csv\n"
            "  docker exec -it tt-webapp python -m src.analysis.evaluate_classifier "
            "--test_csv data/test_labels.csv\n"
        ),
    )
    parser.add_argument(
        "--test_csv",
        required=True,
        help=(
            "Ruta al CSV con las noticias etiquetadas. "
            "Columnas obligatorias: id_noticia, titulo, contenido, label_a1, label_a2."
        ),
    )
    parser.add_argument(
        "--from_col",
        default=None,
        metavar="COLUMNA",
        help=(
            "Nombre de la columna del CSV que ya contiene las predicciones del sistema "
            "(p.ej. 'clasificacion' exportada de PostgreSQL). "
            "Acepta valores: 'Alta'/'Media'/'Baja' o 1/0. "
            "Si se omite, el script carga SemanticDetector y ejecuta inferencia "
            "en tiempo real (requiere torch)."
        ),
    )
    parser.add_argument(
        "--output_tex",
        default="metricas_clasificador.tex",
        help="Ruta del archivo .tex de salida (default: metricas_clasificador.tex).",
    )
    args = parser.parse_args()

    if not os.path.exists(args.test_csv):
        logger.error("Archivo no encontrado: %s", args.test_csv)
        sys.exit(1)

    df = pd.read_csv(args.test_csv)
    logger.info(
        "Cargando conjunto de prueba: %d noticias desde '%s'", len(df), args.test_csv
    )

    # Validar columnas obligatorias
    required_cols = {"titulo", "contenido", "label_a1", "label_a2"}
    missing = required_cols - set(df.columns)
    if missing:
        logger.error("Columnas faltantes en el CSV: %s", missing)
        sys.exit(1)

    if args.from_col:
        logger.info(
            "Modo A activado: leyendo predicciones desde la columna '%s' (sin torch).",
            args.from_col,
        )
    else:
        logger.info(
            "Modo B activado: inferencia en tiempo real con SemanticDetector (requiere torch)."
        )

    kappa    = calcular_kappa(df)
    metricas = evaluar_clasificador(df, kappa, pred_col=args.from_col)
    exportar_latex(metricas, args.output_tex)


if __name__ == "__main__":
    main()
