# Catálogo de Diagramas del Sistema Inteligente para la Identificación y Seguimiento de NNA

> Este documento lista todos los diagramas que se deben elaborar para la documentación del proyecto.  
> Los diagramas están organizados por categoría y cada uno incluye: descripción, contenido esperado e indicación de prioridad.

---

## Resumen rápido

| #  | Diagrama | Categoría | Prioridad |
|----|----------|-----------|-----------|
| 1  | Diagrama de Arquitectura General del Sistema | Arquitectura | Alta |
| 2  | Diagrama de Despliegue (Docker) | Arquitectura | Alta |
| 3  | Diagrama Entidad-Relación de la Base de Datos | Base de datos | Alta |
| 4  | Esquema Relacional (tablas con tipos) | Base de datos | Alta |
| 5  | Diagrama de Casos de Uso General | Comportamiento | Alta |
| 6  | Diagrama de Casos de Uso Detallado | Comportamiento | Alta |
| 7  | Diagrama de Flujo del Proceso de Recolección | Flujo de datos | Alta |
| 8  | Diagrama de Flujo del Proceso de Análisis (11 pasos) | Flujo de datos | Alta |
| 9  | Diagrama de Flujo de Clasificación Dual (Feminicidio × NNA) | Flujo de datos | Alta |
| 10 | Diagrama de Flujo de Deduplicación (4 técnicas en cascada) | Flujo de datos | Media |
| 11 | Diagrama de Componentes del Sistema | Arquitectura | Media |
| 12 | Diagrama de Secuencia — Iniciar Sesión (CU-01) | Comportamiento | Alta |
| 13 | Diagrama de Secuencia — Consultar Tablero (CU-03) | Comportamiento | Alta |
| 14 | Diagrama de Secuencia — Buscar Noticias (CU-04) | Comportamiento | Media |
| 15 | Diagrama de Secuencia — Gestionar Fuentes (CU-05) | Comportamiento | Media |
| 16 | Diagrama de Secuencia — Ejecución Automática del Análisis | Comportamiento | Alta |
| 17 | Diagrama de Estados — Ciclo de vida de una Noticia | Comportamiento | Alta |
| 18 | Diagrama de Estados — Sesión de Usuario | Comportamiento | Media |
| 19 | Diagrama de Navegación (Mapa de pantallas) | Interacción | Alta |
| 20 | Diagrama de Clases del Modelo de Datos (SQLAlchemy) | Diseño | Media |
| 21 | Diagrama de Paquetes / Módulos del Código | Diseño | Media |
| 22 | Diagrama de Flujo de Detección Semántica con BETO (OE-1) | Flujo de datos | Alta |
| 23 | Diagrama de Flujo de Agrupamiento Semántico con BERTopic (OE-4) | Flujo de datos | Alta |
| 24 | Diagrama de Flujo de Búsqueda con Texto Completo (FTS, OE-3) | Flujo de datos | Media |
| 25 | Diagrama de Actividades — Ciclo completo del sistema | Comportamiento | Alta |

---

## 1. Diagrama de Arquitectura General del Sistema

**Categoría:** Arquitectura  
**Prioridad:** Alta  
**Estilo de referencia:** Similar a `images/arquitectura.png`

**Descripción:**  
Vista de alto nivel que muestra los tres bloques principales del sistema y cómo se conectan entre sí.

**Contenido:**
```
┌──────────────────────────────────────────────────────────────┐
│                          Internet                            │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│   │La Jornada│ │ Proceso  │ │  CIMAC   │ │Google    │ ...   │
│   │   (RSS)  │ │  (RSS)   │ │  (RSS)   │ │News (RSS)│      │
│   └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘      │
│        └──────────┬──┴───────────┬┘            │             │
└───────────────────┼──────────────┼─────────────┘             │
                    ▼              ▼                            │
┌──────────────────────────────────────────────────────────────┐
│               MÓDULO DE RECOLECCIÓN                          │
│  ┌──────────────────┐  ┌──────────────────┐                  │
│  │ Recolector RSS   │  │ Raspador Web     │                  │
│  │ (collector.py)   │  │ (scraper.py)     │                  │
│  └────────┬─────────┘  └────────┬─────────┘                  │
│           └─────────┬───────────┘                            │
│                     ▼                                        │
│        ┌────────────────────────┐                            │
│        │ Filtro geográfico      │                            │
│        │ + Puntuación dual      │                            │
│        │ + Deduplicación        │                            │
│        └────────────┬───────────┘                            │
└─────────────────────┼────────────────────────────────────────┘
                      ▼
┌──────────────────────────────────────────────────────────────┐
│               MÓDULO DE ANÁLISIS (PLN)                       │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐  │
│  │TF-IDF  │ │  LDA   │ │K-Means │ │  BETO  │ │ BERTopic │  │
│  └────┬───┘ └───┬────┘ └───┬────┘ └───┬────┘ └────┬─────┘  │
│       └─────────┴──────────┴──────────┴────────────┘        │
└─────────────────────┼────────────────────────────────────────┘
                      ▼
┌──────────────────────────────────────────────────────────────┐
│                  BASE DE DATOS                               │
│        PostgreSQL 16 (FTS + Índices GIN)                     │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────┐     │
│  │ noticias │ │detecciones│ │  clústeres │ │entidades │     │
│  └──────────┘ └──────────┘ └────────────┘ └──────────┘     │
└─────────────────────┼────────────────────────────────────────┘
                      ▼
┌──────────────────────────────────────────────────────────────┐
│             APLICACIÓN WEB (Flask + Gunicorn)                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐     │
│  │  Tablero     │ │  Búsqueda    │ │ Gestión fuentes  │     │
│  │  (gráficas)  │ │  (FTS)       │ │ (CRUD)           │     │
│  └──────────────┘ └──────────────┘ └──────────────────┘     │
│                    API REST                                  │
└──────────────────────────────────────────────────────────────┘
                      ▼
              ┌───────────────┐
              │   Usuarios    │
              │  (Navegador)  │
              └───────────────┘
```

---

## 2. Diagrama de Despliegue (Docker)

**Categoría:** Arquitectura  
**Prioridad:** Alta

**Descripción:**  
Muestra los tres contenedores Docker, los volúmenes compartidos, la red interna y los puertos expuestos.

**Contenido esperado:**
- **Contenedor `nna-postgres`**: PostgreSQL 16-alpine, puerto 5432, volumen `pgdata`
- **Contenedor `nna-analyzer`**: Python 3.11, ejecuta `scheduler.py`, volúmenes: `./data`, `./logs`, `models_cache`
- **Contenedor `nna-webapp`**: Flask + Gunicorn, puerto 5000, 2 workers
- **Red**: `nna-network` (bridge)
- **Volúmenes**: `pgdata` (persistente), `models_cache` (caché de modelos Hugging Face)
- **Dependencias**: webapp → postgres (healthy), analyzer → postgres (healthy)

---

## 3. Diagrama Entidad-Relación de la Base de Datos

**Categoría:** Base de datos  
**Prioridad:** Alta  
**Estilo de referencia:** Similar a `images/modeloDelDominioDelProblema.png`

**Descripción:**  
Diagrama ER que muestra las 6 tablas del sistema con todas sus relaciones y cardinalidades.

**Entidades y relaciones:**

```
┌──────────────┐       1      ┌───────────────────┐
│   users      │──────────────│   news_sources     │
│              │   agrega     │                   │
│ • id (PK)    │              │ • id (PK)         │
│ • username   │              │ • name            │
│ • email      │              │ • url (UNIQUE)    │
│ • password   │              │ • source_type     │
│   _hash      │              │ • is_active       │
│ • is_active  │              │ • added_by (FK)   │
│ • is_admin   │              │ • articles_found  │
│ • created_at │              │ • last_scraped    │
│ • last_login │              └───────────────────┘
└──────────────┘

┌──────────────────────────────┐     N    ┌────────────────────────┐
│   noticias                   │──────────│   detecciones          │
│                              │  tiene   │                        │
│ • id (PK)                    │          │ • id (PK)              │
│ • titulo                     │          │ • noticia_id (FK)      │
│ • contenido                  │          │ • score_heuristico     │
│ • enlace (UNIQUE)            │          │ • score_semantico      │
│ • fuente                     │          │ • score_hibrido        │
│ • fecha                      │          │ • clasificacion        │
│ • score_feminicidio          │          │   _heuristica          │
│ • score_nna                  │          │ • clasificacion        │
│ • score_compuesto            │          │   _hibrida             │
│ • relevancia_final           │          │ • keywords_feminicidio │
│ • clasificacion              │          │ • keywords_nna         │
│ • clasificacion_final        │          │ • confianza_semantica  │
│ • score_semantico            │          │ • menores              │
│ • modo_deteccion             │          │   _identificados       │
│ • cluster_id (FK)            │          │ • edades_mencionadas   │
│ • topic_id                   │          └────────────────────────┘
│ • topic_description          │
│ • max_similarity             │     N    ┌────────────────────────┐
│ • content_hash               │──────────│   entidades            │
│ • scrape_method              │  contiene│                        │
│ • menores_identificados      │          │ • id (PK)              │
│ • busqueda_fts (TSVECTOR)    │          │ • noticia_id (FK)      │
│ • created_at                 │          │ • texto                │
│ • updated_at                 │          │ • tipo (PER|LOC|ORG)   │
└──────────────┬───────────────┘          │ • posicion_inicio      │
               │                          │ • posicion_fin         │
               │ N:1                      │ • confianza            │
               ▼                          └────────────────────────┘
┌──────────────────────────────┐
│   clusters_semanticos        │
│                              │
│ • id (PK)                    │
│ • etiqueta                   │
│ • descripcion                │
│ • terminos_principales (JSON)│
│ • num_documentos             │
│ • cohesion                   │
│ • es_outlier                 │
│ • modelo_version             │
└──────────────────────────────┘
```

**Relaciones:**
- `users` 1 → N `news_sources` (un usuario agrega muchas fuentes)
- `noticias` 1 → N `detecciones` (una noticia tiene varios registros de detección/auditoría)
- `noticias` 1 → N `entidades` (una noticia contiene varias entidades nombradas)
- `clusters_semanticos` 1 → N `noticias` (un clúster agrupa muchas noticias)

---

## 4. Esquema Relacional (tablas con tipos de dato)

**Categoría:** Base de datos  
**Prioridad:** Alta

**Descripción:**  
Diagrama tipo tabla con nombres de columnas, tipos de dato, claves primarias, claves foráneas e índices.  
Similar al ER pero en notación de esquema relacional con recuadros de tabla y líneas de relación.

**Notas adicionales:**  
Incluir los índices especiales:
- `idx_noticias_fts` — GIN sobre `busqueda_fts`
- `idx_noticias_fecha` — B-tree sobre `fecha DESC`
- `idx_noticias_score` — B-tree sobre `score_compuesto DESC`
- `idx_noticias_cluster` — B-tree sobre `cluster_id`
- `idx_noticias_hash` — Hash sobre `content_hash`

---

## 5. Diagrama de Casos de Uso General

**Categoría:** Comportamiento  
**Prioridad:** Alta  
**Estilo de referencia:** Similar a `images/casosDeUso.png`

**Descripción:**  
Diagrama UML de casos de uso mostrando los subsistemas y actores a nivel general.

**Actores:**
- **Analista** (usuario operativo)
- **Administrador del sistema** (hereda de Analista)
- **Sistema (Planificador)** — actor no humano (scheduler.py)

**Subsistemas (rectángulos):**

1. **Autenticación**
   - CU-01: Iniciar sesión
   - CU-02: Registrar usuario

2. **Consulta y Análisis**
   - CU-03: Consultar tablero de análisis
   - CU-04: Buscar noticias
   - CU-08: Exportar datos

3. **Gestión de Fuentes**
   - CU-05: Gestionar fuentes de noticias
   - CU-06: Agregar fuente de noticias
   - CU-07: Eliminar fuente de noticias

4. **Análisis Automático**
   - (Iniciado por el actor Sistema/Planificador)
   - Recolección automática de noticias
   - Análisis PLN automático

---

## 6. Diagrama de Casos de Uso Detallado

**Categoría:** Comportamiento  
**Prioridad:** Alta  
**Estilo de referencia:** Similar a `images/casosDeUsoDetalle.png`

**Descripción:**  
CU-01 a CU-08 con relaciones `«include»` y `«extend»` entre ellos.

**Relaciones:**
- CU-03 (Consultar tablero) `«include»` → CU-01 (Iniciar sesión) — requiere autenticación
- CU-04 (Buscar noticias) `«extend»` → CU-03 (Consultar tablero) — funcionalidad opcional desde tablero
- CU-05 (Gestionar fuentes) `«include»` → CU-01 — requiere autenticación
- CU-06 (Agregar fuente) `«extend»` → CU-05 — operación opcional dentro de gestión
- CU-07 (Eliminar fuente) `«extend»` → CU-05 — operación opcional dentro de gestión
- CU-08 (Exportar datos) `«extend»` → CU-03 — extensión del tablero

---

## 7. Diagrama de Flujo del Proceso de Recolección

**Categoría:** Flujo de datos  
**Prioridad:** Alta  
**Estilo de referencia:** Similar a `images/proceso1.png`, `images/proceso2.png`

**Descripción:**  
Diagrama de flujo que muestra todo el proceso de recolección de noticias que se ejecuta cada 6 horas.

**Pasos del flujo:**
```
[Inicio: Planificador activa cada 6h]
        │
        ▼
[Cargar lista de 54 fuentes RSS]
        │
        ▼
[Para cada fuente RSS] ──────────────────┐
        │                                 │
        ▼                                 │
[Descargar contenido del feed]            │
        │                                 │
        ▼                                 │
{¿URL ya procesada?} ──Sí──→ [Omitir]    │
        │ No                              │
        ▼                                 │
{¿Noticia de los últimos 30 días?}        │
        │ Sí           │ No → [Omitir]    │
        ▼                                 │
[Calcular puntuación dual]                │
  • Eje feminicidio (peso 55%)            │
  • Eje NNA (peso 45%)                    │
  • Bonificación cruzada                  │
        │                                 │
        ▼                                 │
{¿Puntuación ≥ 0.25?}                    │
        │ Sí           │ No → [Descartar] │
        ▼                                 │
[Filtro geográfico México]                │
  • 100+ indicadores México               │
  • 30+ indicadores exclusión             │
        │                                 │
        ▼                                 │
{¿Es noticia de México?}                 │
        │ Sí           │ No → [Descartar] │
        ▼                                 │
[Agregar a lote de noticias nuevas]       │
        │                                 │
        └──── [Siguiente fuente] ─────────┘
        │
        ▼
[Registrar URLs procesadas en seen_urls.json]
        │
        ▼
[Guardar lote en CSV y/o PostgreSQL]
        │
        ▼
[Fin: Registrar en bitácora]
```

---

## 8. Diagrama de Flujo del Proceso de Análisis (Flujo de 11 pasos)

**Categoría:** Flujo de datos  
**Prioridad:** Alta  
**Estilo de referencia:** Similar a `images/proceso1.png`

**Descripción:**  
Diagrama que muestra el flujo completo del proceso de análisis de PLN que se ejecuta cada 12 horas.

**Pasos del flujo:**

```
[Inicio: Planificador activa cada 12h]
        │
        ▼
[Paso 1: Vectorización TF-IDF]
  • 5000 características, n-gramas (1,3)
  • Aumento de dominio con términos clave
        │
        ▼
[Paso 2: Modelado de Tópicos con LDA]
  • 6 tópicos con 30 iteraciones
        │
        ▼
[Paso 3: Agrupamiento con K-Means]
  • 5 grupos, métrica Silhouette
        │
        ▼
[Paso 4: Similitud Coseno]
  • Matriz N×N, detección de duplicados
        │
        ▼
[Paso 5: Reclasificación TF-IDF]
  • Comparación con documento ideal
  • Combinación: 60% heurístico + 40% TF-IDF
        │
        ▼
[Paso 6: Expansión de Búsqueda con Sinónimos]
  • Diccionario: 143 términos en 8 categorías
        │
        ▼
[Paso 7: Detección Semántica con BETO (OE-1)]
  • Modelo BETO 110M parámetros
  • 3 modos: cero-disparo / ajustado / híbrido
  • α dinámico según confianza
        │
        ▼
[Paso 8: Agrupamiento Semántico BERTopic (OE-4)]
  • Incrustaciones → UMAP → HDBSCAN → c-TF-IDF
  • Reasignación de valores atípicos
        │
        ▼
[Paso 9: Persistencia en PostgreSQL (OE-3)]
  • Inserción por lotes + Disparadores FTS
  • Creación de índices
        │
        ▼
[Paso 10: Exportación a CSV]
  • Respaldo con metadatos de ejecución
        │
        ▼
[Paso 11: Generación de Visualizaciones]
  • Mapa de temas, Gráfico de barras, Dendrograma
        │
        ▼
[Fin: Registrar estadísticas en bitácora]
```

---

## 9. Diagrama de Flujo de Clasificación Dual (Feminicidio × NNA)

**Categoría:** Flujo de datos  
**Prioridad:** Alta

**Descripción:**  
Diagrama que detalla cómo se calcula la puntuación dual para determinar la relevancia de una noticia.

**Contenido:**

```
[Entrada: Título + Contenido de la noticia]
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
[Eje Feminicidio (55%)]           [Eje NNA (45%)]
  17 expresiones regulares          23 expresiones regulares
  ponderadas:                       ponderadas:
  • "feminicidio" = 1.0             • "huérfanos" = 1.0
  • "violencia feminicida" = 0.85   • "hijos de la víctima" = 0.95
  • "ex pareja" = 0.35              • "custodia" = 0.4
  Fórmula: Sigmoide suave           Fórmula: Sigmoide suave
        │                                  │
        ▼                                  ▼
[score_feminicidio]                [score_nna]
        │                                  │
        └──────────┬───────────────────────┘
                   ▼
        [Puntuación compuesta]
        score = 0.55 × fem + 0.45 × nna
                   │
                   ▼
        {¿Ambos ejes > 0.10?}
           │ Sí          │ No
           ▼             ▼
        [Bonificación   [Sin bonificación]
         ×1.35 a ×1.55]
                   │
                   ▼
        {¿Título menciona ambos?}
           │ Sí          │ No
           ▼             ▼
        [Bonificación   [Continuar]
         ×1.20]
                   │
                   ▼
        [Clasificación final]
        ≥ 0.45 → ALTA
        0.30–0.44 → MEDIA
        0.25–0.29 → BAJA
        < 0.25 → NO RELEVANTE
```

---

## 10. Diagrama de Flujo de Deduplicación (4 técnicas en cascada)

**Categoría:** Flujo de datos  
**Prioridad:** Media

**Descripción:**  
Muestra las 4 técnicas de deduplicación que se aplican en cascada.

**Flujo:**

```
[Entrada: Noticia candidata]
        │
        ▼
[Técnica 1: Hash MD5 exacto]
  hash = MD5(normalizar(título))
        │
        ▼
{¿Hash ya existe?} ──Sí──→ [DUPLICADO: Descartar]
        │ No
        ▼
[Técnica 2: Similitud Jaccard]
  similitud = |tokens_A ∩ tokens_B| / |tokens_A ∪ tokens_B|
        │
        ▼
{¿Similitud ≥ 0.70?} ──Sí──→ [DUPLICADO: Descartar]
        │ No
        ▼
[Técnica 3: SimHash]
  huella = simhash(título + contenido[:500])
        │
        ▼
{¿Distancia Hamming ≤ 8?} ──Sí──→ [DUPLICADO: Descartar]
        │ No
        ▼
[Técnica 4: Coseno TF-IDF]
  similitud = coseno(vec_A, vec_B)
        │
        ▼
{¿Similitud ≥ 0.85?} ──Sí──→ [DUPLICADO: Descartar]
        │ No
        ▼
[NOTICIA ÚNICA: Conservar]
```

---

## 11. Diagrama de Componentes del Sistema

**Categoría:** Arquitectura  
**Prioridad:** Media

**Descripción:**  
Diagrama UML de componentes mostrando los paquetes de código y sus dependencias.

**Componentes:**

```
┌─────────────────────────────────────────────────────────────┐
│                    «componente» Aplicación Web               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   auth/      │  │   main/      │  │   sources/       │  │
│  │ (rutas de    │  │ (tablero,    │  │ (gestión de      │  │
│  │ autenticación│  │  búsqueda,   │  │  fuentes RSS)    │  │
│  │ + formularios│  │  API REST)   │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │  models.py   │  │  templates/  │                        │
│  │ (User,       │  │ (HTML +      │                        │
│  │  NewsSource) │  │  Bootstrap)  │                        │
│  └──────────────┘  └──────────────┘                        │
└────────────────────────────┬────────────────────────────────┘
                             │ usa
                             ▼
┌─────────────────────────────────────────────────────────────┐
│             «componente» Motor de Análisis (PLN)             │
│  ┌──────────────────┐  ┌─────────────────────────────────┐  │
│  │ analyzer.py      │  │ semantic_detector.py (BETO)     │  │
│  │ (flujo de 11     │  │ (detección semántica, OE-1)     │  │
│  │  pasos)          │  │                                 │  │
│  └──────────────────┘  └─────────────────────────────────┘  │
│  ┌──────────────────┐  ┌─────────────────────────────────┐  │
│  │ bertopic_        │  │ dedup.py                        │  │
│  │ clustering.py    │  │ (4 técnicas de                  │  │
│  │ (BERTopic, OE-4) │  │  deduplicación)                │  │
│  └──────────────────┘  └─────────────────────────────────┘  │
│  ┌──────────────────┐                                       │
│  │ synonyms.py      │                                       │
│  │ (diccionario de  │                                       │
│  │  143 sinónimos)  │                                       │
│  └──────────────────┘                                       │
└────────────────────────────┬────────────────────────────────┘
                             │ usa
                             ▼
┌─────────────────────────────────────────────────────────────┐
│             «componente» Módulo de Recolección               │
│  ┌──────────────────┐  ┌─────────────────────────────────┐  │
│  │ collector.py     │  │ scraper.py                      │  │
│  │ (RSS + puntuación│  │ (raspado web dinámico,          │  │
│  │  dual + filtro)  │  │  anti-bloqueos)                 │  │
│  └──────────────────┘  └─────────────────────────────────┘  │
│  ┌──────────────────┐                                       │
│  │ historical_      │                                       │
│  │ scraper.py       │                                       │
│  │ (Google News     │                                       │
│  │  Histórico +     │                                       │
│  │  Wayback Machine)│                                       │
│  └──────────────────┘                                       │
└────────────────────────────┬────────────────────────────────┘
                             │ usa
                             ▼
┌─────────────────────────────────────────────────────────────┐
│           «componente» Capa de Persistencia                  │
│  ┌──────────────────┐  ┌─────────────────────────────────┐  │
│  │ models_           │  │ repository.py                   │  │
│  │ noticias.py      │  │ (patrón Repositorio,            │  │
│  │ (4 tablas        │  │  FTS, disparadores)             │  │
│  │  SQLAlchemy)     │  │                                 │  │
│  └──────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                             │ conecta
                             ▼
                   ┌───────────────────┐
                   │   PostgreSQL 16   │
                   │   (FTS + GIN)     │
                   └───────────────────┘
```

---

## 12. Diagrama de Secuencia — Iniciar Sesión (CU-01)

**Categoría:** Comportamiento  
**Prioridad:** Alta

**Actores/Objetos:** Usuario, Navegador, Flask (auth/routes), Modelo User, PostgreSQL

**Flujo:**
```
Usuario            Navegador         Flask(auth)       User Model        PostgreSQL
  │                    │                  │                 │                 │
  │──GET /login───────▶│                  │                 │                 │
  │                    │──GET /login──────▶│                 │                 │
  │                    │◀──IU-01 HTML─────│                 │                 │
  │◀──Mostrar form─────│                  │                 │                 │
  │                    │                  │                 │                 │
  │──Ingresa datos────▶│                  │                 │                 │
  │──Clic "Ingresar"──▶│                  │                 │                 │
  │                    │──POST /login─────▶│                 │                 │
  │                    │                  │──buscar_por─────▶│                 │
  │                    │                  │  _usuario()     │──SELECT────────▶│
  │                    │                  │                 │◀──resultado─────│
  │                    │                  │◀──objeto User───│                 │
  │                    │                  │                 │                 │
  │                    │                  │──verificar_     │                 │
  │                    │                  │  contraseña()   │                 │
  │                    │                  │  (Argon2id)     │                 │
  │                    │                  │                 │                 │
  │                    │                  │──login_user()   │                 │
  │                    │                  │──actualizar     │                 │
  │                    │                  │  last_login ────▶│──UPDATE────────▶│
  │                    │◀──Redirect /─────│                 │                 │
  │◀──IU-03 Tablero────│                  │                 │                 │
```

---

## 13. Diagrama de Secuencia — Consultar Tablero (CU-03)

**Categoría:** Comportamiento  
**Prioridad:** Alta

**Actores/Objetos:** Analista, Navegador, Flask (main/routes), Repositorio, PostgreSQL

**Flujo:**
```
Analista          Navegador         Flask(main)      Repositorio       PostgreSQL
  │                    │                │                │                │
  │──Accede a /───────▶│                │                │                │
  │                    │──GET /─────────▶│                │                │
  │                    │                │──obtener_      │                │
  │                    │                │  estadisticas()│                │
  │                    │                │───────────────▶│──SELECT COUNT──▶│
  │                    │                │                │◀──totales──────│
  │                    │                │◀──stats────────│                │
  │                    │                │                │                │
  │                    │                │──obtener_      │                │
  │                    │                │  noticias()    │                │
  │                    │                │───────────────▶│──SELECT * ─────▶│
  │                    │                │                │◀──noticias─────│
  │                    │                │◀──lista────────│                │
  │                    │                │                │                │
  │                    │◀──IU-03 HTML───│                │                │
  │                    │  + datos JSON  │                │                │
  │                    │  (Chart.js)    │                │                │
  │◀──Tablero con──────│                │                │                │
  │   gráficas         │                │                │                │
```

---

## 14. Diagrama de Secuencia — Buscar Noticias (CU-04)

**Categoría:** Comportamiento  
**Prioridad:** Media

**Flujo resumido:**
- El Analista escribe un término de búsqueda en IU-03
- Flask recibe la consulta vía `/api/search?q=...`
- El Repositorio expande la consulta con sinónimos (synonyms.py)
- Se ejecuta búsqueda FTS en PostgreSQL con `ts_rank()`
- Se devuelven resultados ordenados por relevancia

---

## 15. Diagrama de Secuencia — Gestionar Fuentes (CU-05)

**Categoría:** Comportamiento  
**Prioridad:** Media

**Flujo resumido:**
- El Administrador accede a `/sources` (IU-04)
- Flask consulta la lista de fuentes activas/inactivas
- Muestra tabla con nombre, URL, tipo, estado, última recolección
- Operaciones: Agregar nueva (CU-06), Activar/Desactivar, Eliminar (CU-07)

---

## 16. Diagrama de Secuencia — Ejecución Automática del Análisis

**Categoría:** Comportamiento  
**Prioridad:** Alta

**Actores/Objetos:** Planificador (scheduler.py), Recolector, Analizador, Detector Semántico, BERTopic, Repositorio, PostgreSQL

**Flujo:**
```
Planificador     Recolector      Analizador      BETO          BERTopic     Repositorio    PostgreSQL
     │               │               │              │               │            │              │
     │──cada 6h──────▶│               │              │               │            │              │
     │               │──recolectar()  │              │               │            │              │
     │               │  54 fuentes    │              │               │            │              │
     │               │──filtrar()     │              │               │            │              │
     │               │──deduplicar()  │              │               │            │              │
     │◀──CSV─────────│               │              │               │            │              │
     │               │               │              │               │            │              │
     │──cada 12h─────────────────────▶│              │               │            │              │
     │               │               │──TF-IDF()    │               │            │              │
     │               │               │──LDA()       │               │            │              │
     │               │               │──K-Means()   │               │            │              │
     │               │               │──coseno()    │               │            │              │
     │               │               │              │               │            │              │
     │               │               │──detectar()──▶│               │            │              │
     │               │               │◀──scores─────│               │            │              │
     │               │               │              │               │            │              │
     │               │               │──agrupar()───────────────────▶│            │              │
     │               │               │◀──clústeres──────────────────│            │              │
     │               │               │              │               │            │              │
     │               │               │──persistir()──────────────────────────────▶│──INSERT──────▶│
     │               │               │              │               │            │◀──OK─────────│
     │◀──resumen─────────────────────│              │               │            │              │
```

---

## 17. Diagrama de Estados — Ciclo de vida de una Noticia

**Categoría:** Comportamiento  
**Prioridad:** Alta  
**Estilo de referencia:** Similar a `images/edoPrestamo.png`

**Estados:**

```
                    ┌────────────────┐
                    │   Descubierta  │
                    │  (URL en feed) │
                    └───────┬────────┘
                            │ [URL nueva + reciente]
                            ▼
                    ┌────────────────┐
                    │  Pre-filtrada  │
                    │ (puntuación    │
                    │  dual)         │
                    └───────┬────────┘
                   ╱        │         ╲
          [< 0.25]         [≥ 0.25]    [no México]
              ▼             ▼              ▼
     ┌──────────┐  ┌────────────────┐  ┌──────────┐
     │Descartada│  │   Candidata    │  │Descartada│
     │(no relev)│  │ (pasa filtro   │  │(otro país│
     └──────────┘  │  geográfico)   │  └──────────┘
                   └───────┬────────┘
                           │ [pasa deduplicación]
                           ▼
                   ┌────────────────┐
                   │  Recolectada   │
                   │ (guardada en   │
                   │  CSV/BD)       │
                   └───────┬────────┘
                           │ [ciclo de análisis 12h]
                           ▼
                   ┌────────────────┐
                   │   Analizada    │
                   │ (TF-IDF, LDA,  │
                   │  K-Means)      │
                   └───────┬────────┘
                           │
                  ┌────────┴────────┐
                  ▼                 ▼
          ┌──────────────┐  ┌──────────────┐
          │  Clasificada │  │  Clasificada │
          │  Semántic.   │  │  Solo        │
          │  (BETO +     │  │  heurística  │
          │   híbrido)   │  │              │
          └──────┬───────┘  └──────┬───────┘
                 └────────┬────────┘
                          ▼
                 ┌────────────────┐
                 │   Agrupada     │
                 │ (BERTopic,     │
                 │  cluster_id)   │
                 └───────┬────────┘
                         │
                         ▼
                 ┌────────────────┐
                 │  Persistida    │
                 │ (PostgreSQL +  │
                 │  FTS indexada) │
                 └───────┬────────┘
                         │
                         ▼
                 ┌────────────────┐
                 │  Consultable   │
                 │ (visible en    │
                 │  tablero web)  │
                 └────────────────┘
```

---

## 18. Diagrama de Estados — Sesión de Usuario

**Categoría:** Comportamiento  
**Prioridad:** Media

**Estados:**
```
[Sin sesión] ──login exitoso──▶ [Sesión activa]
                                      │
                            ┌─────────┼──────────┐
                            │         │          │
                         [timeout  [logout   [cuenta
                          60 min]  manual]   desactivada]
                            │         │          │
                            ▼         ▼          ▼
                        [Sesión expirada]  [Sin sesión]
```

---

## 19. Diagrama de Navegación (Mapa de pantallas)

**Categoría:** Interacción  
**Prioridad:** Alta  
**Estilo de referencia:** Similar a `images/mapa.jpg`

**Contenido:**

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   ┌─────────────┐      éxito      ┌──────────────────┐      │
│   │  IU-01       │────────────────▶│  IU-03            │      │
│   │  Inicio de   │                 │  Tablero de      │      │
│   │  sesión      │                 │  análisis        │◀─┐   │
│   └──────┬───────┘                 │  • Estadísticas  │  │   │
│          │                         │  • Gráficas      │  │   │
│          │ "Registrarse"           │  • Lista noticias│  │   │
│          ▼                         │  • Búsqueda      │  │   │
│   ┌─────────────┐      éxito      │  • Exportar CSV  │  │   │
│   │  IU-02       │────────────────▶└────────┬─────────┘  │   │
│   │  Registro    │                          │            │   │
│   │  de usuario  │                "Fuentes" │    "Tablero│   │
│   └─────────────┘                          ▼            │   │
│                                    ┌──────────────────┐  │   │
│                                    │  IU-04            │  │   │
│                                    │  Gestión de      │──┘   │
│                                    │  fuentes         │      │
│                                    │  • Lista fuentes │      │
│                                    │  • Agregar nueva │      │
│                                    │  • Activar/Desact│      │
│                                    │  • Eliminar      │      │
│                                    └──────────────────┘      │
│                                                              │
│   Todas las pantallas: Barra superior con nombre del         │
│   sistema, usuario autenticado y botón "Cerrar sesión"       │
│   → Redirige a IU-01                                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 20. Diagrama de Clases del Modelo de Datos (SQLAlchemy)

**Categoría:** Diseño  
**Prioridad:** Media

**Descripción:**  
Diagrama UML de clases mostrando los modelos de SQLAlchemy con atributos y métodos.

**Clases principales:**
- `User` — atributos: id, username, email, password_hash, is_active, is_admin; métodos: set_password(), check_password(), get_id()
- `NewsSource` — atributos: id, name, url, source_type, is_active, added_by; relación con User
- `Noticia` — atributos: (ver tabla completa arriba); relación con ClusterSemantico, Deteccion, Entidad
- `Deteccion` — atributos: scores y clasificaciones
- `ClusterSemantico` — atributos: etiqueta, términos, cohesión
- `Entidad` — atributos: texto, tipo, posición, confianza

---

## 21. Diagrama de Paquetes / Módulos del Código

**Categoría:** Diseño  
**Prioridad:** Media

**Estructura:**

```
┌──────────────────────────────────────────────────┐
│                    Raíz del proyecto              │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌────────────────┐    ┌────────────────────┐    │
│  │   «paquete»    │    │    «paquete»       │    │
│  │     app/       │    │      src/          │    │
│  │  (Aplicación   │    │   (Lógica de       │    │
│  │   web Flask)   │    │    negocio)        │    │
│  ├────────────────┤    ├────────────────────┤    │
│  │  auth/         │    │  analysis/         │    │
│  │  main/         │    │  collection/       │    │
│  │  sources/      │    │  database/         │    │
│  │  templates/    │    │                    │    │
│  │  models.py     │    │                    │    │
│  └────────────────┘    └────────────────────┘    │
│                                                  │
│  ┌────────────────┐    ┌────────────────────┐    │
│  │  config.py     │    │  scheduler.py      │    │
│  │  (configuración│    │  (planificador     │    │
│  │   centralizada)│    │   APScheduler)     │    │
│  └────────────────┘    └────────────────────┘    │
│                                                  │
│  ┌────────────────┐    ┌────────────────────┐    │
│  │  wsgi.py       │    │  docker-compose    │    │
│  │  (punto de     │    │  .yml              │    │
│  │   entrada      │    │  (orquestación)    │    │
│  │   Gunicorn)    │    │                    │    │
│  └────────────────┘    └────────────────────┘    │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 22. Diagrama de Flujo de Detección Semántica con BETO (OE-1)

**Categoría:** Flujo de datos  
**Prioridad:** Alta

**Descripción:**  
Diagrama que muestra el proceso de detección semántica con el modelo BETO.

**Flujo:**

```
[Entrada: Texto de la noticia]
        │
        ▼
[Tokenización WordPiece]
  (máx. 512 tokens)
        │
        ▼
[BETO: 12 capas Transformer]
  110M parámetros
  Incrustaciones de 768 dimensiones
        │
        ▼
[Token [CLS] → Vector 768-dim]
        │
        ▼
[Abandono (0.3)]
        │
        ▼
[Capa Lineal: 768 → 256]
        │
        ▼
[Activación ReLU]
        │
        ▼
[Abandono (0.2)]
        │
        ▼
[Capa Lineal: 256 → 2]
        │
        ▼
[Softmax → P(relevante)]
        │
        ▼
{¿Modo de operación?}
        │
   ┌────┼────────────────┐
   │    │                 │
   ▼    ▼                 ▼
[Cero-   [Ajuste fino]  [Híbrido]
 disparo]                   │
   │       │                │
   │       │                ▼
   │       │        [Combinar con heurístico]
   │       │         α dinámico:
   │       │         • Confianza > 0.8 → α=0.70
   │       │         • Confianza 0.5-0.8 → α=0.50
   │       │         • Confianza < 0.5 → α=0.30
   │       │                │
   └───────┴────────────────┘
                │
                ▼
[score_semantico, modo_deteccion,
 clasificacion_final]
```

---

## 23. Diagrama de Flujo de Agrupamiento Semántico con BERTopic (OE-4)

**Categoría:** Flujo de datos  
**Prioridad:** Alta

**Flujo:**

```
[Entrada: Corpus de noticias analizadas]
        │
        ▼
[1. Generación de Incrustaciones]
  Modelo: paraphrase-multilingual-MiniLM-L12-v2
  Salida: vectores de 384 dimensiones por noticia
        │
        ▼
[2. Reducción de Dimensionalidad — UMAP]
  384 dims → 5 dims
  n_neighbors=15, min_dist=0.0
  métrica='coseno'
        │
        ▼
[3. Agrupamiento — HDBSCAN]
  min_cluster_size=8, min_samples=5
  Detección automática del número de grupos
        │
        ▼
{¿Documento asignado a grupo?}
   │ Sí                    │ No (valor atípico)
   ▼                       ▼
[Asignar topic_id]   [Reasignación multi-etapa]
                       │
                       ├─[Etapa 1: Probabilidades blandas]
                       │  P(grupo) ≥ 0.05 → reasignar
                       │
                       ├─[Etapa 2: Distribución c-TF-IDF]
                       │  Comparar con centroides
                       │
                       └─[Etapa 3: Incrustaciones]
                          Distancia coseno vs centroides
                              │
                              ▼
                       {¿Se pudo reasignar?}
                        │ Sí          │ No
                        ▼             ▼
                    [Asignar     [Mantener como
                     topic_id]   valor atípico (-1)]
        │                              │
        └──────────┬───────────────────┘
                   ▼
[4. Representación de Temas — c-TF-IDF]
  Generar términos representativos por grupo
  Ejemplo: "Feminicidio · Menor · Huérfano"
        │
        ▼
[5. Etiquetado Automático (KeyBERTInspired)]
        │
        ▼
[Salida: topic_id, etiqueta, términos_principales,
         num_documentos, cohesión por cada grupo]
        │
        ▼
[Persistir en tabla clusters_semanticos]
```

---

## 24. Diagrama de Flujo de Búsqueda con Texto Completo (FTS, OE-3)

**Categoría:** Flujo de datos  
**Prioridad:** Media

**Flujo:**

```
[Entrada: Consulta del usuario (ej: "huérfanos")]
        │
        ▼
[Expandir con diccionario de sinónimos]
  "huérfanos" → {"huérfanos", "orfandad", "sin madre",
                  "víctimas indirectas", "hijos de la víctima"}
        │
        ▼
[Construir consulta tsquery]
  'huérfanos' | 'orfandad' | 'sin madre' | ...
        │
        ▼
[Ejecutar en PostgreSQL]
  SELECT *, ts_rank(busqueda_fts, consulta) AS ranking
  FROM noticias
  WHERE busqueda_fts @@ consulta
  ORDER BY ranking DESC
        │
        ▼
[Índice GIN: tiempo < 10ms]
        │
        ▼
[Devolver resultados ordenados por relevancia]
```

---

## 25. Diagrama de Actividades — Ciclo completo del sistema

**Categoría:** Comportamiento  
**Prioridad:** Alta

**Descripción:**  
Diagrama de actividades UML que muestra el ciclo completo del sistema desde la recolección hasta la visualización, incluyendo las dos ramas paralelas (recolección cada 6h y análisis cada 12h).

**Carriles (swimlanes):**
1. **Planificador** (scheduler.py)
2. **Recolección** (collector.py + scraper.py)
3. **Análisis** (analyzer.py + semantic_detector.py + bertopic_clustering.py)
4. **Persistencia** (repository.py + PostgreSQL)
5. **Presentación** (Flask webapp)

---

## Plataformas Recomendadas para Diagramas Profesionales

A continuación se listan herramientas para crear diagramas con aspecto profesional y académico:

### 1. **draw.io (diagrams.net)** — RECOMENDADA PRINCIPAL
- **Costo:** Gratuita
- **Enlace:** https://app.diagrams.net
- **Ventajas:**
  - Integración con VS Code (extensión "Draw.io Integration")
  - Exporta a PNG, SVG, PDF en alta resolución
  - Plantillas UML completas (casos de uso, secuencia, ER, estados, componentes)
  - Guardado en Google Drive, GitHub o local
  - Ideal para todos los diagramas de esta lista
- **Ideal para:** Todos los diagramas (ER, flujo, secuencia, casos de uso, etc.)

### 2. **Lucidchart**
- **Costo:** Gratuito (limitado) / Educativo gratuito con correo .edu
- **Enlace:** https://www.lucidchart.com
- **Ventajas:**
  - Interfaz muy pulida y profesional
  - Colaboración en tiempo real
  - Gran biblioteca de formas UML
  - Exporta a PNG, PDF, Visio
- **Ideal para:** Diagramas de arquitectura, ER, casos de uso

### 3. **PlantUML**
- **Costo:** Gratuita
- **Enlace:** https://plantuml.com
- **Ventajas:**
  - Genera diagramas desde texto/código (reproducible)
  - Extensión para VS Code
  - Soporta: secuencia, clases, estados, actividades, componentes, ER
  - Consistencia visual automática
- **Ideal para:** Diagramas de secuencia, clases, estados

### 4. **Mermaid** (integrado en Markdown/GitHub)
- **Costo:** Gratuita
- **Enlace:** https://mermaid.js.org
- **Ventajas:**
  - Se escribe en texto dentro de Markdown
  - Renderiza en GitHub, GitLab, Notion
  - Soporta: flujo, secuencia, ER, Gantt, estados
- **Ideal para:** Documentación en repositorios, diagramas rápidos

### 5. **StarUML**
- **Costo:** Licencia de pago (prueba gratuita)
- **Enlace:** https://staruml.io
- **Ventajas:**
  - Herramienta UML profesional completa
  - Genera código desde diagramas
  - Muy usado en ambientes académicos
- **Ideal para:** Diagramas UML formales (clases, secuencia, casos de uso)

### 6. **dbdiagram.io**
- **Costo:** Gratuita
- **Enlace:** https://dbdiagram.io
- **Ventajas:**
  - Especializada en diagramas de base de datos
  - Sintaxis simple tipo código
  - Exporta a PNG, PDF
  - Genera SQL desde el diagrama
- **Ideal para:** Diagrama Entidad-Relación y esquema relacional (diagramas 3 y 4)

---

### Recomendación final

Para tu proyecto, la combinación más práctica sería:

| Herramienta | Diagramas a hacer |
|---|---|
| **draw.io** | Arquitectura (#1, #2, #11), Flujos (#7–#10, #22–#24), Navegación (#19), Actividades (#25) |
| **dbdiagram.io** | Entidad-Relación (#3) y Esquema relacional (#4) |
| **draw.io o PlantUML** | Casos de uso (#5, #6), Secuencia (#12–#16), Estados (#17, #18), Clases (#20) |

> **Consejo:** Mantén un estilo visual consistente en todos los diagramas: misma paleta de colores, misma tipografía, y bordes redondeados vs. rectos iguales en todo el documento. Eso los hace verse profesionales como los de la carpeta `images/` de referencia.
