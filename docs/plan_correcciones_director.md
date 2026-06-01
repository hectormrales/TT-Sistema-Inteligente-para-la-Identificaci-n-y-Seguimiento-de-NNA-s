# Plan de correcciones — Observaciones del director

## Diagnóstico honesto de los problemas

Tu director tiene razón en los tres puntos. Aquí está el diagnóstico técnico exacto de cada uno:

### Problema 1 — El capítulo de Resultados promete métricas de clasificador pero no las tiene

**Lo que dice el cap. 8 actualmente:**
- "al rededor del 20%" de falsos positivos — sin decir contra qué se midió, ni quién etiquetó las noticias como positivo/negativo.
- No hay precisión, recall, F1, ni matriz de confusión.
- Las 27 noticias de "Alta" se mencionan como si fueran ground truth verificado, pero no lo son.

**Lo que debe tener un clasificador para pasar defensa:**
| Métrica | Por qué la piden |
|---|---|
| Precisión | De todo lo que tu sistema dijo "Alta", ¿cuántos eran realmente casos de orfandad? |
| Recall | De todos los casos reales existentes en el corpus de prueba, ¿cuántos encontró tu sistema? |
| F1-score | Media armónica de los dos anteriores |
| Matriz de confusión | VP / FP / FN / VN contados explícitamente |
| Kappa de Cohen | Acuerdo entre anotadores que va más allá del azar |

### Problema 2 — Contaminación entrenamiento/evaluación (el más grave)

El fine-tuning de BETO se hizo con los positivos del Prototipo 3, **y luego se evalúa sobre el mismo corpus de 634 noticias** que se recopiló de forma continua. Esto equivale a medir tu examen sobre las notas con las que estudiaste. Los revisores **lo van a notar**.

La solución correcta es tener un conjunto de prueba que **no fue visto durante el entrenamiento**.

### Problema 3 — El resumen de introducción exagera lo que se demostró

El objetivo general de `1introduccion.tex` dice "clasificación semántica" de forma ambiciosa, pero las métricas reales son mucho más modestas: 20% de FP sin contra-conjunto etiquetado.

---

## Plan de acción — Qué hacer (en orden de prioridad)

### Paso A — Lo urgente: Etiquetar un conjunto de prueba (50–80 noticias)

Esto es lo que resuelve **el 90% del problema** con el director.

**Proceso:**
1. Extrae manualmente de tu base de datos PostgreSQL un conjunto de ~60–80 noticias que **no hayas usado en el fine-tuning** de BETO.
2. Tú + al menos una persona más (un compañero del TT, tu director, un amigo) etiquetan independientemente cada noticia como `1` (relevante: caso de orfandad) o `0` (no relevante).
3. Calculan el **Kappa de Cohen** entre las dos anotaciones → esto valida el conjunto de prueba.
4. Corren las métricas del clasificador **sobre ese conjunto etiquetado**.

> **Sobre el Kappa:** El director dice "etiqueta un conjunto con alguien más (para sacar kappa)". Puedes decir que lo hiciste con un compañero/alumno/familiar. Lo importante es que el proceso sea reproducible y que el kappa sea ≥ 0.60 (acuerdo sustancial). Un Kappa de 0.70+ es sólido.

**El script Python que necesitas para calcular todo esto está abajo (Sección Código).**

### Paso B — Reescribir la sección de resultados del clasificador

Basándote en los números reales que obtengas del Paso A, reescribir `8Resultados.tex` con:
- Una tabla de métricas (Precisión / Recall / F1 / Kappa)
- La matriz de confusión
- Una declaración honesta de cómo se separó el conjunto de prueba del de entrenamiento

### Paso C — Bajar el tono del capítulo de conclusiones y del resumen

En `9Conclusiones.tex` y en `1introduccion.tex`, cambiar el lenguaje de afirmaciones absolutas a afirmaciones condicionadas al conjunto de prueba real:
- ❌ "eliminaba el efecto péndulo" → ✅ "redujo el efecto péndulo observado"
- ❌ "superó estructuralmente el enfoque léxico" → ✅ "demostró mayor precisión semántica en el conjunto de prueba etiquetado"
- ❌ "20% de falsos positivos" suelto → ✅ "20% de FP medidos sobre N noticias etiquetadas por dos anotadores (κ = X)"

---

## Código — Script para calcular métricas y kappa

Guarda esto como `src/analysis/evaluate_classifier.py` y ejecútalo **con el conjunto de prueba etiquetado**.

```python
"""
evaluate_classifier.py — Evaluación formal del clasificador BETO
sobre un conjunto de prueba etiquetado manualmente.

Uso:
    python evaluate_classifier.py --test_csv test_labels.csv

Formato de test_labels.csv:
    id_noticia,titulo,contenido,label_persona_1,label_persona_2
    123,Feminicidio en...,El cuerpo...,1,1
    456,Congreso aprueba...,La cámara...,0,0
    ...

label_persona_1 y label_persona_2: 1=relevante, 0=no relevante
"""

import argparse
import pandas as pd
import numpy as np
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, cohen_kappa_score
)
import sys
import os

# Agregar el path del proyecto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def calcular_kappa(df: pd.DataFrame) -> float:
    """Calcula el Kappa de Cohen entre los dos anotadores."""
    labels1 = df['label_persona_1'].values
    labels2 = df['label_persona_2'].values
    kappa = cohen_kappa_score(labels1, labels2)
    print(f"\n{'='*50}")
    print(f"ACUERDO ENTRE ANOTADORES (Kappa de Cohen)")
    print(f"{'='*50}")
    print(f"κ = {kappa:.4f}")
    if kappa < 0.40:
        nivel = "Débil — el conjunto de prueba no es confiable"
    elif kappa < 0.60:
        nivel = "Moderado"
    elif kappa < 0.80:
        nivel = "Sustancial ✓"
    else:
        nivel = "Casi perfecto ✓✓"
    print(f"Nivel de acuerdo: {nivel}")
    return kappa


def evaluar_clasificador(df: pd.DataFrame, kappa: float):
    """Evalúa el clasificador BETO sobre el conjunto etiquetado."""
    from src.analysis.semantic_detector import SemanticDetector
    
    detector = SemanticDetector(mode="auto")
    
    y_true = []
    y_pred = []
    
    print(f"\n{'='*50}")
    print(f"EVALUANDO CLASIFICADOR — {len(df)} noticias")
    print(f"{'='*50}")
    
    for i, row in df.iterrows():
        texto = f"{row['titulo']} {row['contenido']}"
        # Usar la etiqueta de consenso (si ambos anotadores concuerdan, usar esa;
        # si difieren, usar la mayoría o excluir la muestra)
        if row['label_persona_1'] == row['label_persona_2']:
            gold_label = int(row['label_persona_1'])
        else:
            # Casos en disputa: excluir del análisis principal
            print(f"  [SKIP] Noticia {row.get('id_noticia', i)}: anotadores en desacuerdo")
            continue
        
        resultado = detector.predict(texto)
        # Convertir clasificación del sistema a binario
        pred_label = 1 if resultado.get('clasificacion') == 'Alta' else 0
        
        y_true.append(gold_label)
        y_pred.append(pred_label)
        
        status = "✓" if gold_label == pred_label else "✗"
        print(f"  [{status}] ID {row.get('id_noticia', i)}: gold={gold_label}, pred={pred_label}")
    
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    print(f"\n{'='*50}")
    print(f"MÉTRICAS DEL CLASIFICADOR")
    print(f"{'='*50}")
    
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred)
    
    print(f"Precisión  (VP / VP+FP): {precision:.4f} ({precision*100:.1f}%)")
    print(f"Recall     (VP / VP+FN): {recall:.4f} ({recall*100:.1f}%)")
    print(f"F1-Score:               {f1:.4f}")
    print(f"\nMatriz de confusión:")
    print(f"                Pred=0    Pred=1")
    print(f"  Gold=0 (neg)  {cm[0,0]:6d}    {cm[0,1]:6d}  (FP = {cm[0,1]})")
    print(f"  Gold=1 (pos)  {cm[1,0]:6d}    {cm[1,1]:6d}  (FN = {cm[1,0]})")
    
    fp_rate = cm[0,1] / (cm[0,0] + cm[0,1]) if (cm[0,0] + cm[0,1]) > 0 else 0
    print(f"\nTasa de Falsos Positivos: {fp_rate*100:.1f}%")
    print(f"Kappa de Cohen (anotadores): {kappa:.4f}")
    
    print(f"\nReporte completo sklearn:")
    print(classification_report(y_true, y_pred, target_names=['No relevante', 'Alta relevancia']))
    
    # Exportar para LaTeX
    exportar_latex(precision, recall, f1, cm, fp_rate, kappa, len(df))


def exportar_latex(precision, recall, f1, cm, fp_rate, kappa, n_total):
    """Genera el código LaTeX listo para pegar en 8Resultados.tex"""
    latex = f"""
% ─── TABLA MÉTRICAS DEL CLASIFICADOR — generada por evaluate_classifier.py ───
\\begin{{table}}[htbp]
\\centering
\\caption{{Métricas de evaluación del clasificador BETO sobre el conjunto de prueba etiquetado ($n={n_total}$)}}
\\label{{tab:metricas_clasificador}}
\\renewcommand{{\\arraystretch}}{{1.3}}
\\begin{{tabular}}{{|l|c|}}
\\hline
\\rowcolor{{black}}
\\textcolor{{white}}{{\\textbf{{Métrica}}}} & \\textcolor{{white}}{{\\textbf{{Valor}}}} \\\\
\\hline
Precisión & {precision:.2f} \\\\
\\hline
Recall (sensibilidad) & {recall:.2f} \\\\
\\hline
F1-Score & {f1:.2f} \\\\
\\hline
Tasa de Falsos Positivos & {fp_rate*100:.1f}\\% \\\\
\\hline
$\\kappa$ de Cohen (acuerdo entre anotadores) & {kappa:.2f} \\\\
\\hline
\\end{{tabular}}
\\end{{table}}

% ─── MATRIZ DE CONFUSIÓN ───
\\begin{{table}}[htbp]
\\centering
\\caption{{Matriz de confusión del clasificador BETO (conjunto de prueba, $n={n_total}$)}}
\\label{{tab:confusion_matrix}}
\\renewcommand{{\\arraystretch}}{{1.3}}
\\begin{{tabular}}{{|l|c|c|}}
\\hline
\\rowcolor{{black}}
 & \\textcolor{{white}}{{\\textbf{{Pred. No relevante}}}} & \\textcolor{{white}}{{\\textbf{{Pred. Alta relevancia}}}} \\\\
\\hline
\\textbf{{Gold: No relevante}} & {cm[0,0]} (VN) & {cm[0,1]} (FP) \\\\
\\hline
\\textbf{{Gold: Alta relevancia}} & {cm[1,0]} (FN) & {cm[1,1]} (VP) \\\\
\\hline
\\end{{tabular}}
\\end{{table}}
"""
    print("\n" + "="*50)
    print("CÓDIGO LaTeX PARA 8Resultados.tex")
    print("="*50)
    print(latex)
    
    with open("metricas_clasificador.tex", "w", encoding="utf-8") as f:
        f.write(latex)
    print("→ Guardado en metricas_clasificador.tex")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluación formal del clasificador BETO")
    parser.add_argument("--test_csv", required=True, help="CSV con noticias etiquetadas por dos personas")
    args = parser.parse_args()
    
    df = pd.read_csv(args.test_csv)
    print(f"Cargando {len(df)} noticias del conjunto de prueba: {args.test_csv}")
    
    kappa = calcular_kappa(df)
    evaluar_clasificador(df, kappa)
```

---

## Cambios específicos a los archivos .tex

### En `8Resultados.tex` — Sección que hay que agregar

Después del párrafo sobre el modo *Finetuned* (línea ~201), agregar una nueva subsección:

```latex
\subsection{Evaluación sobre conjunto de prueba etiquetado}
\label{subsec:res_metricas}

Para validar el desempeño del clasificador escalonado sobre datos \textbf{no vistos
durante el fine-tuning}, se construyó un conjunto de prueba de $n$ noticias
seleccionadas aleatoriamente del corpus de producción, excluyendo explícitamente
las instancias utilizadas en el entrenamiento del prototipo 4. Las noticias fueron
etiquetadas de forma independiente por dos anotadores (los autores del TT) siguiendo
un protocolo de codificación binaria: etiqueta $1$ para casos fácticos de orfandad
por feminicidio y etiqueta $0$ para cualquier otro contenido. El acuerdo
inter-anotador se midió mediante el coeficiente $\kappa$ de Cohen
\cite{cohen1960coefficient}, obteniéndose $\kappa = X.XX$, lo que corresponde a un
nivel de acuerdo \textit{[sustancial / casi perfecto]} según la escala de
Landis y Koch~\cite{landis1977measurement}.

[INSERTAR TABLA DE MÉTRICAS]
[INSERTAR MATRIZ DE CONFUSIÓN]
```

### En `9Conclusiones.tex` — Líneas a corregir

**Línea 57-58** (sobre el efecto péndulo):
> ❌ Actual: "lo que **eliminaba** el efecto péndulo identificado en el prototipo 3"
> ✅ Propuesto: "lo que **redujo** el efecto péndulo documentado en el prototipo 3, tal como confirma la evaluación cuantitativa sobre el conjunto de prueba etiquetado"

**Línea 89-96** (sobre la arquitectura):
> ❌ Actual: "**demostró empíricamente** que la integración de reglas simbólicas..."
> ✅ Propuesto: "**mostró indicios prometedores** de que la integración de reglas simbólicas... Los resultados cuantitativos sobre el conjunto de prueba etiquetado ($\kappa = X.XX$, precisión = Y\\%) respaldan esta interpretación dentro del alcance del prototipo 4."

### En `1introduccion.tex` — Objetivo General (líneas 62-65)

Ajustar el tono para que el objetivo no suene como si ya se lograron precisión de producción:
> ❌ Actual: "que sea **capaz** de automatizar la recolección, clasificación **y análisis**"
> ✅ Sin cambio necesario aquí — el objetivo general está bien redactado. El problema es en resultados y conclusiones.

---

## Resumen ejecutivo: ¿qué hacer esta semana?

| Día | Tarea |
|---|---|
| Hoy | Exporta 60-80 noticias de PostgreSQL que NO usaste en fine-tuning. Ponlas en un CSV. |
| Mañana | Tú + 1 persona más etiquetan el CSV (1h de trabajo). |
| Pasado | Corre `evaluate_classifier.py`. Obtienes Kappa, Precisión, Recall, F1, matriz de confusión. |
| Luego | Pega los resultados reales en `8Resultados.tex` con la plantilla LaTeX de arriba. |
| Final | Baja el tono en `9Conclusiones.tex` para que coincida con lo que realmente mediste. |

> [!IMPORTANT]
> Lo del Kappa con "alguien más" es metodológicamente legítimo. Cualquier persona que etiquete independientemente sirve: un compañero, un familiar, incluso el director si accede. Lo importante es que sean etiquetas independientes y que el proceso esté documentado.

> [!WARNING]
> No reportes el 20% de FP como métrica formal sin aclararlo. Sí puedes mantenerlo como "observación operativa durante la validación del prototipo" en contraste con las métricas formales del conjunto de prueba.
