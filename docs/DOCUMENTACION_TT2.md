# DOCUMENTACIÓN TT2 — Cambios Implementados

## Sistema Inteligente para la Identificación y Seguimiento de NNA
### Trabajo Terminal 2 — Objetivos Específicos OE-1 a OE-4

---

## Índice
1. [Resumen de Cambios](#1-resumen-de-cambios)
2. [OE-1: Detección Semántica con BETO](#2-oe-1-detección-semántica-con-beto)
3. [OE-2: Scraper Histórico 2023-2026](#3-oe-2-scraper-histórico-2023-2026)
4. [OE-3: Migración a PostgreSQL con FTS](#4-oe-3-migración-a-postgresql-con-fts)
5. [OE-4: Clustering Semántico con BERTopic](#5-oe-4-clustering-semántico-con-bertopic)
6. [Integración del Pipeline v5.0](#6-integración-del-pipeline-v50)
7. [Configuración y Despliegue](#7-configuración-y-despliegue)
8. [Mejoras Adicionales Sugeridas](#8-mejoras-adicionales-sugeridas)

---

## 1. Resumen de Cambios

### Archivos Nuevos (6)
| Archivo | OE | Descripción |
|---------|-----|-------------|
| `src/analysis/semantic_detector.py` | OE-1 | Detector semántico con BETO (861 líneas) |
| `src/collection/historical_scraper.py` | OE-2 | Scraper histórico 2023-2026 (974 líneas) |
| `src/database/models_noticias.py` | OE-3 | Modelos SQLAlchemy normalizados (272 líneas) |
| `src/database/repository.py` | OE-3 | Repositorio con FTS PostgreSQL (350+ líneas) |
| `src/database/__init__.py` | OE-3 | Init del módulo database |
| `src/analysis/bertopic_clustering.py` | OE-4 | Clustering BERTopic (550+ líneas) |

### Archivos Modificados (7)
| Archivo | Cambios |
|---------|---------|
| `src/analysis/analyzer.py` | Pasos 9-11 (BETO, BERTopic, PostgreSQL), pipeline v5.0 |
| `app/__init__.py` | Registro de modelos noticias, init FTS |
| `app/main/routes.py` | Dual CSV/PostgreSQL, FTS search, nuevos endpoints |
| `scheduler.py` | Comandos: historical, migrate_csv, analyze_basic |
| `requirements.txt` | +10 dependencias (torch, transformers, bertopic, etc.) |
| `Dockerfile` | PyTorch CPU, cache de modelos, build-essential |
| `docker-compose.yml` | Volumen models_cache, variables HF, dependencias |

### Dependencias Nuevas
```
torch>=2.1.0          # Backend de deep learning
transformers>=4.36.0  # Modelos Hugging Face (BETO)
sentence-transformers>=2.2.2  # Embeddings de frase
bertopic>=0.16.0      # Framework de topic modeling
hdbscan>=0.8.33       # Clustering basado en densidad
umap-learn>=0.5.5     # Reducción de dimensionalidad
feedparser>=6.0.0     # Parsing de RSS
plotly>=5.18.0        # Visualizaciones interactivas
tqdm>=4.66.0          # Barras de progreso
schedule>=1.2.0       # Planificación de tareas
```

---

## 2. OE-1: Detección Semántica con BETO

### Archivo: `src/analysis/semantic_detector.py`

### ¿Qué hace?
Reemplaza/complementa la detección heurística basada en keywords con un modelo de lenguaje pre-entrenado que **entiende el significado** del texto, no solo la presencia de palabras clave.

### Arquitectura

```
Texto (título + contenido)
        ↓
Tokenizer BETO (WordPiece, max_length=512)
        ↓
BETO Encoder (12 capas Transformer, 768-dim)
        ↓
[CLS] token → embedding 768-dim
        ↓
Clasificador binario (Linear 768→256→1 + Sigmoid)
        ↓
P(relevante) ∈ [0, 1]
```

### Modelo Base: BETO
- **Nombre:** `dccuchile/bert-base-spanish-wwm-cased`
- **Origen:** Universidad de Chile (DCC)
- **Parámetros:** 110M
- **Pre-entrenamiento:** Wikipedia en español + corpus OPUS
- **Tokenización:** WordPiece (WWM = Whole Word Masking)
- **¿Por qué BETO?** Es el mejor modelo BERT disponible para español. Fue entrenado específicamente con texto en español, a diferencia de mBERT (multilingual) que diluye su capacidad al cubrir 104 idiomas.

### Modos de Operación

#### 1. Zero-shot (sin entrenamiento)
```python
detector = SemanticDetector(mode="zero_shot")
result = detector.detect("Menor de 5 años queda huérfano tras feminicidio")
# → {'score': 0.89, 'label': 'relevante', 'confidence': 'alta'}
```

**¿Cómo funciona?**
1. Genera embedding del texto de entrada con BETO
2. Genera embeddings de descripciones de categorías:
   - "Noticia sobre feminicidio, violencia feminicida, asesinato de mujer..."
   - "Noticia genérica no relacionada con violencia de género..."
3. Calcula similitud coseno entre texto y cada categoría
4. Aplica softmax con temperatura para obtener probabilidad
5. Si similitud con categoría relevante > 0.5 → relevante

**Ventaja:** Funciona inmediatamente sin datos de entrenamiento.
**Limitación:** Menos preciso que fine-tuning (~85% vs ~95%).

#### 2. Fine-tuned (entrenamiento supervisado)
```python
detector = SemanticDetector(mode="finetuned")
detector.train(train_data, val_data, epochs=10)
```

**¿Cómo funciona?**
1. Usa noticias clasificadas por el sistema heurístico como datos de entrenamiento
2. Congela las primeras 8 capas de BETO (transfer learning)
3. Entrena las capas superiores + clasificador lineal
4. Optimizador: AdamW (weight decay regularization)
5. Scheduler: LinearLR (calentamiento + decay)
6. Early stopping: Para si val_loss no mejora en 3 épocas

**Dataset:** `NNANewsDataset` (hereda de `torch.utils.data.Dataset`)
- Input: texto tokenizado (input_ids, attention_mask)
- Output: label binario (0=no relevante, 1=relevante)

#### 3. Híbrido (combinación inteligente)
```python
hybrid = HybridScorer()
result = hybrid.combine(heuristic_score=0.65, semantic_score=0.82)
```

**¿Cómo funciona?**
- Combina score heurístico y semántico con peso α dinámico:
  ```
  score_final = α × semántico + (1-α) × heurístico
  ```
- α se ajusta según la confianza del modelo semántico:
  - Confianza alta (>0.8): α = 0.70 (confía más en BETO)
  - Confianza media (0.5-0.8): α = 0.50 (balance)
  - Confianza baja (<0.5): α = 0.30 (confía más en heurístico)

### Clases Principales

| Clase | Responsabilidad |
|-------|-----------------|
| `NNANewsDataset` | Dataset PyTorch para noticias etiquetadas |
| `BETOClassifier` | Red neuronal: BETO + Linear(768→256→1) |
| `SemanticDetector` | Orquestador de detección (zero-shot/finetuned) |
| `HybridScorer` | Combinación inteligente de scores con α dinámico |

### Integración en Pipeline
Se ejecuta como **Paso 9** del pipeline `SimplifiedNewsAnalyzer`:
```python
analyzer.run_complete_analysis(enable_semantic=True)
```

---

## 3. OE-2: Scraper Histórico 2023-2026

### Archivo: `src/collection/historical_scraper.py`

### ¿Qué hace?
Recolecta noticias históricas del período enero 2023 a diciembre 2026 usando múltiples estrategias de búsqueda retrospectiva para alcanzar ≥1,500 noticias históricas adicionales.

### Corrección aplicada
El documento original decía "2023-2025". Se corrigió a **2023-2026** como se solicitó.

### Estrategias de Recolección

#### 1. Google News Historical
```python
GoogleNewsHistorical.search(query, start_date, end_date)
```

**¿Cómo funciona?**
1. Construye URL de Google News con parámetros de fecha:
   ```
   https://news.google.com/rss/search?q={query}+after:{start}+before:{end}&hl=es-419&gl=MX
   ```
2. Parsea el RSS resultante con `feedparser`
3. Para cada artículo encontrado, usa `DynamicScraper` para extraer contenido completo
4. Aplica `score_relevance()` para filtrar por relevancia
5. Respeta delays de 15-30 segundos entre peticiones

**20 queries predefinidos:**
```python
HISTORICAL_QUERIES = [
    "feminicidio México menores",
    "feminicidio huérfanos hijos",
    "asesinato mujer hijos menores México",
    "violencia feminicida niños víctimas",
    "orfandad feminicidio México",
    # ... 15 más
]
```

#### 2. Wayback Machine (Internet Archive)
```python
WaybackHistorical.search(domain, start_date, end_date)
```

**¿Cómo funciona?**
1. Consulta el CDX API de Internet Archive:
   ```
   https://web.archive.org/cdx/search/cdx?url={domain}&from={start}&to={end}
   ```
2. Filtra solo respuestas HTTP 200 con content-type text/html
3. Construye URL de acceso al snapshot archivado
4. Extrae contenido con `BeautifulSoup`
5. Aplica scoring de relevancia

**9 dominios monitoreados:**
```python
WAYBACK_DOMAINS = [
    "jornada.com.mx", "proceso.com.mx", "animalpolitico.com",
    "eluniversal.com.mx", "milenio.com", "sinembargo.mx",
    "aristeguinoticias.com", "cimacnoticias.com.mx", "piedepagina.mx",
]
```

#### 3. Análisis de Series Temporales
```python
TimeSeriesAnalyzer.analyze(df)
```

**¿Cómo funciona?**
1. **Conteos temporales:** Agrupa noticias por mes/trimestre/año
2. **Media Móvil Simple (SMA):** Suaviza con ventana de 3 meses
   ```
   SMA(t) = (1/n) × Σ x(t-i) para i=0..n-1
   ```
3. **Detección de picos:** Usa Z-score para identificar meses con cobertura anormal
   ```
   Z(t) = (x(t) - μ) / σ
   ```
   Picos = meses donde |Z| > 1.5
4. **Estacionalidad:** Identifica el mes con mayor/menor cobertura promedio

### Clases Principales

| Clase | Responsabilidad |
|-------|-----------------|
| `GoogleNewsHistorical` | Búsqueda retrospectiva vía Google News RSS |
| `WaybackHistorical` | Recuperación de snapshots de Internet Archive |
| `TimeSeriesAnalyzer` | Análisis temporal con SMA y Z-score |
| `HistoricalCollector` | Orquestador con progreso persistible |

### Uso
```bash
python scheduler.py historical
```

---

## 4. OE-3: Migración a PostgreSQL con FTS

### Archivos: `src/database/models_noticias.py`, `src/database/repository.py`

### ¿Qué hace?
Migra el almacenamiento de noticias de archivos CSV a un esquema relacional normalizado en PostgreSQL con Full-Text Search (FTS), logrando búsquedas en <100ms.

### Esquema Relacional (4 tablas)

```
┌──────────────┐    ┌──────────────────┐
│   noticias    │───→│   detecciones    │
│ (artículos)   │    │ (scores/labels)  │
└──────┬───────┘    └──────────────────┘
       │
       │ M:1
┌──────┴───────┐    ┌──────────────────┐
│   clusters    │    │    entidades     │
│ (semánticos)  │    │ (NER extraídas)  │
└──────────────┘    └──────────────────┘
```

#### Tabla `noticias` (principal)
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL PK | ID auto-incremental |
| titulo | VARCHAR(500) | Título de la noticia |
| contenido | TEXT | Contenido completo |
| enlace | VARCHAR(2000) | URL (UNIQUE) |
| fuente | VARCHAR(300) | Medio de comunicación |
| fecha | TIMESTAMPTZ | Fecha de publicación |
| score_feminicidio | FLOAT | Score eje feminicidio |
| score_nna | FLOAT | Score eje NNA |
| score_compuesto | FLOAT | Score combinado heurístico |
| relevancia_final | FLOAT | Score final (heurístico + semántico) |
| score_semantico | FLOAT | Score BETO (OE-1) |
| clasificacion_final | VARCHAR(20) | Alta/Media/Baja/No relevante |
| cluster_id | INT FK | Cluster semántico (OE-4) |
| topic_id | INT | Topic BERTopic |
| content_hash | VARCHAR(64) | Hash MD5 para deduplicación |
| busqueda_fts | TSVECTOR | Vector FTS (generado) |

#### Tabla `detecciones` (auditoría)
Almacena scores heurístico, semántico e híbrido por separado para comparación y auditoría.

#### Tabla `clusters_semanticos`
Almacena clusters generados por BERTopic con etiquetas, términos c-TF-IDF, y cohesión.

#### Tabla `entidades`
Entidades NER extraídas (PER, LOC, ORG, MISC).

### Full-Text Search (FTS)

**¿Qué es FTS?**
Full-Text Search de PostgreSQL permite buscar texto natural de manera eficiente, con:
- **Stemming:** "feminicidios" y "feminicidio" son el mismo término
- **Stop words:** Ignora "el", "de", "la", etc.
- **Ranking:** Ordena resultados por relevancia del match
- **Pesos:** El título tiene 4x más peso que el contenido

**¿Cómo funciona?**

1. **tsvector:** Representación vectorizada del texto
   ```sql
   to_tsvector('spanish', 'feminicidio en Puebla')
   → 'feminicid':1 'puebl':3
   ```

2. **tsquery:** Query de búsqueda con operadores booleanos
   ```sql
   to_tsquery('spanish', 'feminicidio | asesinato')
   ```

3. **Operador @@:** Match entre tsvector y tsquery
   ```sql
   WHERE busqueda_fts @@ to_tsquery('spanish', 'feminicidio & menor')
   ```

4. **ts_rank:** Ranking por relevancia
   ```sql
   ORDER BY ts_rank(busqueda_fts, query) DESC
   ```

**Configuración personalizada:**
- `spanish_unaccent`: Combina stemming español + normalización de acentos
- Los títulos tienen peso 'A' (4x) y el contenido peso 'B' (1x)

### Índices para Rendimiento <100ms

| Índice | Tipo | Columna | Uso |
|--------|------|---------|-----|
| idx_noticias_fts | GIN | busqueda_fts | FTS en <10ms |
| idx_noticias_fecha | B-tree | fecha DESC | Ordenación cronológica |
| idx_noticias_score | B-tree | score_compuesto DESC | Top relevancia |
| idx_noticias_cluster | B-tree | cluster_id | Agrupación |
| idx_noticias_nna | B-tree parcial | score_nna (WHERE menores='Si') | Filtro NNA |
| idx_noticias_hash | Hash | content_hash | Deduplicación O(1) |

**¿Por qué GIN?**
Generalized Inverted Index — estructura de datos optimizada para tsvector que permite buscar en O(log n) en vez de O(n). Ideal para texto completo.

**¿Por qué B-tree?**
Balanced Tree — índice estándar para ordenación y comparaciones (=, <, >). Búsqueda en O(log n).

**¿Por qué Hash?**
Para deduplicación por content_hash donde solo necesitamos igualdad (=). O(1) amortizado.

### Trigger Automático
```sql
CREATE TRIGGER trg_noticias_fts
BEFORE INSERT OR UPDATE OF titulo, contenido
ON noticias
FOR EACH ROW
EXECUTE FUNCTION noticias_fts_trigger();
```
Cada vez que se inserta o actualiza una noticia, el tsvector se recalcula automáticamente.

### Patrón Dual CSV/PostgreSQL
El sistema mantiene **backward compatibility** con CSV:
- Si PostgreSQL tiene datos → usa FTS para búsquedas
- Si no → fallback a búsqueda con pandas
- Siempre guarda CSV como backup

### Uso
```bash
# Migrar CSV existente a PostgreSQL
python scheduler.py migrate_csv

# Las APIs automáticamente detectan PostgreSQL
# GET /api/search?q=feminicidio → FTS si hay datos en PG, sino CSV
```

---

## 5. OE-4: Clustering Semántico con BERTopic

### Archivo: `src/analysis/bertopic_clustering.py`

### ¿Qué hace?
Reemplaza K-Means con BERTopic para agrupar noticias por **similitud semántica** en vez de similitud léxica, y genera etiquetas automáticas para cada cluster.

### ¿Por qué BERTopic y no K-Means?

| Aspecto | K-Means (TT1) | BERTopic (TT2) |
|---------|---------------|-----------------|
| Representación | TF-IDF (frecuencia de palabras) | BETO embeddings (significado) |
| Número de clusters | Fijo (k parámetro) | Automático (HDBSCAN) |
| Manejo de ruido | No (todos se asignan) | Sí (outliers = -1) |
| Etiquetas | Manual | Automáticas (c-TF-IDF) |
| Sinónimos | No los detecta | Sí (embeddings semánticos) |

### Pipeline BERTopic

```
1. EMBEDDINGS (sentence-transformers)
   └── paraphrase-multilingual-MiniLM-L12-v2 (384-dim)
       
2. UMAP (Reducción de dimensionalidad)
   └── 768D/384D → 5D (preserva topología)
       
3. HDBSCAN (Clustering jerárquico)
   └── Encuentra clusters de densidad variable
       
4. c-TF-IDF (Representación por cluster)
   └── Identifica términos característicos
       
5. KeyBERTInspired (Etiquetado)
   └── Genera etiquetas semánticas automáticas
```

### Algoritmos Explicados

#### UMAP (Uniform Manifold Approximation and Projection)
- **Referencia:** McInnes, 2018
- **Qué hace:** Proyecta vectores 768D → 5D
- **¿Cómo?** Construye un grafo de vecinos cercanos en el espacio original, luego optimiza una proyección a baja dimensionalidad que preserve las distancias locales del grafo
- **Parámetros:**
  - `n_components=5`: 5 dimensiones de salida
  - `n_neighbors=15`: Cada punto considera sus 15 vecinos más cercanos
  - `min_dist=0.0`: Permite clusters muy compactos (mejor para HDBSCAN)
  - `metric='cosine'`: Distancia coseno (apropiada para embeddings)
- **¿Por qué no PCA/t-SNE?** UMAP preserva estructura global y local, es más rápido que t-SNE, y produce proyecciones más estables para clustering downstream

#### HDBSCAN (Hierarchical DBSCAN)
- **Referencia:** Campello et al., 2013
- **Qué hace:** Agrupa puntos por densidad, sin especificar el número de clusters
- **¿Cómo?**
  1. Construye un árbol de spanning mínimo ponderado por distancia
  2. Elimina aristas en orden descendente de peso (creando componentes)
  3. Aplica el criterio "Excess of Mass" para seleccionar los clusters más estables
  4. Los puntos que no caen en ningún cluster estable = outliers (-1)
- **Parámetros:**
  - `min_cluster_size=8`: Un cluster necesita al menos 8 documentos
  - `min_samples=5`: Un punto core necesita 5 vecinos dentro de ε
  - `cluster_selection_method='eom'`: Excess of Mass (más estable que 'leaf')
  - `prediction_data=True`: Guarda datos para reducción de outliers

#### c-TF-IDF (Class-based TF-IDF)
- **Referencia:** Grootendorst, 2022
- **Qué hace:** Identifica las palabras más representativas de cada cluster
- **¿Cómo?** Trata cada cluster como un "super-documento" y aplica TF-IDF a nivel de clase:
  ```
  c-TF-IDF(t, c) = tf(t, c) × log(1 + A / tf(t))
  ```
  Donde `tf(t, c)` = frecuencia del término t en el cluster c, y `A` = promedio de palabras por clase

### Reducción de Outliers (81.4% → 50-60%)

El problema: HDBSCAN es conservador y marca muchos documentos como outliers (-1) cuando los datos son ruidosos.

**Estrategia multi-etapa:**

1. **Etapa 1 — Probabilidades:** Usa las probabilidades soft de HDBSCAN. Si un outlier tiene >5% de probabilidad de pertenecer a un cluster → reasignar.

2. **Etapa 2 — Distribuciones:** Calcula la distribución c-TF-IDF del outlier y lo asigna al cluster con distribución más similar.

3. **Etapa 3 — Embeddings:** Calcula distancia coseno entre el embedding del outlier y el centroide de cada cluster. Reasigna si similitud > 0.3.

Cada etapa se aplica secuencialmente; la siguiente solo procesa los outliers restantes.

### Parámetros Clave
```python
HDBSCAN_MIN_CLUSTER_SIZE = 8   # Más bajo = más clusters, menos outliers
HDBSCAN_MIN_SAMPLES = 5        # Densidad requerida
UMAP_N_COMPONENTS = 5          # Dimensiones reducidas
UMAP_N_NEIGHBORS = 15          # Balance local/global
OUTLIER_TARGET_PERCENT = 0.55  # Objetivo: máximo 55% outliers
```

### Visualizaciones Generadas
- `data/cluster_topic_map.html`: Mapa 2D de distancias inter-topic
- `data/cluster_barchart.html`: Términos más relevantes por topic
- `data/cluster_hierarchy.html`: Dendrograma de jerarquía de topics

---

## 6. Integración del Pipeline v5.0

### Pipeline Completo (11 pasos)

```
┌─────────────────────────────────────────────────────┐
│  PIPELINE v5.0 — TT2 SEMÁNTICO                     │
│                                                     │
│  Pasos 1-8: Pipeline original (TT1)                 │
│  ├── 1. Recolección RSS + scoring dual              │
│  ├── 2. Almacenamiento CSV inicial                  │
│  ├── 3. TF-IDF (domain-boosted)                     │
│  ├── 4. LDA (topic modeling)                        │
│  ├── 5. K-Means (clustering fallback)               │
│  ├── 6. Similitud coseno + deduplicación            │
│  ├── 7. Reclasificación TF-IDF                      │
│  └── 8. Búsqueda con sinónimos                      │
│                                                     │
│  Pasos 9-11: Nuevos (TT2)                           │
│  ├── 9.  Detección semántica BETO    (OE-1)         │
│  ├── 10. Clustering BERTopic         (OE-4)         │
│  └── 11. Persistencia PostgreSQL     (OE-3)         │
└─────────────────────────────────────────────────────┘
```

### Modos de Ejecución

```python
# Pipeline completo (TT2)
analyzer.run_complete_analysis(
    enable_semantic=True,    # BETO detector
    enable_bertopic=True,    # BERTopic clustering
    enable_postgres=True,    # PostgreSQL FTS
)

# Pipeline básico (TT1 compatible, sin GPU)
analyzer.run_complete_analysis(
    enable_semantic=False,
    enable_bertopic=False,
    enable_postgres=True,
)
```

### API REST Actualizada

| Endpoint | Cambio |
|----------|--------|
| `GET /api/stats` | Usa PostgreSQL si disponible, fallback CSV |
| `GET /api/noticias` | Paginación PostgreSQL, fallback CSV |
| `GET /api/search?q=X` | FTS con ts_rank si PG, sino sinónimos CSV |
| `GET /api/analyze` | Acepta `?semantic=true&bertopic=true&postgres=true` |

### Scheduler (CLI)

```bash
python scheduler.py schedule     # Planificador automático
python scheduler.py collect      # Solo recolección RSS
python scheduler.py analyze      # Análisis completo v5.0
python scheduler.py analyze_basic # Sin BETO/BERTopic
python scheduler.py full         # Ciclo completo
python scheduler.py historical   # Recolección 2023-2026 (OE-2)
python scheduler.py migrate_csv  # CSV → PostgreSQL (OE-3)
```

---

## 7. Configuración y Despliegue

### Docker

```bash
# Construir y arrancar
docker-compose up --build -d

# Migrar datos existentes
docker-compose exec nna-webapp python scheduler.py migrate_csv

# Ejecutar recolección histórica
docker-compose exec nna-analyzer python scheduler.py historical

# Ejecutar análisis completo
docker-compose exec nna-analyzer python scheduler.py analyze
```

### Variables de Entorno Nuevas
```env
TRANSFORMERS_CACHE=/app/models/cache   # Cache de modelos HF
HF_HOME=/app/models/cache              # Home de Hugging Face
MODELS_DIR=/app/models                 # Directorio de modelos
```

### Volúmenes Docker Nuevos
```yaml
models_cache:  # Persistir modelos descargados entre reinicios
  driver: local
```

---

## 8. Mejoras Adicionales Sugeridas

### Implementadas
1. **Patrón Repository** para acceso a datos (separación de responsabilidades)
2. **Dual CSV/PostgreSQL** con detección automática
3. **Trigger automático** para actualización de tsvector
4. **Fallback gracioso** en cada paso (usa el anterior si el nuevo falla)
5. **Caché de modelos** compartida entre contenedores Docker
6. **Scheduler actualizado** con comandos para todas las operaciones TT2

### Sugerencias para Futuro
1. **NER con spaCy/Stanza:** Extraer entidades nombradas (víctimas, ubicaciones, edades) de cada noticia y almacenar en tabla `entidades`
2. **Dashboard de clusters:** Visualización interactiva de los clusters BERTopic en el dashboard web
3. **API de series temporales:** Endpoint `/api/temporal` para consultar tendencias y picos de cobertura
4. **Fine-tuning activo:** Interfaz para que el usuario marque noticias como relevantes/no relevantes y re-entrene el modelo BETO
5. **GPU en Docker:** Si se dispone de GPU, cambiar la imagen base a `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime` para acelerar 10-50x la inferencia
6. **Alertas en tiempo real:** Webhooks o notificaciones cuando se detecta un caso nuevo de alta relevancia
7. **Exportación de reportes:** Generar PDFs/Excel con estadísticas temporales para presentación académica

---

*Documento generado como parte de TT2 — Sistema Inteligente para la Identificación y Seguimiento de NNA*
