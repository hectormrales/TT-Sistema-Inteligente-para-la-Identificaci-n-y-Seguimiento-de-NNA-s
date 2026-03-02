# Documentación de Mejoras — Plataforma NNA v6.0

> **Sistema Inteligente para la Identificación y Seguimiento de NNA Víctimas Indirectas del Feminicidio en México**  
> Documento generado tras la auditoría y mejora integral del sistema.

---

## Índice

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Mejoras al Dashboard (Frontend)](#2-mejoras-al-dashboard)
3. [Mejoras al Scraping y Recolección](#3-mejoras-al-scraping)
4. [Filtro México v6.0](#4-filtro-mexico-v60)
5. [Funcionalidades para ONGs](#5-funcionalidades-para-ongs)
6. [Seguridad y Bugs Corregidos](#6-seguridad-y-bugs)
7. [Docker y Configuración](#7-docker-y-configuracion)
8. [Modelos de IA: Comparativas](#8-modelos-de-ia)
9. [Arquitectura general](#9-arquitectura-general)
10. [Resumen de ventajas y desventajas](#10-resumen)

---

## 1. Resumen ejecutivo

Se realizó una auditoría completa del proyecto que incluyó lectura de **todos los archivos fuente** y se implementaron **8 categorías de mejoras**:

| Categoría | Archivos modificados | Estado |
|---|---|---|
| Bugs críticos y seguridad | `wsgi.py`, `config.py`, `app/__init__.py`, dashboard | ✅ |
| Filtro México v6.0 | `src/collection/collector.py` | ✅ |
| Robustez del scraping | `src/collection/collector.py` | ✅ |
| Dashboard con gráficos | `app/templates/dashboard.html`, `app/main/routes.py` | ✅ |
| Funcionalidades para ONGs | `app/templates/dashboard.html` | ✅ |
| Docker y configuración | `docker-compose.yml`, `.env`, `requirements.txt` | ✅ |
| Limpieza de código muerto | `models.py` (eliminado) | ✅ |
| Documentación | Este archivo | ✅ |

---

## 2. Mejoras al Dashboard

### Antes (v5.0)
- Dashboard de una sola vista (lista de noticias + búsqueda)
- Sin gráficos ni visualizaciones
- Sin capacidad de guardar noticias
- Sin indicadores geográficos
- Vulnerabilidad XSS en comillas simples

### Después (v6.0)
- **Sistema de pestañas**: Noticias | Gráficos | Guardadas
- **4 gráficos interactivos** con Chart.js:
  - 📈 Tendencia temporal (línea) — noticias por mes
  - 🍩 Distribución de relevancia (doughnut) — Alta/Media/Baja
  - 📊 Top estados (barras horizontales) — incidencia por entidad federativa
  - 📊 Top fuentes (barras horizontales) — artículos por medio
- **Bookmark/Guardado** de noticias para seguimiento (localStorage)
- **Exportar guardadas** a CSV individual
- **Toast notifications** para feedback al usuario
- **Sub-header contextual** con indicador "Solo México"
- **CSRF token** en meta tag para seguridad de formularios
- **XSS fix**: función `esc()` ahora escapa comillas simples (`'` → `&#39;`)

### Ventajas
- Las ONGs pueden visualizar tendencias y patrones geográficos sin herramientas externas
- El guardado local permite marcar casos de interés sin necesidad de base de datos adicional
- Los gráficos se cargan bajo demanda (pestaña Gráficos) para no ralentizar la carga inicial

### Desventajas
- Las gráficas dependen de Chart.js vía CDN (requiere internet)
- El guardado local (localStorage) se pierde al limpiar el navegador
- Chart.js es una biblioteca del lado del cliente; con millones de registros podría ser lenta

### 4 Endpoints de API creados

| Endpoint | Tipo | Descripción |
|---|---|---|
| `/api/charts/temporal` | GET | Conteo mensual de noticias |
| `/api/charts/relevancia` | GET | Distribución Alta/Media/Baja/No relevante |
| `/api/charts/estados` | GET | Top 15 estados por incidencia (32 estados + patrones) |
| `/api/charts/fuentes` | GET | Top 10 fuentes de noticias |

---

## 3. Mejoras al Scraping

### Antes (v5.0)
- Re-scraping de URLs ya vistas en cada ciclo de 6 horas
- Sin filtro de antigüedad: artículos de años anteriores podían entrar
- Errores silenciosos (un timeout mataba toda la colección)
- Sin estadísticas de recolección

### Después (v6.0)
- **Tracking de URLs vistas** (`data/seen_urls.json`)
  - Persiste entre ciclos de ejecución
  - Auto-limpieza de URLs mayores a 60 días
  - Evita reprocesar artículos ya analizados
- **Filtro de recencia**: solo artículos de los últimos 30 días
- **Manejo específico de excepciones**:
  - `requests.Timeout` → registra timeout sin detener la colección
  - `requests.ConnectionError` → registra error de conexión
  - `Exception` genérica → captura cualquier otro error
- **Estadísticas por fuente**: `sources_ok`, `sources_error`, conteos de `skip_seen`, `skip_old`, `skip_non_mexico`
- **Logging mejorado**: `logging.debug` con conteos para diagnóstico

### Ventajas
- Reducción significativa de procesamiento redundante (no re-analizar noticias ya vistas)
- El sistema es más resiliente: un medio caído no afecta a los demás
- Las estadísticas permiten identificar fuentes problemáticas

### Desventajas
- El archivo `seen_urls.json` crece con el tiempo (mitigado con limpieza a 60 días)
- Si se borra el archivo, se re-procesarán noticias ya vistas (las duplicadas se filtran por dedup)

---

## 4. Filtro México v6.0

### Antes (v5.0)
- ~50 indicadores de México (estados + algunas ciudades)
- ~15 indicadores de exclusión (otros países)
- Detección binaria (México sí/no) sin ponderación
- Dominios `.mx` no validados (podían publicar noticias de otros países)

### Después (v6.0)
- **100+ indicadores de México**:
  - 32 estados
  - 60+ ciudades y municipios (Celaya, Irapuato, Mazatlán, Tapachula, etc.)
  - 16 alcaldías de CDMX (Tláhuac, Xochimilco, GAM, etc.)
  - Municipios del Edomex con alta incidencia (Chimalhuacán, Chalco, Ecatepec, etc.)
  - Instituciones mexicanas: SEDENA, SEMAR, CONAGO, INEGI, SIPINNA, SESNSP, etc.
  - Figuras políticas: AMLO, Claudia Sheinbaum, SEGOB
- **30+ indicadores de exclusión**:
  - Ciudades latinoamericanas: Medellín, Guayaquil, Brasilia, Lima, etc.
  - Estados/provincias de EE.UU.: Texas, California, Florida, etc.
  - Países: Canadá, España, etc.
- **Sistema de puntaje ponderado**:
  - Coincidencias en **título** cuentan **3x** más que en contenido
  - Se calcula `mexico_score` vs `non_mexico_score`
  - Umbrales: `mexico_score >= 2` para aceptar, `non_mexico_score > mexico_score * 1.5` para rechazar
- **Validación reforzada para `.mx`**: dominios mexicanos ahora también se rechazan si `non_mexico_score > mexico_score AND mexico_score < 3`

### Ventajas
- Significativa reducción de falsos positivos (noticias de otros países que pasaban como mexicanas)
- La ponderación por título refleja que el título es más indicativo que el cuerpo
- Instituciones mexicanas como indicadores capturan noticias que no mencionan ubicaciones
- La validación reforzada para `.mx` previene artículos de agencias con sede en México que cubren Centroamérica

### Desventajas
- Lista de indicadores es estática (requiere actualización manual para nuevas instituciones/ciudades)
- En casos muy ambiguos (artículo que menciona México y otro país), el sistema puede fallar en decidir
- El matching es por substring (podría dar falsos positivos con nombres que contengan nombres de ciudades)

---

## 5. Funcionalidades para ONGs

### Nuevas funcionalidades implementadas

| Funcionalidad | Descripción | Implementación |
|---|---|---|
| **Guardar noticias** | Bookmark de noticias individuales para seguimiento | localStorage del navegador |
| **Exportar guardadas** | Descarga CSV con solo las noticias marcadas | Generación client-side |
| **Limpiar guardadas** | Eliminar todos los bookmarks con confirmación | localStorage clear |
| **Indicador visual** | Badge con conteo de guardadas en la pestaña | Badge actualizado en tiempo real |
| **Exportar todo** | CSV completo de todas las noticias analizadas | API endpoint `/api/export/csv` |
| **Gráficos geográficos** | Mapa de calor por estado mexicano | Chart.js bar horizontal |

### Flujo de uso para ONG

1. La ONG inicia sesión con credenciales seguras (Argon2id)
2. Revisa el dashboard con estadísticas generales
3. Filtra por "Alta relevancia" o "NNA identificados"
4. Marca noticias relevantes para su seguimiento con el ícono de bookmark
5. Va a la pestaña "Guardadas" para ver solo sus casos de interés
6. Exporta sus casos a CSV para reportes internos
7. Revisa gráficos para identificar tendencias y patrones geográficos

---

## 6. Seguridad y Bugs Corregidos

### Bug: `sort_col` UnboundLocalError
- **Archivo**: `app/main/routes.py`
- **Causa**: la variable `sort_col` solo se definía dentro del bloque `if 'fecha' in df.columns`, causando `NameError` si no existía la columna
- **Fix**: mover `sort_col = 'fecha'` antes del condicional como valor por defecto

### Bug: `wsgi.py` orden de carga
- **Archivo**: `wsgi.py`
- **Causa**: `_load_data()` se llamaba antes de `create_app()`, sin contexto de aplicación Flask
- **Fix**: invertir el orden — crear app primero, luego cargar datos dentro de `app.app_context()`

### Bug: Contraseña admin hardcodeada en logs
- **Archivo**: `app/__init__.py`
- **Causa**: la contraseña del admin se imprimía en el log al crear el usuario semilla
- **Fix**: contraseña ahora viene de `os.environ.get('ADMIN_PASSWORD')`, log ya no la muestra

### Bug: `SECRET_KEY` vacío
- **Archivo**: `config.py`
- **Causa**: `SECRET_KEY = os.environ.get('SECRET_KEY', '')` — string vacío en producción es inseguro
- **Fix**: `SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()` — auto-genera si no está definido

### Bug: XSS por comillas simples
- **Archivo**: `app/templates/dashboard.html`
- **Causa**: función `esc()` no escapaba `'` (comilla simple), permitiendo inyección en atributos HTML
- **Fix**: agregado `.replace(/'/g, '&#39;')` a la función de escape

### Bug: `.env` concatenado
- **Archivo**: `.env`
- **Causa**: `SECRET_KEY`, `ADMIN_PASSWORD` y `FLASK_ENV` estaban en una misma línea sin separador
- **Fix**: separar cada variable en su propia línea

### Bug: `db_Integer` inexistente en query
- **Archivo**: `app/main/routes.py`
- **Causa**: endpoint `/api/charts/temporal` referenciaba `db_Integer` que no existe
- **Fix**: simplificar la query a `func.count(Noticia.id)`

---

## 7. Docker y Configuración

### Cambios en `docker-compose.yml`
1. **`nna-analyzer`**: agregado `env_file: .env` para que el servicio de análisis tenga acceso a las credenciales de PostgreSQL y `POSTGRES_HOST=nna-postgres`
2. **`nna-webapp`**: cambiado de `python wsgi.py` a `gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 300 wsgi:app` para producción

### Cambios en `requirements.txt`
1. Eliminada entrada duplicada de `schedule` (tenía `>=1.2.0` y `==1.2.2`)
2. Agregado `gunicorn>=21.2.0` como servidor WSGI de producción

### Cambios en `.env`
1. Separadas variables concatenadas en líneas individuales
2. Agregada variable `ADMIN_PASSWORD`

### Código muerto eliminado
- **`models.py` (raíz)**: archivo de 94 líneas que duplicaba el modelo `User` de `app/models.py` — nunca era importado por ningún módulo. **Eliminado**.

---

## 8. Modelos de IA: Comparativas

### BERTopic vs K-Means/LDA (Clustering)

| Aspecto | K-Means + LDA (v4.0) | BERTopic (v5.0+) |
|---|---|---|
| **Representación** | TF-IDF (bag of words) | Embeddings contextuales (sentence-transformers) |
| **Número de clusters** | Debe definirse manualmente (K) | Se determina automáticamente (HDBSCAN) |
| **Calidad semántica** | Baja – agrupa por co-ocurrencia de palabras | Alta – agrupa por significado semántico |
| **Temas outlier** | No soporta | Sí (topic_id = -1 para ruido) |
| **Escalabilidad** | Alta (O(n·k)) | Media (UMAP + HDBSCAN son O(n·log(n))) |
| **Interpretabilidad** | Palabras clave por tema | c-TF-IDF más representativa |
| **Requisitos** | CPU básica | GPU recomendada, más RAM |

**Ventaja principal**: BERTopic entiende que "menor asesinado" y "niño víctima de homicidio" pertenecen al mismo tema, mientras K-Means los separaría por vocabulario diferente.

**Desventaja principal**: BERTopic requiere más recursos computacionales y la primera ejecución descarga el modelo (600MB+).

### BETO vs Keywords (Detección Semántica)

| Aspecto | Heurística por keywords (v4.0) | BETO (v5.0+) |
|---|---|---|
| **Enfoque** | Búsqueda de patrones regex/strings | Comprensión contextual del texto |
| **Falsos positivos** | Alto: "niño prodigio del fútbol" → detectado | Bajo: entiende el contexto |
| **Falsos negativos** | Alto: no detecta paráfrasis | Bajo: capta variaciones semánticas |
| **Velocidad** | Instantánea | ~50ms por artículo |
| **Adaptabilidad** | Requiere agregar keywords manualmente | Zero-shot o fine-tuning |
| **Idioma** | Funciona como texto plano | Entrenado específicamente en español |

**Ventaja principal**: BETO (dccuchile/bert-base-spanish-wwm-cased) fue pre-entrenado con texto en español y distingue contexto — "la niña ganó un premio" vs "la niña quedó huérfana tras feminicidio".

**Desventaja principal**: Modelo de ~420MB, requiere PyTorch y consume más CPU/RAM.

### PostgreSQL FTS vs CSV (Búsqueda)

| Aspecto | Búsqueda en CSV (v4.0) | PostgreSQL FTS (v5.0+) |
|---|---|---|
| **Velocidad** | O(n) – escanea todas las filas | O(log n) – índice GIN |
| **Relevancia** | Conteo simple de coincidencias | ts_rank con pesado por zona |
| **Stemming** | No (busca texto exacto) | Sí (configuración `spanish_unaccent`) |
| **Acentos** | Case-sensitive y accent-sensitive | Unaccent integrado |
| **Persistencia** | Archivo plano (posible corrupción) | ACID con WAL |
| **Concurrencia** | Un proceso a la vez | Multi-usuario |

**Ventaja principal**: la búsqueda "niños huérfanos" en PostgreSQL FTS también encuentra "niño huérfano", "niñas huérfanas" gracias al stemming español.

**Desventaja principal**: requiere un servicio PostgreSQL adicional (más complejidad de infraestructura vs un simple CSV).

---

## 9. Arquitectura general (v6.0)

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                         │
│  ┌───────────┐ ┌───────────┐ ┌───────────────────┐  │
│  │ Noticias  │ │ Gráficos  │ │ Guardadas (ONG)   │  │
│  │ + Filtros │ │ Chart.js  │ │ localStorage      │  │
│  │ + Búsqueda│ │ 4 charts  │ │ Export CSV        │  │
│  └───────────┘ └───────────┘ └───────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │ REST API
┌──────────────────────┴──────────────────────────────┐
│                 FLASK (Gunicorn)                     │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ Auth    │ │ API REST │ │ Charts   │ │ Export  │ │
│  │ Argon2  │ │ /api/*   │ │ /api/    │ │ CSV     │ │
│  │ CSRF    │ │          │ │ charts/* │ │         │ │
│  └─────────┘ └──────────┘ └──────────┘ └─────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│             PIPELINE DE ANÁLISIS                     │
│  ┌────────┐ ┌────────┐ ┌───────┐ ┌───────────────┐  │
│  │ RSS    │ │ Scrap  │ │ Dedup │ │ México Filter │  │
│  │ Feed   │ │ +URL   │ │ cos   │ │ v6.0 weighted │  │
│  │ Parser │ │ Track  │ │ sim   │ │ 100+ indicat. │  │
│  └────┬───┘ └───┬────┘ └───┬───┘ └───────┬───────┘  │
│       └─────────┴──────────┴─────────────┘           │
│  ┌────────┐ ┌──────────┐ ┌───────────────────────┐   │
│  │ BETO   │ │ BERTopic │ │ Scoring biaxial       │   │
│  │ detect │ │ cluster  │ │ 55% fem + 45% NNA     │   │
│  └────────┘ └──────────┘ └───────────────────────┘   │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│               PERSISTENCIA                           │
│  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ PostgreSQL 16   │  │ CSV (fallback)           │   │
│  │ + FTS español   │  │ + seen_urls.json         │   │
│  │ + GIN index     │  │ + synonym_dictionary.json│   │
│  │ + unaccent      │  │                          │   │
│  └─────────────────┘  └──────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

---

## 10. Resumen de ventajas y desventajas

### Ventajas generales del sistema v6.0
1. **Detección semántica real** — BETO comprende contexto, no solo keywords
2. **Clustering automático** — BERTopic agrupa sin definir K manualmente
3. **FTS en español** — búsqueda con stemming y sin acentos
4. **Filtro geográfico inteligente** — puntaje ponderado con 100+ indicadores
5. **Sin re-scraping** — tracking de URLs reduce procesamiento redundante
6. **Visualizaciones** — tendencias y patrones visibles para toma de decisiones
7. **Funcionalidades ONG** — guardar, exportar y rastrear casos
8. **Seguridad reforzada** — Argon2id, CSRF, sin credenciales hardcodeadas, XSS fix
9. **Producción-ready** — Gunicorn, Docker multi-servicio, healthchecks

### Desventajas y limitaciones
1. **Recursos computacionales** — BETO + BERTopic + sentence-transformers requieren RAM significativa (~4GB+)
2. **Dependencia de CDN** — Chart.js y Font Awesome requieren internet
3. **Guardado local** — localStorage no sincroniza entre dispositivos/navegadores
4. **Lista de indicadores estática** — el filtro México necesita actualización manual
5. **Sin notificaciones push** — las ONGs deben revisar el dashboard manualmente
6. **Primera ejecución lenta** — descarga de modelos pre-entrenados (~1.5GB total)
7. **Sin soporte multiusuario avanzado** — todos los usuarios ven los mismos datos (no hay roles/permisos granulares)

---

*Documento generado automáticamente como parte de la auditoría y mejora del Sistema NNA v6.0*
