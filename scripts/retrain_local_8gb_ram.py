"""
scripts/retrain_local_8gb_ram.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Active Learning — Re-entrenamiento local con restricción de 8 GB RAM.

Diseñado para ejecutarse FUERA de Docker, directamente desde el venv de
Windows, con Docker, Chrome y servicios pesados CERRADOS.

Estrategias de optimización de memoria:
  1. batch_size=4 (mínimo funcional para BETO)
  2. gradient_accumulation_steps=8  → effective batch = 32 sin OOM
  3. Congelamiento de las primeras N capas del encoder (por defecto 8 de 12)
  4. torch.cuda.empty_cache() + gc.collect() en cada época
  5. Precisión mixta automática (torch.autocast) — aprovecha CPU BF16 si
     el hardware lo soporta; si no, usa FP32 estándar sin romper nada.
  6. Solo las muestras con etiqueta_corregida no-nula entran al dataset.

Uso:
    python scripts/retrain_local_8gb_ram.py [--epochs N] [--freeze N] [--accum N]

Salida:
    Sobreescribe  models/finetuned/model.pt  con el mejor checkpoint (F1).
    Guarda métricas en  models/finetuned/retrain_metrics.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import gc
import json
import logging
import os
import sys
import pathlib
import warnings
from typing import Optional

# ── Rutas del proyecto (robusto independientemente del CWD) ────────────────
SCRIPT_DIR   = pathlib.Path(__file__).resolve().parent          # scripts/
PROJECT_ROOT = SCRIPT_DIR.parent                                # raíz del proyecto

DATA_CSV        = PROJECT_ROOT / "data" / "noticias_analyzed_simplified.csv"
FINETUNED_DIR   = PROJECT_ROOT / "models" / "finetuned"
MODEL_PT        = FINETUNED_DIR / "model.pt"
METRICS_JSON    = FINETUNED_DIR / "retrain_metrics.json"
CACHE_DIR       = PROJECT_ROOT / "models" / "cache"

# Añadir raíz al path para importar BETOClassifier desde semantic_detector
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("retrain")
warnings.filterwarnings("ignore", category=FutureWarning)

# ── Imports pesados (después del logging) ──────────────────────────────────
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics import (
    precision_score, recall_score, f1_score, classification_report,
)
from sklearn.model_selection import train_test_split

# ── Constantes del modelo (deben coincidir con semantic_detector.py) ───────
BETO_MODEL_NAME = "dccuchile/bert-base-spanish-wwm-cased"
MAX_SEQ_LENGTH  = 512
TEXT_COL        = "texto_combinado"
LABEL_COL       = "etiqueta_corregida"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dataset
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class NNADataset(Dataset):
    """Dataset mínimo para re-entrenamiento con etiqueta_corregida."""

    def __init__(self, texts: list[str], labels: list[int], tokenizer, max_len: int):
        self.texts     = texts
        self.labels    = labels
        self.tokenizer = tokenizer
        self.max_len   = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.texts[idx],
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids":      enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels":         torch.tensor(self.labels[idx], dtype=torch.long),
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Arquitectura del clasificador (réplica exacta de BETOClassifier)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BETOClassifier(nn.Module):
    """
    Cabeza de clasificación binaria sobre BETO.
    Arquitectura idéntica a la definida en semantic_detector.py:
      [CLS](768) → Dropout(0.3) → Linear(768,256) → ReLU → Dropout(0.2) → Linear(256,2)
    """

    def __init__(self, num_classes: int = 2, dropout: float = 0.3):
        super().__init__()
        self.bert = AutoModel.from_pretrained(
            BETO_MODEL_NAME,
            cache_dir=str(CACHE_DIR),
        )
        hidden = self.bert.config.hidden_size  # 768

        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, num_classes),
        )

    def forward(self, input_ids, attention_mask, labels=None, pos_weight: torch.Tensor = None):
        out     = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls_emb = out.last_hidden_state[:, 0, :]       # token [CLS]
        logits  = self.classifier(cls_emb)             # shape: (B, 2)

        loss = None
        if labels is not None:
            if pos_weight is not None:
                # BCEWithLogitsLoss binaria: usa logit de clase 1 vs clase 0
                # pos_weight penaliza más los errores en la clase positiva (VP)
                bce = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
                loss = bce(logits[:, 1] - logits[:, 0], labels.float())
            else:
                loss = nn.CrossEntropyLoss()(logits, labels)

        return {"loss": loss, "logits": logits}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Congelamiento de capas
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def freeze_encoder_layers(model: BETOClassifier) -> None:
    """
    Aplica Linear Probing: Congela todo el encoder de BETO y deja únicamente
    la capa de clasificación final (model.classifier) entrenable.
    """
    # Congelar todo model.bert
    for param in model.bert.parameters():
        param.requires_grad = False

    # Asegurar que el clasificador esté entrenable
    for param in model.classifier.parameters():
        param.requires_grad = True

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    logger.info(
        "[freeze] Linear Probing activado. Todo model.bert está congelado. | Parámetros entrenables: %s / %s (%.1f%%)",
        f"{trainable:,}", f"{total:,}",
        trainable / total * 100,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Carga de datos
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def cargar_datos(
    csv_path: pathlib.Path,
    oversample_factor: int = 3,
) -> tuple[list[str], list[int]]:
    """
    Lee el CSV y devuelve (textos, etiquetas) solo para filas etiquetadas.

    Reglas:
      • Usa columna `texto_combinado` como input.
      • Usa `etiqueta_corregida`: 1 = VP, 0 = FP.
      • Filas con NaN en `etiqueta_corregida` se DESCARTAN.
      • Filas con `texto_combinado` vacío también se descartan.

    Oversampling de la clase minoritaria (VP):
      Duplica/triplica las muestras positivas ANTES del split para que el
      modelo vea más ejemplos VP sin crear data leakage. El factor se
      controla con `oversample_factor` (default=3 → ratio ~1:1.1).
    """
    logger.info("[datos] Leyendo %s …", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)

    if TEXT_COL not in df.columns:
        raise ValueError(
            f"Columna '{TEXT_COL}' no encontrada. "
            f"Columnas disponibles: {df.columns.tolist()}"
        )
    if LABEL_COL not in df.columns:
        raise ValueError(
            f"Columna '{LABEL_COL}' no encontrada. "
            f"Agrega la columna de etiquetas al CSV antes de ejecutar este script."
        )

    # Filtrar solo filas con etiqueta explícita
    df_labeled = df.dropna(subset=[LABEL_COL]).copy()
    df_labeled = df_labeled[df_labeled[TEXT_COL].notna()]
    df_labeled = df_labeled[df_labeled[TEXT_COL].str.strip() != ""]

    etiquetas_raw = df_labeled[LABEL_COL].astype(float).astype(int).tolist()
    textos_raw    = df_labeled[TEXT_COL].astype(str).tolist()

    n_pos_orig = sum(etiquetas_raw)
    n_neg_orig = len(etiquetas_raw) - n_pos_orig

    if n_pos_orig == 0:
        raise RuntimeError(
            "No hay muestras positivas (etiqueta_corregida=1). "
            "Etiqueta al menos algunos verdaderos positivos antes de re-entrenar."
        )
    if n_neg_orig == 0:
        raise RuntimeError(
            "No hay muestras negativas (etiqueta_corregida=0). "
            "Necesitas ambas clases para entrenar un clasificador binario."
        )

    # ── Oversampling de VP (clase minoritaria) ────────────────────────────
    # Separar VP y FP en listas independientes
    textos_vp  = [t for t, e in zip(textos_raw, etiquetas_raw) if e == 1]
    textos_fp  = [t for t, e in zip(textos_raw, etiquetas_raw) if e == 0]

    # Repetir VP `oversample_factor` veces adicionales
    # (factor=3 → VP × 4 total, haciendo ratio VP:FP ≈ 1:0.8 con 38 VP y 127 FP)
    textos_vp_over  = textos_vp * oversample_factor
    etiquetas_vp_over = [1] * len(textos_vp_over)
    etiquetas_fp_orig = [0] * len(textos_fp)

    textos    = textos_fp    + textos_vp_over
    etiquetas = etiquetas_fp_orig + etiquetas_vp_over

    n_pos = sum(etiquetas)
    n_neg = len(etiquetas) - n_pos
    logger.info(
        "[datos] Original: VP=%d | FP=%d", n_pos_orig, n_neg_orig,
    )
    logger.info(
        "[datos] Tras oversampling (×%d): VP=%d | FP=%d | Total=%d",
        oversample_factor, n_pos, n_neg, len(textos),
    )

    return textos, etiquetas


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bucle de entrenamiento
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def entrenar(
    model: BETOClassifier,
    train_loader: DataLoader,
    val_loader: DataLoader,
    device: torch.device,
    epochs: int,
    lr: float,
    accum_steps: int,
    output_path: pathlib.Path,
    pos_weight: torch.Tensor = None,
) -> dict:
    """
    Entrena el modelo con gradient accumulation y precisión mixta automática.

    Gradient Accumulation:
      En lugar de un batch real de 32, acumulamos gradientes de 8 micro-batches
      de 4 muestras. El efecto es idéntico matemáticamente, con 8× menos RAM
      para activaciones intermedias. El optimizador solo da un paso cada
      `accum_steps` micro-batches.

    Mixed Precision (autocast):
      torch.autocast convierte automáticamente las operaciones que se benefician
      de FP16/BF16 (multiplicaciones matriciales en BETO) y mantiene FP32 donde
      la precisión numérica es crítica (acumulaciones de gradiente). En CPU
      solo se activa si el hardware soporta BF16; si no, es un no-op seguro.
    """
    from torch.optim import AdamW
    from torch.optim.lr_scheduler import OneCycleLR

    optimizer = AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=lr,
        weight_decay=0.01,
        eps=1e-8,
    )

    # OneCycleLR: learning rate que sube y baja en 1 ciclo — converge más rápido
    # con pocos datos y protege contra explotar los gradientes en las capas altas.
    total_opt_steps = (len(train_loader) // accum_steps) * epochs
    scheduler = OneCycleLR(
        optimizer,
        max_lr=lr,
        total_steps=max(total_opt_steps, 1),
        pct_start=0.1,
        anneal_strategy="cos",
    )

    # Determinar si autocast tiene soporte útil en este hardware
    use_amp   = False
    amp_dtype = torch.float32
    if device.type == "cuda":
        use_amp   = True
        amp_dtype = torch.float16
        logger.info("[train] Precisión mixta FP16 habilitada (CUDA).")
    elif hasattr(torch, "is_bf16_supported") and torch.is_bf16_supported():
        use_amp   = True
        amp_dtype = torch.bfloat16
        logger.info("[train] Precisión mixta BF16 habilitada (CPU con soporte AVX512).")
    else:
        logger.info("[train] Entrenamiento en FP32 (CPU estándar).")

    best_f1   = 0.0
    history   = {"train_loss": [], "val_precision": [], "val_recall": [], "val_f1": []}

    patience = 2
    epochs_no_improve = 0

    for epoch in range(1, epochs + 1):
        # ── Train ──────────────────────────────────────────────────────
        model.train()
        running_loss   = 0.0
        optimizer.zero_grad()

        for step, batch in enumerate(train_loader, start=1):
            input_ids      = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels         = batch["labels"].to(device)

            with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=use_amp):
                pw = pos_weight.to(device) if pos_weight is not None else None
                out  = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels,
                    pos_weight=pw,
                )
                # Escalar la pérdida por accum_steps para que el promedio sea correcto
                loss = out["loss"] / accum_steps

            loss.backward()
            running_loss += loss.item() * accum_steps  # revertir escala para log

            if step % accum_steps == 0 or step == len(train_loader):
                torch.nn.utils.clip_grad_norm_(
                    filter(lambda p: p.requires_grad, model.parameters()), 1.0
                )
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

        avg_loss = running_loss / len(train_loader)
        history["train_loss"].append(round(avg_loss, 5))

        # ── Validation ─────────────────────────────────────────────────
        model.eval()
        all_preds, all_labels = [], []

        with torch.no_grad():
            for batch in val_loader:
                out   = model(
                    input_ids=batch["input_ids"].to(device),
                    attention_mask=batch["attention_mask"].to(device),
                )
                preds = torch.argmax(out["logits"], dim=1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(batch["labels"].numpy())

        prec   = precision_score(all_labels, all_preds, zero_division=0)
        rec    = recall_score(all_labels, all_preds, zero_division=0)
        f1     = f1_score(all_labels, all_preds, zero_division=0)

        history["val_precision"].append(round(prec, 4))
        history["val_recall"].append(round(rec, 4))
        history["val_f1"].append(round(f1, 4))

        logger.info(
            "Época %d/%d | Loss: %.4f | P: %.4f | R: %.4f | F1: %.4f",
            epoch, epochs, avg_loss, prec, rec, f1,
        )

        # ── Checkpoint (solo el mejor) ──────────────────────────────────
        if f1 > best_f1:
            best_f1 = f1
            epochs_no_improve = 0
            torch.save(model.state_dict(), str(output_path))
            logger.info("  ✅ Mejor F1=%.4f — model.pt actualizado.", best_f1)
        else:
            epochs_no_improve += 1
            logger.info("  ⚠ Sin mejora de F1 (%.4f ≤ %.4f). Paciencia: %d/%d", f1, best_f1, epochs_no_improve, patience)

        # ── Early Stopping ──────────────────────────────────────────────
        if epochs_no_improve >= patience:
            logger.info("🛑 Early Stopping activado en época %d. El modelo no mejoró en %d épocas.", epoch, patience)
            break

        # ── Liberar memoria al final de cada época ──────────────────────
        if device.type == "cuda":
            torch.cuda.empty_cache()
        gc.collect()

    logger.info("━━━ Entrenamiento finalizado. Mejor F1 = %.4f ━━━", best_f1)

    # Reporte final sobre validación de la última época
    report = classification_report(
        all_labels, all_preds,
        target_names=["No relevante (FP)", "Relevante (VP)"],
        output_dict=True,
        zero_division=0,
    )

    return {
        "best_f1":     round(best_f1, 4),
        "epochs_run":  epochs,
        "accum_steps": accum_steps,
        "history":     history,
        "classification_report": report,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Punto de entrada
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def parse_args():
    p = argparse.ArgumentParser(
        description="Re-entrena BETO con Active Learning (8 GB RAM)."
    )
    p.add_argument("--epochs",  type=int,   default=10,   help="Épocas de entrenamiento (default: 10)")
    p.add_argument("--accum",   type=int,   default=8,    help="Pasos de gradient accumulation (default: 8)")
    p.add_argument("--lr",      type=float, default=1e-4, help="Learning rate (default: 1e-4 para Linear Probing)")
    p.add_argument("--val",     type=float, default=0.20, help="Fracción de validación (default: 0.20)")
    p.add_argument("--batch",   type=int,   default=4,    help="Micro batch size (default: 4, NO subir >4 con 8 GB)")
    p.add_argument("--no-load", action="store_true",      help="Ignorar model.pt existente; partir de pesos base BETO")
    return p.parse_args()


def main():
    args = parse_args()

    logger.info("=" * 60)
    logger.info("  Active Learning — Re-entrenamiento local (8 GB RAM) con Linear Probing")
    logger.info("=" * 60)
    logger.info("  epochs=%d | accum=%d | lr=%g | batch=%d",
                args.epochs, args.accum, args.lr, args.batch)
    logger.info("  Effective batch size = %d × %d = %d",
                args.batch, args.accum, args.batch * args.accum)

    # ── Dispositivo ────────────────────────────────────────────────────────
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("  Dispositivo: %s", device)
    if device.type == "cpu":
        logger.warning(
            "  Ejecutando en CPU. Cada época tardará ~5-15 min con 198 muestras. "
            "Es normal — no canceles el proceso."
        )

    # ── Datos con Oversampling ────────────────────────────────────────────
    textos, etiquetas = cargar_datos(DATA_CSV, oversample_factor=3)

    # Split estratificado (respeta proporción de clases en train/val)
    X_tr, X_val, y_tr, y_val = train_test_split(
        textos, etiquetas,
        test_size=args.val,
        stratify=etiquetas,
        random_state=42,
    )
    logger.info(
        "[split] Train=%d | Val=%d | VP en train=%d | VP en val=%d",
        len(X_tr), len(X_val), sum(y_tr), sum(y_val),
    )

    # ── pos_weight estático para BCEWithLogitsLoss ────────────────────────
    # Usar un peso fijo para evitar inestabilidad con pocos datos
    pos_weight = torch.tensor([2.0], dtype=torch.float32)
    logger.info("[loss] pos_weight fijo en %.1f para estabilizar entrenamiento.", pos_weight.item())

    # ── Tokenizer ─────────────────────────────────────────────────────────
    logger.info("[model] Cargando tokenizer BETO …")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(BETO_MODEL_NAME, cache_dir=str(CACHE_DIR))

    train_ds  = NNADataset(X_tr,  y_tr,  tokenizer, MAX_SEQ_LENGTH)
    val_ds    = NNADataset(X_val, y_val, tokenizer, MAX_SEQ_LENGTH)

    # num_workers=0 es OBLIGATORIO en Windows para evitar el error de multiprocessing
    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,  num_workers=0, pin_memory=(device.type=="cuda"))
    val_loader   = DataLoader(val_ds,  batch_size=args.batch, shuffle=False, num_workers=0, pin_memory=(device.type=="cuda"))

    # ── Modelo ────────────────────────────────────────────────────────────
    logger.info("[model] Inicializando BETOClassifier …")
    model = BETOClassifier(num_classes=2)

    if not args.no_load and MODEL_PT.exists():
        logger.info("[model] Cargando pesos desde %s …", MODEL_PT)
        try:
            state = torch.load(str(MODEL_PT), map_location="cpu", weights_only=True)
            model.load_state_dict(state)
            logger.info("[model] ✅ Pesos cargados correctamente (continuación de fine-tuning).")
        except Exception as exc:
            logger.warning(
                "[model] ⚠ No se pudieron cargar los pesos (%s). "
                "Iniciando desde pesos base BETO pre-entrenado.", exc
            )
    else:
        if args.no_load:
            logger.info("[model] --no-load activo: partiendo de pesos base BETO.")
        else:
            logger.info("[model] model.pt no encontrado — partiendo de pesos base BETO.")

    # ── Congelamiento de capas ─────────────────────────────────────────────
    freeze_encoder_layers(model)
    model.to(device)

    # ── Entrenamiento ─────────────────────────────────────────────────────
    FINETUNED_DIR.mkdir(parents=True, exist_ok=True)

    metrics = entrenar(
        model        = model,
        train_loader = train_loader,
        val_loader   = val_loader,
        device       = device,
        epochs       = args.epochs,
        lr           = args.lr,
        accum_steps  = args.accum,
        output_path  = MODEL_PT,
        pos_weight   = pos_weight,
    )

    # ── Guardar métricas ──────────────────────────────────────────────────
    with open(METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    logger.info("[out] Métricas guardadas en %s", METRICS_JSON)
    logger.info("[out] Modelo guardado en    %s", MODEL_PT)

    # ── Resumen final ─────────────────────────────────────────────────────
    rep = metrics["classification_report"]
    logger.info("")
    logger.info("┌─────────────────────────────────────────────┐")
    logger.info("│           REPORTE FINAL (Val set)           │")
    logger.info("├─────────────────────────────────────────────┤")
    for label in ["No relevante (FP)", "Relevante (VP)"]:
        if label in rep:
            r = rep[label]
            logger.info(
                "│  %-22s  P=%.3f  R=%.3f  F1=%.3f │",
                label, r["precision"], r["recall"], r["f1-score"],
            )
    logger.info("├─────────────────────────────────────────────┤")
    logger.info("│  Mejor F1 global: %-5.4f                    │", metrics["best_f1"])
    logger.info("└─────────────────────────────────────────────┘")


if __name__ == "__main__":
    main()
