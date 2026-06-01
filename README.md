# NNA Monitor — Sistema Inteligente para la Identificación y Seguimiento de NNA en Situación de Orfandad por Feminicidio

**Trabajo Terminal 2026-A135 · ESCOM-IPN · Junio 2026**

Sistema de monitoreo de medios periodísticos que automatiza la detección de casos de Niñas, Niños y Adolescentes (NNA) en situación de orfandad por feminicidio en México. Combina web scraping con evasión de WAF, clasificación semántica basada en BETO y un módulo de investigación profunda con IA generativa.

---

## El problema

México registró más de 8,000 feminicidios entre 2010 y 2023 (SESNSP). Detrás de cada caso hay NNA que quedan en situación de orfandad repentina — la REDIM estima al menos 3,500 menores en esa condición. No existe un registro nacional. La información está dispersa en miles de notas de medios locales que ningún equipo humano puede auditar de forma concurrente.

Este sistema automatiza ese proceso.

---

## Arquitectura del pipeline

```
45 RSS + Google News
+ StealthSession (WAF bypass)
        │
        ▼
Deduplicación en cascada (4 fases)
MD5 → Jaccard → SimHash → TF-IDF coseno
        │
        ▼
Clasificación escalonada BETO
  Capa 0: Escudo léxico (frozenset, O(1))
  Capa 1: Escudo suave (penalización -0.35)
  Capa 2: BETO fine-tuned (bert-base-spanish-wwm-cased)
  Capa 3: Post-filtro de validación (regex VP/FP)
        │
        ▼
BERTopic (UMAP + HDBSCAN + c-TF-IDF)
        │
        ▼
PostgreSQL 16 (ACID, FTS con índices GIN)
        │
        ▼
Dashboard Flask + DeepInvestigator (Gemini Flash)
```

---

## Stack tecnológico

| Capa | Tecnologías |
|---|---|
| Recolección | Python 3.12, `cloudscraper`, BeautifulSoup4, feedparser |
| NLP / ML | PyTorch, HuggingFace Transformers, BETO, BERTopic, scikit-learn |
| Base de datos | PostgreSQL 16 con `tsvector` + índices GIN |
| Backend | Flask 3.0, SQLAlchemy, Flask-Login, Argon2id |
| IA generativa | Google Gemini Flash (`google-genai`) |
| Infraestructura | Docker Compose (3 servicios: db / analyzer / webapp) |

---

## Instalación

**Requisitos:** Docker + Docker Compose.

```bash
git clone <repo>
cd <repo>

# Copiar y configurar variables de entorno
cp .env.example .env
# Editar .env: POSTGRES_PASSWORD, SECRET_KEY, GEMINI_API_KEY

# Levantar todos los servicios
docker compose up --build
```

Acceder en `http://localhost:5000`.

**Credenciales por defecto:** `admin` / `Admin_NNA_2026!` (cambiar en primer uso).

### Desarrollo local (sin Docker)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Con PostgreSQL local corriendo:
python wsgi.py                 # Servidor web
python scheduler.py full       # Recolección + análisis
```

---

## Módulos principales

### `src/collection/`
- **`collector.py`** — Orquesta la recolección desde 45 feeds RSS y Google News.
- **`scraper.py`** — `StealthSession`: evasión de WAF con emulación de fingerprint TLS (JA3), delays log-normal y Circuit Breaker por dominio.

### `src/analysis/`
- **`semantic_detector.py`** — Clasificador BETO escalonado. Modos: `fine-tuned` (producción) y `zero_shot` (fallback). Configurable via `DETECTOR_MODE` en el entorno.
- **`dedup.py`** — Deduplicación en cascada: hash MD5, Jaccard ≥ 0.70, SimHash (Hamming ≤ 6), TF-IDF coseno ≥ 0.85.
- **`bertopic_clustering.py`** — Agrupamiento semántico: BETO embeddings → UMAP (768D → 5D) → HDBSCAN → c-TF-IDF.
- **`investigator.py`** — `DeepInvestigator`: genera query con Gemini, busca en DuckDuckGo, extrae contenido y sintetiza ficha de caso en JSON.
- **`evaluate_classifier.py`** — Evaluación formal: calcula Kappa de Cohen, Precisión, Recall, F1 y Matriz de Confusión sobre un conjunto de prueba etiquetado. Exporta tablas LaTeX.

### `app/`
- Dashboard Flask con filtros por clasificación, Full-Text Search en español, exportación CSV y panel de administración.

---

## Resultados del prototipo 4

| Métrica | TT1 (P2) | Meta TT2 | Resultado P4 |
|---|---|---|---|
| Fuentes monitoreadas | 10 RSS | 45 RSS | 45 RSS + Google News + Stealth |
| Noticias únicas por ciclo | 281 | > 500 | **634** |
| Tasa de falsos positivos | 60% | < 30% | ~20%* |
| Motor de clasificación | RegEx (72 patrones) | BETO fine-tuned | BETO escalonado v7.1 |
| Persistencia | CSV | PostgreSQL | PostgreSQL 16 (ACID) |
| Casos Alta relevancia detectados | — | — | **27** (4.4% del corpus) |

> \* Observación operativa sobre el corpus de producción. Métricas formales (Precisión, Recall, F1, κ de Cohen) sobre conjunto de prueba etiquetado documentadas en el Capítulo 8 del documento técnico.

---

## Evaluación formal del clasificador

El script `src/analysis/evaluate_classifier.py` calcula métricas sobre un conjunto de prueba etiquetado por dos anotadores independientes:

```bash
# Formato del CSV: id_noticia, titulo, contenido, label_a1, label_a2
python -m src.analysis.evaluate_classifier --test_csv test_labels.csv
```

Salida: Kappa de Cohen inter-anotador, Precisión, Recall, F1, Matriz de Confusión y archivo `.tex` con tablas LaTeX listas para el documento técnico.

---

## Comandos útiles

```bash
# Solo recolección
python scheduler.py collect

# Solo análisis semántico
python scheduler.py analyze

# Ciclo completo
python scheduler.py full

# Logs de los contenedores
docker compose logs -f nna-webapp
docker compose logs -f nna-analyzer

# Reset completo (elimina volúmenes y datos)
docker compose down --volumes && docker compose up --build -d
```

---

## Fuentes monitoreadas (~45)

Incluye: La Jornada, Proceso, Aristegui Noticias, Animal Político, Sin Embargo, El Universal, Milenio, Pie de Página, Contralínea, CIMAC Noticias, Luchadoras, medios regionales (Noroeste, El Debate, Informador), y 14 queries específicas a Google News sobre feminicidio, orfandad y NNA.

---

## Contexto académico

Proyecto desarrollado como Trabajo Terminal en la Escuela Superior de Cómputo (ESCOM) del Instituto Politécnico Nacional (IPN) bajo el protocolo 2026-A135. El documento técnico completo incluye marco teórico, arquitectura del sistema, metodología de desarrollo y evaluación formal de resultados.

---

*Este sistema procesa exclusivamente información periodística de acceso público. No almacena ni procesa datos de identidad de NNA. Diseñado bajo los principios de la LGDNNA y el interés superior de la niñez.*
