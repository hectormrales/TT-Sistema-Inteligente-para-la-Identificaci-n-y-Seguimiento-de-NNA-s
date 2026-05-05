# Sistema Inteligente para Identificación y Seguimiento de NNA

## Descripción

Sistema automatizado para detectar y analizar noticias sobre **feminicidios** que mencionen **víctimas indirectas (Niños, Niñas y Adolescentes — NNA)** en medios digitales mexicanos, utilizando Machine Learning y procesamiento de lenguaje natural.

El sistema recopila noticias de múltiples fuentes (RSS + web scraping dinámico + Google Search), aplica un **scoring de relevancia de 4 ejes** (feminicidio, NNA, caso individual, víctima indirecta), **deduplica** automáticamente noticias de diferentes sitios, filtra ruidos estadísticos, y presenta los resultados en un dashboard interactivo con gestión de fuentes.

---

## Cambios v6.0 — Precisión Extrema + Rendimiento (Batch Inference)

### Nuevas funcionalidades

| Funcionalidad | Descripción |
|---------------|-------------|
| **Scoring de 4 Ejes** | Se pasó de un scoring dual a uno de 4 ejes: Feminicidio, NNA (general), Caso Individual y **Víctima Indirecta** (orfandad/desamparo). |
| **Batch Inference (BETO)** | Procesamiento de análisis semántico en lotes (mini-batches) de 16 usando PyTorch. Reducción de tiempo de análisis de **60 min a < 3 min**. |
| **Penalización Estricta** | El sistema ahora descarta automáticamente casos donde el menor es la víctima directa, el agresor, o si es ruido estadístico/político. |
| **Google Search Scraper** | Integración de `StealthSession` para capturar menciones en redes sociales y medios que no tienen RSS, con rotación de User-Agents. |
| **Clasificación Estricta** | La relevancia "Alta" ahora exige cumplimiento simultáneo de los 4 ejes + validación semántica de BETO (>0.50). |

---

## Cambios v4.0 — Web Scraping Dinámico + Deduplicación + Gestión de Fuentes

### Nuevas funcionalidades

| Funcionalidad | Descripción |
|---------------|-------------|
| **Web Scraping Dinámico** | El sistema detecta automáticamente el tipo de cada fuente (RSS, HTML, Sitemap) leyendo `robots.txt` y adaptando la técnica de extracción. Respeta `Crawl-delay` y aplica rate limiting por dominio. |
| **Deduplicación Cross-Site** | Pipeline de 4 fases: hash exacto de título → Jaccard de títulos (≥0.70) → SimHash de contenido (Hamming ≤8) → TF-IDF cosine similarity (≥0.80). Elimina noticias repetidas entre diferentes medios. |
| **Gestión de Fuentes (UI)** | Nueva página `/fuentes` donde se pueden agregar, editar, probar, activar/desactivar y eliminar fuentes de noticias. Cada fuente se guarda en PostgreSQL. |
| **Sondeo de URL** | Botón "Sondear" que analiza una URL antes de agregarla: verifica robots.txt, detecta feeds RSS automáticamente, muestra crawl delay y tipo recomendado. |
| **Prueba de Fuente** | Botón "Probar" que ejecuta el scraping real de una fuente y muestra artículos de muestra para verificar que funciona correctamente. |
| **Mayor volumen** | ~45 feeds RSS (31 medios + 14 queries Google News) + fuentes dinámicas ilimitadas desde la UI. |

### Archivos nuevos

| Archivo | Propósito |
|---------|-----------|
| `src/collection/scraper.py` | Scraper dinámico: `RobotsChecker` + `DynamicScraper` — sondeo, rate limiting, extracción HTML/RSS/Sitemap |
| `src/analysis/dedup.py` | `NewsDeduplicator` — deduplicación en cascada (hash, Jaccard, SimHash, TF-IDF cosine) |
| `app/sources/__init__.py` | Blueprint de gestión de fuentes |
| `app/sources/routes.py` | API REST completa (CRUD + probe + test) para fuentes |
| `app/templates/sources.html` | Interfaz de gestión de fuentes con Bootstrap 5 |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `config.py` | ~45 RSS feeds (de 22 a ~45). 13 medios nuevos + 8 queries Google News adicionales. Medios regionales y especializados en DDHH. |
| `collector.py` | Integración con `DynamicScraper` y `NewsDeduplicator`. `collect_all_news()` scrapea fuentes de la DB además de las estáticas. Actualiza estado de fuentes en DB tras cada scraping. |
| `analyzer.py` | Paso 6 incluye deduplicación semántica post-clustering. Versión actualizada a v4.0. |
| `scheduler.py` | `collect_news()` usa `NewsDeduplicator` en vez de `drop_duplicates()` simple. |
| `app/models.py` | Nuevo modelo `NewsSource` (id, name, url, source_type, is_active, last_scraped, last_status, crawl_delay, etc.). |
| `app/__init__.py` | Registra `sources_bp` blueprint. |
| `app/templates/dashboard.html` | Botón "Fuentes" en el header que lleva a `/fuentes`. |

---

## Cambios v3.0 — Scoring de Relevancia Dual

### Problema resuelto

La versión anterior no filtraba por tema; recolectaba TODAS las noticias sin importar si hablaban de feminicidios o NNA.

### Resumen de cambios v3.0

- **Scoring dual heurístico** con ~35 patrones regex ponderados (eje feminicidio + eje NNA).
- **Reclasificación TF-IDF** con documento ideal (60% heurístico + 40% TF-IDF).
- **Diccionario ampliado** a 200+ sinónimos en 8 categorías.
- **Dashboard mejorado** con badges de relevancia y filtros por clasificación.

---

## Arquitectura del Sistema

```
┌──────────────────────────────────────────────────────────────┐
│                    FUENTES DE DATOS                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐   │
│  │ RSS (31) │  │ Google   │  │ HTML     │  │ Google     │   │
│  │ Feeds    │  │ News (14)│  │ Scraping │  │ Search     │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘   │
│       └──────────────┴──────────────┴───────────────┘         │
│                           │                                  │
│                    robots.txt check                          │
│                    rate limiting + StealthSession            │
└──────────────────────────┬───────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │    SCORING 4 EJES       │
              │  1. Feminicidio         │
              │  2. NNA (General)       │
              │  3. Caso Individual     │
              │  4. Víctima Indirecta   │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   DEDUPLICACIÓN (4fx)   │
              │  1. Hash exacto título  │
              │  2. Jaccard ≥ 0.70      │
              │  3. SimHash (H ≤ 8)     │
              │  4. TF-IDF cosine ≥0.80 │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │    PIPELINE NLP v6.0    │
              │  Batch Inference (BETO) │
              │  TF-IDF (domain-boost)  │
              │  BERTopic (Clustering)  │
              │  Cosine Similarity      │
              │  Rescore Heurístico     │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │     DASHBOARD           │
              │  Stats · Filtros        │
              │  Búsqueda + sinónimos   │
              │  Métricas 4 ejes        │
              └─────────────────────────┘
```

---

## Tecnologías

| Categoría | Tecnología |
|-----------|------------|
| Backend | Python 3.12, Flask 3.0.3 |
| Base de Datos | PostgreSQL 16 (Docker) |
| ML/NLP | scikit-learn 1.4.2, **PyTorch** (Batch Inference), **BETO** (Spanish BERT) |
| Scraping | BeautifulSoup4, lxml, requests, urllib.robotparser, **StealthSession** |
| Deduplicación | SimHash, Jaccard, TF-IDF coseno |
| Auth | Argon2id (OWASP), Flask-Login |
| Frontend | Bootstrap 5, Font Awesome 6, Chart.js |
| Deploy | Docker Compose (3 servicios) |

---

## Instalación

### Pre-requisitos
- Docker + Docker Compose
- Python 3.11+ (para desarrollo local)

### Con Docker (producción)
```bash
docker-compose up --build
```
Acceder a `http://localhost:5000` — usuario: `admin` / contraseña: `Admin_NNA_2026!`

### Desarrollo local
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Variables de entorno
export SECRET_KEY='tu-clave-secreta-aqui'
export POSTGRES_HOST='localhost'
export POSTGRES_PASSWORD='tu-password'

# Ejecutar
python wsgi.py             # App web
python scheduler.py full   # Recolección + análisis
```

---

## Estructura del Proyecto

```
├── app/
│   ├── __init__.py              # Factory: crea Flask app
│   ├── models.py                # User + NewsSource (SQLAlchemy)
│   ├── auth/                    # Blueprint autenticación
│   │   ├── forms.py
│   │   └── routes.py
│   ├── main/                    # Blueprint dashboard + API
│   │   └── routes.py
│   ├── sources/                 # Blueprint gestión de fuentes (v4.0)
│   │   └── routes.py
│   └── templates/
│       ├── dashboard.html       # Dashboard principal
│       ├── sources.html         # Gestión de fuentes (v4.0)
│       └── auth/
│           ├── login.html
│           └── register.html
├── src/
│   ├── collection/
│   │   ├── collector.py         # Recolección RSS + scoring dual
│   │   └── scraper.py           # Web scraping dinámico (v4.0)
│   └── analysis/
│       ├── analyzer.py          # Pipeline NLP (8 pasos)
│       ├── synonyms.py          # Diccionario 200+ sinónimos
│       └── dedup.py             # Deduplicación avanzada (v4.0)
├── data/                        # CSV, JSON (generados)
├── config.py                    # Configuración centralizada
├── scheduler.py                 # Servicio programado
├── wsgi.py                      # Punto de entrada web
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Dashboard principal |
| GET | `/fuentes/` | Gestión de fuentes |
| GET | `/api/stats` | Estadísticas resumidas |
| GET | `/api/noticias` | Listado paginado (filtros: `only_nna`, `clasificacion`) |
| GET | `/api/search?q=` | Búsqueda con sinónimos |
| GET | `/api/analyze` | Ejecuta pipeline completo |
| GET | `/api/export/csv` | Exporta datos |
| GET | `/health` | Health check |
| GET | `/fuentes/api/sources` | Lista fuentes |
| POST | `/fuentes/api/sources` | Agregar fuente |
| PUT | `/fuentes/api/sources/<id>` | Editar fuente |
| DELETE | `/fuentes/api/sources/<id>` | Eliminar fuente |
| POST | `/fuentes/api/sources/<id>/toggle` | Activar/desactivar |
| POST | `/fuentes/api/sources/<id>/test` | Probar fuente |
| POST | `/fuentes/api/sources/probe` | Sondear URL |

---

## Web Scraping Dinámico (v4.0)

El módulo `src/collection/scraper.py` implementa un scraping inteligente que se adapta a cada sitio:

1. **Lectura de robots.txt** — Verifica si el scraping está permitido usando `urllib.robotparser`. Si el sitio lo bloquea, la fuente se marca como "bloqueada".

2. **Detección automática del tipo de fuente:**
   - Si la URL contiene `/rss`, `/feed`, `.xml` → **RSS**
   - Si la página HTML tiene `<link rel="alternate" type="application/rss+xml">` → **RSS** (se extrae automáticamente el feed)
   - Si robots.txt declara sitemaps → **Sitemap**
   - Si no hay feed disponible → **HTML scraping** directo

3. **Extracción de contenido HTML:**
   - Prueba 16+ selectores CSS comunes (`article`, `.entry-content`, `.nota-body`, etc.)
   - Fallback a `meta[property="og:description"]`
   - Elimina scripts, ads, navigation antes de extraer texto

4. **Rate limiting:**
   - Respeta `Crawl-delay` de robots.txt
   - Default 1.5s entre requests al mismo dominio
   - Caché de robots.txt por dominio

---

## Deduplicación Cross-Site (v4.0)

El módulo `src/analysis/dedup.py` detecta noticias duplicadas o cuasi-duplicadas en cascada:

| Fase | Técnica | Complejidad | Descripción |
|------|---------|-------------|-------------|
| 1 | Hash MD5 de título | O(n) | Detecta títulos idénticos |
| 2 | Jaccard ≥ 0.70 | O(n²) | Detecta títulos similares |
| 3 | SimHash (Hamming ≤ 8) | O(n²) | Detecta contenido cuasi-idéntico |
| 4 | TF-IDF cosine ≥ 0.80 | O(n² × v) | Detecta parafraseo semántico |

Se conserva la noticia con mayor `score_compuesto` de cada grupo de duplicados.

---

## Algoritmos utilizados

| Algoritmo | Uso en el sistema |
|-----------|-------------------|
| **Scoring 4 Ejes** | Feminicidio, NNA, Caso Individual, Víctima Indirecta. Penalización de agresores/víctimas directas. |
| **Batch Inference (PyTorch)** | Vectorización masiva de noticias para análisis semántico (lotes de 16). |
| **BETO Zero-Shot** | Clasificación semántica profunda para validar la intención del texto. |
| **TF-IDF (domain-boosted)** | `sublinear_tf=True`, n-gramas 1-3, stop words español, vocabulario inyectado. |
| **BERTopic** | Modelado de tópicos latentes y clustering avanzado (reemplaza LDA/K-Means). |
| **SimHash + Jaccard** | Deduplicación eficiente cross-site. |
| **Cosine Similarity** | Detección de duplicados semánticos y relevancia temática. |
| **Expansión de sinónimos** | 200+ sinónimos en 8 categorías con ranking ponderado. |

---

## Fuentes RSS Monitoreadas (~45 fuentes)

**Medios generales (27):**
La Jornada (Política + Estados + Sociedad), Proceso, Aristegui Noticias, Animal Político, Sin Embargo, El Sol de México, El Financiero, El Universal, Milenio, Excélsior, Reporte Índigo, Pie de Página, Contralínea, SDP Noticias, El Debate, La Razón, El Heraldo, Informador, Zócalo, La Jornada de Oriente

**Medios especializados en género/DDHH (5):**
CIMAC Noticias, Luchadoras, El Economista, El País México, BBC Mundo México

**Medios regionales (4):**
El Sol de Toluca, El Sol de Puebla, Diario de Xalapa, Noroeste

**Google News queries específicas (14):**
feminicidio México, feminicidio hijos huérfanos, feminicidio niños niñas, orfandad feminicidio menores, víctimas indirectas feminicidio, feminicidio menores huérfanos, feminicidio hijos menores México, violencia feminicida niños, asesinato mujer hijos quedaron, alerta de género menores, orfandad violencia genero, DIF custodia feminicidio, violencia contra mujer menores huérfanos, feminicidio NNA víctimas indirectas

---

## Solución de Problemas

```bash
# Puerto 5000 ocupado → cambiar en docker-compose.yml
ports:
  - "5001:5000"

# Logs detallados
docker-compose logs nna-webapp
docker-compose logs nna-analyzer

# Reset completo
docker-compose down --volumes
docker-compose up --build -d

# Solo recolección manual
python scheduler.py collect

# Solo análisis manual
python scheduler.py analyze
```
