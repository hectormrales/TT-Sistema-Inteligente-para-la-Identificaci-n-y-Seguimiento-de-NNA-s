# Estructura del Proyecto — Explicación de cada archivo

> Guía completa de qué hace cada archivo del sistema y cómo se relacionan entre sí.

---

## Vista general del árbol

```
📁 Raíz del proyecto
│
├── config.py                    ← Configuración centralizada
├── scheduler.py                 ← Planificador automático (cada 6h/12h)
├── wsgi.py                      ← Punto de entrada para producción (Gunicorn)
├── Dockerfile                   ← Imagen Docker del sistema
├── docker-compose.yml           ← Orquestación de 3 contenedores
├── requirements.txt             ← Dependencias de Python (40+ paquetes)
│
├── 📁 app/                      ← APLICACIÓN WEB (Flask)
│   ├── __init__.py              ← Fábrica de la aplicación Flask
│   ├── models.py                ← Modelos de usuario y fuentes (Argon2id)
│   ├── 📁 auth/                 ← Módulo de autenticación
│   │   ├── __init__.py
│   │   ├── forms.py             ← Formularios de login y registro (WTForms)
│   │   └── routes.py            ← Rutas: /login, /register, /logout
│   ├── 📁 main/                 ← Módulo principal (tablero + API)
│   │   ├── __init__.py
│   │   └── routes.py            ← Tablero, búsqueda, API REST (11 endpoints)
│   ├── 📁 sources/              ← Módulo de gestión de fuentes
│   │   ├── __init__.py
│   │   └── routes.py            ← CRUD de fuentes RSS
│   └── 📁 templates/            ← Plantillas HTML
│       ├── dashboard.html       ← Tablero con gráficas (Bootstrap + Chart.js)
│       ├── sources.html         ← Gestión de fuentes
│       └── 📁 auth/
│           ├── login.html       ← Pantalla de inicio de sesión
│           └── register.html    ← Pantalla de registro
│
├── 📁 src/                      ← LÓGICA DE NEGOCIO
│   ├── __init__.py
│   ├── 📁 analysis/             ← Motor de análisis PLN
│   │   ├── __init__.py
│   │   ├── analyzer.py          ← Flujo completo de 11 pasos
│   │   ├── semantic_detector.py ← Detección semántica BETO (OE-1)
│   │   ├── bertopic_clustering.py ← Agrupamiento BERTopic (OE-4)
│   │   ├── dedup.py             ← 4 técnicas de deduplicación
│   │   └── synonyms.py          ← Diccionario de 143 sinónimos
│   ├── 📁 collection/           ← Módulo de recolección
│   │   ├── __init__.py
│   │   ├── collector.py         ← Recolección RSS + puntuación dual
│   │   ├── scraper.py           ← Raspado web dinámico (stealth)
│   │   └── historical_scraper.py ← Recolección histórica (OE-2)
│   └── 📁 database/             ← Capa de persistencia
│       ├── __init__.py
│       ├── models_noticias.py   ← 4 tablas SQLAlchemy
│       └── repository.py        ← Repositorio + FTS + disparadores
│
├── 📁 data/                     ← DATOS (generados automáticamente)
│   ├── noticias_raw.csv         ← Noticias sin analizar
│   ├── noticias.csv             ← Noticias procesadas
│   ├── noticias_analyzed_simplified.csv  ← Resultado final del análisis
│   ├── noticias_analyzed_simplified_metadata.json ← Metadatos del análisis
│   ├── seen_urls.json           ← URLs ya procesadas (evita re-descarga)
│   └── synonym_dictionary.json  ← Diccionario de sinónimos exportado
│
├── 📁 logs/                     ← REGISTROS
│   └── webapp.log               ← Registro de la aplicación web
│
└── 📁 docs/                     ← DOCUMENTACIÓN
    ├── 📁 TT2/                  ← Documentación formal LaTeX
    └── varios .md               ← Documentación técnica
```

---

## Archivos raíz

### `config.py`
**Función:** Configuración centralizada de todo el sistema.  
**Detalle:** Define una clase `Config` que contiene:
- **38 feeds RSS** + **10 consultas de Google News** — son las 54 fuentes de las que se obtienen noticias. Incluye medios como La Jornada, Proceso, CIMAC Noticias, Animal Político, entre otros.
- **Pesos del sistema de puntuación** — feminicidio tiene peso 0.55 y NNA peso 0.45. El umbral mínimo de relevancia es 0.25. El título pesa 3× más que el contenido.
- **Parámetros de los algoritmos** — K-Means con 5 grupos, LDA con 6 tópicos, TF-IDF con 5000 características.
- **Conexión a PostgreSQL** — lee credenciales desde variables de entorno (para Docker), configura pool de 5 conexiones con máximo 10 de desbordamiento.
- **Seguridad de sesiones Flask** — cookies HttpOnly, SameSite=Lax, tiempo de vida de 60 minutos.
- **Cabeceras HTTP** — User-Agent para las peticiones de raspado web.

**Relación:** Prácticamente todos los demás archivos importan `Config` de aquí para obtener parámetros.

---

### `scheduler.py`
**Función:** Planificador automático que orquesta la recolección y el análisis de noticias.  
**Detalle:** Este archivo es el "cerebro operativo" del sistema. Cuando se ejecuta:
- `python scheduler.py schedule` → Inicia un ciclo automático que **recolecta noticias cada 6 horas** y **ejecuta el análisis PLN cada 12 horas**.
- `python scheduler.py collect` → Ejecuta solo la recolección una vez.
- `python scheduler.py analyze` → Ejecuta solo el análisis una vez.
- `python scheduler.py full` → Ejecuta recolección + análisis secuencialmente.
- `python scheduler.py historical` → Ejecuta la recolección histórica (OE-2).
- `python scheduler.py migrate` → Migra datos de CSV a PostgreSQL (OE-3).

**Funciones principales:**
- `collect_news()` — Llama al recolector, deduplica y guarda en CSV.
- `analyze_news()` — Ejecuta el flujo completo de 11 pasos (TF-IDF, LDA, BETO, BERTopic, PostgreSQL).
- `start_scheduler()` — Configura los intervalos y entra en bucle infinito.

**Relación:** Importa `collector.py`, `analyzer.py`, `dedup.py`, `historical_scraper.py`.

---

### `wsgi.py`
**Función:** Punto de entrada de la aplicación web para producción.  
**Detalle:** Gunicorn (el servidor de producción) ejecuta este archivo. Lo que hace:
1. Crea la aplicación Flask usando la fábrica `create_app()`.
2. Configura el registro de actividad (logging) para guardar en `logs/webapp.log`.
3. Intenta cargar el CSV de noticias analizadas al contexto de la aplicación como caché inicial.
4. Expone el objeto `app` que Gunicorn sirve en el puerto 5000.

**Relación:** Importa `app.create_app`.

---

### `Dockerfile`
**Función:** Define la imagen Docker del sistema.  
**Detalle:**
- Usa `python:3.11-slim` como imagen base (ligera).
- Instala dependencias del sistema: `curl` (para health checks), `libpq-dev` (para PostgreSQL), `build-essential` (para compilar paquetes C).
- Instala PyTorch versión CPU (sin CUDA, para que sea más ligera).
- Crea un usuario no privilegiado `appuser` por seguridad (el contenedor no corre como root).
- Copia el código fuente y las dependencias.
- Incluye un health check que verifica `http://localhost:5000/health` cada 30 segundos.

---

### `docker-compose.yml`
**Función:** Orquesta los 3 contenedores Docker del sistema.  
**Detalle:** Define tres servicios:

| Servicio | Qué ejecuta | Puerto | Detalles |
|---|---|---|---|
| `nna-postgres` | PostgreSQL 16 | 5432 | Base de datos principal. Tiene health check con `pg_isready`. Volumen persistente `pgdata`. |
| `nna-analyzer` | `scheduler.py schedule` | — | Ejecuta recolección cada 6h y análisis cada 12h. Comparte volúmenes `./data`, `./logs` y `models_cache`. Espera a que PostgreSQL esté sano. |
| `nna-webapp` | `gunicorn wsgi:app` | 5000 | Aplicación web con 2 workers y timeout de 300 segundos. Espera a que PostgreSQL esté sano y el analizador haya iniciado. |

Los tres contenedores comparten la red `nna-network`.

---

### `requirements.txt`
**Función:** Lista de todas las dependencias Python del proyecto (40+ paquetes).  
**Detalle por categoría:**
- **Datos:** pandas, numpy, scikit-learn — manipulación de DataFrames y algoritmos de ML.
- **PLN:** torch, transformers, sentence-transformers — modelos de lenguaje (BETO).
- **Agrupamiento:** bertopic, hdbscan, umap-learn — clustering semántico.
- **Web scraping:** requests, beautifulsoup4, feedparser, trafilatura — descarga y extracción de contenido.
- **Aplicación web:** Flask, Flask-Login, Flask-SQLAlchemy, Flask-WTF — framework web con autenticación y formularios.
- **Base de datos:** psycopg2-binary, SQLAlchemy — conexión y ORM para PostgreSQL.
- **Seguridad:** argon2-cffi — hashing de contraseñas (estándar OWASP).
- **Producción:** gunicorn, schedule — servidor WSGI y planificación de tareas.

---

## Carpeta `app/` — Aplicación Web

### `app/__init__.py`
**Función:** Fábrica de la aplicación Flask (patrón Application Factory).  
**Detalle:** La función `create_app()` es la que construye toda la aplicación web:
1. Crea la instancia de Flask.
2. Carga la configuración desde `config.py`.
3. Inicializa extensiones: CORS (para permitir peticiones desde otros dominios en las rutas `/api/*`), CSRF (protección contra ataques), SQLAlchemy (ORM), LoginManager (sesiones de usuario).
4. Registra los tres blueprints (módulos): `auth_bp`, `main_bp`, `sources_bp`.
5. Llama a `_init_database()` que:
   - Crea todas las tablas en PostgreSQL si no existen.
   - Crea un usuario administrador por defecto (credenciales desde `.env`).
   - Siembra las 30+ fuentes RSS predefinidas en la tabla `news_sources` con nombres legibles (ej: "La Jornada", "Proceso", "CIMAC Noticias").
   - Inicializa el esquema de búsqueda de texto completo (FTS).

**Relación:** Es importado por `wsgi.py` y por los tests.

---

### `app/models.py`
**Función:** Define los modelos ORM de usuario y fuentes de noticias.  
**Detalle:** Contiene dos clases:

**`User`** — Modelo de usuario del sistema:
- Campos: `id`, `username` (único), `email` (único), `password_hash`, `is_active`, `is_admin`, `created_at`, `last_login`.
- `set_password(password)` — Genera el hash Argon2id de la contraseña con parámetros OWASP (time_cost=3, memory=64MB, parallelism=4).
- `check_password(password)` — Verifica la contraseña contra el hash almacenado. Si los parámetros de Argon2 cambiaron, re-hashea automáticamente.
- Hereda de `UserMixin` de Flask-Login para manejar sesiones.

**`NewsSource`** — Modelo de fuente de noticias:
- Campos: `id`, `name`, `url` (único), `source_type` (auto/rss/sitemap/html), `is_active`, `is_predefined` (no se puede borrar), `added_by` (FK a User), `last_scraped`, `last_status`, `last_error`, `articles_found`, `crawl_delay`, `notes`.
- `to_dict()` — Serializa el objeto a diccionario para la API REST.

---

### `app/auth/forms.py`
**Función:** Formularios para inicio de sesión y registro con validación robusta.  
**Detalle:**
- **`LoginForm`** — Campos: nombre de usuario, contraseña, "recordarme". Todos con validación `DataRequired`.
- **`RegistrationForm`** — Campos: nombre de usuario, email, contraseña, confirmación. Validaciones:
  - El nombre de usuario solo acepta letras, números y guion bajo.
  - El email debe ser válido y no estar ya registrado.
  - La contraseña debe cumplir OWASP: mínimo 12 caracteres, al menos una mayúscula, una minúscula, un número y un símbolo especial.
  - Verifica que username y email no existan ya en la base de datos.
- Todos los formularios generan automáticamente un token CSRF.

---

### `app/auth/routes.py`
**Función:** Maneja las tres rutas de autenticación: login, registro y logout.  
**Detalle:**
- **`/login` (GET/POST)** — Muestra el formulario de login. Al enviar, busca al usuario por username, verifica la contraseña con Argon2id, crea la sesión y redirige al tablero. Soporta "recordarme" y una URL de retorno segura (`next` param) con validación contra Open Redirect.
- **`/register` (GET/POST)** — Muestra el formulario de registro. Crea el usuario con contraseña hasheada y lo redirige al login.
- **`/logout`** — Cierra la sesión del usuario y limpia los datos de sesión.
- **`_is_safe_url(target)`** — Función de seguridad que valida que la URL de redirección no apunte a otro dominio (previene ataques de redirección abierta).

---

### `app/main/routes.py`
**Función:** Corazón de la aplicación web — tablero, búsqueda, API REST y gráficas.  
**Detalle:** Es el archivo más extenso del módulo web (~540 líneas). Define el blueprint `main_bp` con estas rutas:

| Ruta | Método | Función |
|---|---|---|
| `/` | GET | Renderiza el tablero (dashboard.html) con estadísticas y datos |
| `/api/stats` | GET | Devuelve JSON con totales: noticias, NNA, relevancia alta/media/baja, clústeres |
| `/api/noticias` | GET | Lista paginada de noticias con filtros (relevancia, solo NNA, ordenamiento) |
| `/api/search` | GET | Búsqueda con expansión de sinónimos vía FTS de PostgreSQL |
| `/api/analyze` | POST | Dispara el flujo de análisis completo (pasos 1-11) |
| `/api/export/csv` | GET | Descarga un archivo CSV con todas las noticias analizadas |
| `/api/charts/temporal` | GET | Datos para gráfica de noticias por mes |
| `/api/charts/relevancia` | GET | Datos para gráfica circular de distribución de relevancia |
| `/api/charts/estados` | GET | Datos para gráfica de noticias por estado de México |
| `/api/charts/fuentes` | GET | Datos para gráfica de noticias por medio de comunicación |
| `/health` | GET | Comprobación de salud del sistema (sin autenticación, para Docker) |

**Modo dual CSV/PostgreSQL:** Cada endpoint intenta primero obtener datos de PostgreSQL. Si no hay conexión o datos, cae automáticamente a leer el CSV como respaldo.

---

### `app/sources/routes.py`
**Función:** CRUD completo para gestionar las fuentes de noticias RSS.  
**Detalle:** Define el blueprint `sources_bp` con prefijo `/fuentes`:

| Ruta | Método | Función |
|---|---|---|
| `/fuentes/` | GET | Página HTML de gestión de fuentes |
| `/fuentes/api/sources` | GET | Lista todas las fuentes con conteo de activas |
| `/fuentes/api/sources` | POST | Agrega nueva fuente (valida URL, detecta duplicados, genera nombre automático) |
| `/fuentes/api/sources/<id>` | PUT | Actualiza una fuente existente |
| `/fuentes/api/sources/<id>` | DELETE | Elimina una fuente (solo las agregadas por el usuario, no las predefinidas) |
| `/fuentes/api/sources/<id>/toggle` | POST | Activa o desactiva una fuente |
| `/fuentes/api/sources/<id>/test` | POST | Prueba una fuente: detecta si es RSS/sitemap/HTML, extrae 5 artículos de muestra, actualiza el estado |
| `/fuentes/api/sources/probe` | POST | Sondea una URL sin guardarla para ver qué tipo de fuente es |

---

### `app/templates/dashboard.html`
**Función:** Interfaz del tablero principal.  
**Detalle:** Página HTML que usa Bootstrap 5 para el diseño y Chart.js para las gráficas interactivas. Muestra tarjetas con estadísticas, gráficas temporales/de relevancia, y una tabla de noticias con paginación y búsqueda.

### `app/templates/sources.html`
**Función:** Interfaz de gestión de fuentes.  
**Detalle:** Tabla interactiva con las fuentes RSS configuradas, botones de acción (probar, activar/desactivar, eliminar) y formulario para agregar nuevas fuentes.

### `app/templates/auth/login.html`
**Función:** Formulario de inicio de sesión con campos de usuario y contraseña.

### `app/templates/auth/register.html`
**Función:** Formulario de registro con validaciones del lado del cliente.

---

## Carpeta `src/analysis/` — Motor de Análisis PLN

### `src/analysis/analyzer.py`
**Función:** Orquesta el flujo completo de análisis de noticias en 11 pasos.  
**Detalle:** Es el archivo central del análisis (~890 líneas). La clase `SimplifiedNewsAnalyzer` ejecuta secuencialmente:

| Paso | Método | Qué hace |
|---|---|---|
| 1 | `step_1_collect_data()` | Obtiene noticias del recolector con puntuación dual |
| 2 | `step_2_save_initial_data()` | Guarda CSV sin procesar como respaldo |
| 3 | `step_3_vectorize_text()` | Vectorización TF-IDF con 5000 características, n-gramas (1,3), aumento de dominio con 20 términos clave |
| 4 | `step_4_topic_modeling()` | LDA (Latent Dirichlet Allocation) para encontrar 6 tópicos automáticamente |
| 5 | `step_5_clustering()` | K-Means con 5 grupos + métrica Silhouette Score |
| 6 | `step_6_similarity_analysis()` | Matriz de similitud coseno N×N para detectar duplicados semánticos |
| 7 | `step_7_tfidf_rescore()` | Reclasificación: compara cada noticia con un "documento ideal" de términos de dominio (60% heurístico + 40% TF-IDF) |
| 8 | `step_8_enhanced_search_setup()` | Configura el diccionario de sinónimos |
| 9 | `step_9_semantic_detection()` | OE-1: Clasificación con BETO (modo híbrido con α dinámico) |
| 10 | `step_10_bertopic_clustering()` | OE-4: Reemplaza K-Means con BERTopic semántico |
| 11 | `step_11_persist_to_postgres()` | OE-3: Guarda todo en PostgreSQL con FTS |

También define:
- `DOMAIN_TERMS`: 20 términos de dominio ("feminicidio", "huérfanos", "orfandad", etc.) que se inyectan en TF-IDF para asegurar que siempre estén en el vocabulario.
- `SPANISH_STOP_WORDS`: 70+ palabras vacías en español que se excluyen del análisis.

---

### `src/analysis/semantic_detector.py`
**Función:** Implementa la detección semántica con el modelo BETO (OE-1).  
**Detalle:** Este es el módulo de inteligencia artificial más complejo del sistema (~890 líneas). Contiene:

**`BETOClassifier`** — Red neuronal que extiende BETO:
- Toma el token [CLS] de BETO (768 dimensiones).
- Lo pasa por: Dropout(0.3) → Linear(768→256) → ReLU → Dropout(0.2) → Linear(256→2) → Softmax.
- Salida: probabilidad de que la noticia sea relevante.

**`SemanticDetector`** — Clase principal con 3 modos de operación:
- **Cero-disparo (zero_shot):** Sin entrenamiento previo. Compara las incrustaciones de la noticia con descripciones de categorías predefinidas usando similitud coseno. Precisión: ~80-85%.
- **Ajuste fino (finetuned):** Entrena el clasificador con noticias ya etiquetadas por el heurístico. Usa AdamW + planificador lineal con detención temprana. Precisión: ~90-95%.
- **Híbrido (hybrid):** Combina el score semántico con el heurístico usando un α dinámico: si la confianza del modelo es alta (>0.8), le da 70% de peso al semántico; si es baja (<0.5), solo 30%.

**`HybridScorer`** — Combina ambas puntuaciones: `score_final = α × score_semántico + (1-α) × score_heurístico`.

El modelo base es `dccuchile/bert-base-spanish-wwm-cased` (BETO), un modelo Transformer pre-entrenado con texto en español.

---

### `src/analysis/bertopic_clustering.py`
**Función:** Implementa el agrupamiento semántico con BERTopic (OE-4).  
**Detalle:** ~730 líneas. La clase `SemanticClustering` construye un flujo modular:

1. **Incrustaciones:** Usa `paraphrase-multilingual-MiniLM-L12-v2` para convertir cada noticia en un vector de 384 dimensiones que captura su significado semántico.
2. **UMAP:** Reduce de 384 a 5 dimensiones preservando la estructura topológica (mejor que PCA o t-SNE para agrupamiento).
3. **HDBSCAN:** Detecta automáticamente cuántos grupos existen sin necesidad de especificar un número fijo. Identifica valores atípicos (outliers).
4. **Reasignación de valores atípicos:** HDBSCAN marca ~80% como outliers. El sistema aplica 3 estrategias secuenciales para reasignarlos: probabilidades blandas → distribución c-TF-IDF → distancia coseno. Reduce outliers a ~55%.
5. **c-TF-IDF:** Genera una representación de cada grupo con los términos más representativos.
6. **KeyBERTInspired:** Genera etiquetas automáticas (ej: "Feminicidio · Menor · Huérfano").

También genera visualizaciones interactivas en HTML (Plotly): mapa de temas, gráfico de barras de términos y dendrograma jerárquico.

---

### `src/analysis/dedup.py`
**Función:** Elimina noticias duplicadas usando 4 técnicas en cascada.  
**Detalle:** La clase `NewsDeduplicator` aplica estas técnicas en orden de velocidad:

| Técnica | Velocidad | Qué detecta | Umbral |
|---|---|---|---|
| 1. Hash MD5 | ~milisegundos | Títulos idénticos (tras normalizar) | Exacto |
| 2. Jaccard | Rápida | Títulos con variaciones menores | ≥ 0.70 |
| 3. SimHash | Rápida | Contenidos casi idénticos | Distancia Hamming ≤ 8 |
| 4. Coseno TF-IDF | Lenta | Noticias semánticamente iguales | ≥ 0.85 |

La idea es que los métodos rápidos eliminan la mayoría de duplicados, y solo las noticias que pasan las 3 primeras pruebas se evalúan con TF-IDF (que es más costosa computacionalmente).

Resultado típico: de ~144 artículos por ciclo, elimina ~10-14 duplicados.

---

### `src/analysis/synonyms.py`
**Función:** Diccionario de sinónimos especializado en feminicidio y NNA.  
**Detalle:** La clase `SynonymDictionary` contiene 143 términos organizados en 8 categorías:

| Categoría | Ejemplos |
|---|---|
| feminicidio | feminicidio, femicidio, asesinato de mujer, violencia feminicida |
| nna | niños, menores, infantes, adolescentes, hijos, bebés |
| orfandad | huérfanos, sin madre, víctimas indirectas, hijos de la víctima |
| violencia | agresión, maltrato, abuso, lesiones |
| alerta_genero | AVG, declaratoria de alerta |
| justicia | juicio, sentencia, fiscalía, denuncia |
| proteccion | DIF, custodia, tutela, adopción, albergue |
| actores | víctima, agresor, feminicida, imputado |

Cuando un usuario busca "huérfanos", el sistema automáticamente expande la búsqueda a todos los sinónimos: "orfandad", "sin madre", "víctimas indirectas", etc. Esto mejora significativamente la cobertura de la búsqueda.

---

## Carpeta `src/collection/` — Módulo de Recolección

### `src/collection/collector.py`
**Función:** Recolecta noticias de 54 fuentes RSS, las puntúa y filtra.  
**Detalle:** Este es el módulo que alimenta de datos al sistema (~620 líneas). Su función principal `collect_all_news()`:

1. **Obtiene las fuentes** — Primero intenta leer fuentes activas desde la tabla `news_sources` en la base de datos. Si no hay conexión, usa las 54 fuentes de `config.py`.
2. **Descarga cada feed RSS** — Parsea el XML, extrae título, contenido, enlace, fecha y fuente.
3. **Filtra por antigüedad** — Solo conserva noticias de los últimos 30 días.
4. **Calcula la puntuación dual** — Cada noticia recibe dos puntuaciones:
   - **score_feminicidio** (peso 55%): Evalúa 17 expresiones regulares como "feminicidio" (peso 1.0), "violencia feminicida" (0.85), "ex pareja" (0.35), etc.
   - **score_nna** (peso 45%): Evalúa 23 expresiones regulares como "huérfanos" (1.0), "hijos de la víctima" (0.95), "custodia" (0.4), etc.
   - Si ambos ejes superan 0.10, se aplica una bonificación de ×1.35 a ×1.55.
   - Si el título menciona ambos temas, otra bonificación de ×1.20.
5. **Filtra por relevancia** — Descarta noticias con puntuación compuesta < 0.25.
6. **Filtro geográfico de México** — Utiliza 100+ indicadores de México (32 estados, 60+ ciudades, instituciones como DIF, Fiscalía, SIPINNA) y 30+ indicadores de exclusión (otros países de Latinoamérica). La lógica es conservadora: si no se detectan suficientes indicadores de México, se descarta.
7. **Deduplicación** — Llama al deduplicador para eliminar la misma noticia publicada en varios medios.
8. **Registra URLs procesadas** — Guarda las URLs en `seen_urls.json` para no re-descargarlas en el próximo ciclo.

---

### `src/collection/scraper.py`
**Función:** Raspador web dinámico e inteligente con técnicas anti-bloqueo.  
**Detalle:** Es el archivo más extenso del módulo de recolección (~960 líneas). Contiene:

**`RobotsChecker`** — Antes de raspar, lee `robots.txt` del sitio para respetar las reglas:
- Verifica si la URL está permitida para el bot.
- Obtiene el `crawl-delay` (tiempo entre peticiones).
- Descubre sitemaps disponibles.

**`StealthSession`** — Sesiones HTTP que imitan un navegador real:
- Rota entre 9 User-Agents reales (Chrome, Firefox, Safari, Edge).
- Genera cabeceras HTTP realistas (Accept, Accept-Language, Sec-Fetch-*).
- Aplica pausas aleatorias entre peticiones (8-20 segundos en producción, 2-5 en pruebas).
- Reintentos con retroceso exponencial (máximo 3 intentos).

**`DynamicScraper`** — El raspador principal:
- **`probe_url(url)`** — Detecta automáticamente qué tipo de fuente es una URL: RSS, sitemap o HTML. Lee robots.txt, busca etiquetas `<link>` de feeds y prueba 16 rutas comunes de RSS.
- **`scrape_source(url, method)`** — Extrae artículos según el tipo detectado:
  - RSS: parsea XML y extrae items.
  - Sitemap: sigue el `sitemap.xml`, filtra URLs que parecen artículos y extrae cada uno.
  - HTML: encuentra enlaces a artículos en la página y los raspa individualmente.
- **`_extract_article(url)`** — Cascada de 7 niveles para extraer el contenido:
  1. JSON-LD (Schema.org) — la fuente más estructurada.
  2. Trafilatura — biblioteca especializada en extracción de texto.
  3. 16 selectores CSS para contenido del artículo.
  4. 8 selectores CSS para título.
  5. Meta tags Open Graph (og:title, og:description).
  6. Validación mínima (título ≥ 10 caracteres, contenido ≥ 50).
  7. Google Cache como último recurso si la página está bloqueada.

Detecta 20 firmas de bloqueo: Cloudflare, CAPTCHA, paywall, errores 403/406.

---

### `src/collection/historical_scraper.py`
**Función:** Recolección de noticias históricas del período 2023–2026 (OE-2).  
**Detalle:** ~580 líneas. Utiliza dos fuentes de archivo:

**`GoogleNewsHistorical`** — Busca en Google News con filtros de fecha:
- 20 consultas especializadas (ej: "feminicidio huérfanos México", "orfandad feminicidio NNA").
- Divide el período en ventanas mensuales.
- Aplica pausas de 3-8 segundos entre peticiones para evitar bloqueos.

**`WaybackHistorical`** — Usa la Wayback Machine (Internet Archive):
- API CDX para encontrar páginas archivadas de 9 dominios de medios mexicanos.
- Extrae el contenido de cada versión archivada.
- Pausas de 2-5 segundos.

**`TimeSeriesAnalyzer`** — Analiza los datos recolectados temporalmente:
- Conteos mensuales, trimestrales y anuales.
- Media móvil (ventana de 3 meses).
- Detección de picos mediáticos usando z-score.
- Análisis de estacionalidad (qué meses tienen más cobertura).

---

## Carpeta `src/database/` — Capa de Persistencia

### `src/database/models_noticias.py`
**Función:** Define las 4 tablas principales del sistema como modelos SQLAlchemy.  
**Detalle:** ~250 líneas. Tablas:

**`Noticia`** — Tabla principal con ~25 columnas:
- Contenido: título, contenido, enlace, fuente, fecha.
- Puntuaciones: score_feminicidio, score_nna, score_compuesto, relevancia_final.
- Semántica (OE-1): score_semantico, modo_deteccion.
- Agrupamiento (OE-4): cluster_id (FK), topic_id, topic_description.
- FTS (OE-3): busqueda_fts (tsvector generado por trigger).
- Metadatos: content_hash (para deduplicación), scrape_method, menores_identificados.

**`Deteccion`** — Auditoría detallada de cómo se clasificó cada noticia (relación 1:1 con Noticia):
- Scores separados: heurístico, semántico, híbrido.
- Palabras clave encontradas (JSON).
- Alpha usado en modo híbrido.
- Si se encontraron menores y edades mencionadas.

**`ClusterSemantico`** — Un registro por cada grupo temático encontrado por BERTopic:
- Etiqueta automática, descripción, términos principales con pesos (JSON), número de documentos, cohesión.

**`Entidad`** — Para futura extracción de entidades nombradas (NER):
- Texto, tipo (PER/LOC/ORG/MISC), posición en el texto original, confianza.

---

### `src/database/repository.py`
**Función:** Implementa el patrón Repositorio para acceso a datos con búsqueda de texto completo (FTS).  
**Detalle:** ~450 líneas. La clase `NoticiasRepository` ofrece:

**`init_fts_schema()`** — Configura PostgreSQL para búsqueda de texto completo:
- Instala la extensión `unaccent` para búsqueda sin acentos.
- Crea la configuración FTS con stemmer en español.
- Crea un trigger que actualiza automáticamente el campo `busqueda_fts` (tsvector) cada vez que se inserta o actualiza una noticia.
- Crea el índice GIN para búsqueda en < 10ms.
- Crea 8 índices B-tree adicionales para consultas rápidas.

**`buscar_fts(query)`** — Búsqueda de texto completo:
- Convierte la consulta a tsquery con operador OR entre términos.
- Usa `ts_rank()` para ordenar por relevancia.
- Soporta filtros adicionales: clasificacion, solo_nna.
- Tiempo de respuesta < 50ms.

**`crear_batch(records)`** — Inserción masiva de noticias en lotes de 100, con deduplicación por hash y enlace.

**`estadisticas()`** — Consultas COUNT optimizadas con índices para el tablero.

**`importar_desde_csv()`** — Importa noticias desde CSV a PostgreSQL, generando content_hash MD5 para cada una.

---

## Carpeta `data/` — Datos

| Archivo | Descripción |
|---|---|
| `noticias_raw.csv` | Noticias recién recolectadas, sin análisis. Se genera en el paso 2 del flujo. |
| `noticias.csv` | Noticias con puntuación dual y filtro geográfico aplicados. |
| `noticias_analyzed_simplified.csv` | **Resultado final**: noticias analizadas con todos los scores, clasificaciones, clústeres y tópicos. Es el archivo principal que usa la webapp como respaldo si PostgreSQL no está disponible. |
| `noticias_analyzed_simplified_metadata.json` | Metadatos del último análisis: total de noticias, versión, algoritmos usados, timestamp. |
| `seen_urls.json` | Diccionario de URLs ya procesadas con sus timestamps. Evita re-descargar la misma noticia. Se limpia automáticamente tras 60 días. |
| `synonym_dictionary.json` | Exportación del diccionario de sinónimos en formato JSON. |

---

## Carpeta `logs/`

| Archivo | Descripción |
|---|---|
| `webapp.log` | Registro de actividad de la aplicación web: errores, peticiones, inicio de sesión, etc. |

---

## Cómo se conecta todo (flujo simplificado)

```
                    scheduler.py
                    (cada 6h / 12h)
                         │
            ┌────────────┴───────────┐
            ▼                        ▼
     collector.py              analyzer.py
     (recolectar)              (analizar)
         │                         │
         ▼                    ┌────┴────┐
     scraper.py           BETO    BERTopic
     (raspar)          (OE-1)    (OE-4)
         │                    └────┬────┘
         ▼                        ▼
     dedup.py              repository.py
     (deduplicar)          (guardar en BD)
         │                        │
         ▼                        ▼
     data/*.csv            PostgreSQL 16
     (respaldo)            (FTS + índices)
                                  │
                                  ▼
                           main/routes.py
                           (API REST + tablero)
                                  │
                                  ▼
                           dashboard.html
                           (gráficas + tabla)
                                  │
                                  ▼
                             Navegador
                             del usuario
```
