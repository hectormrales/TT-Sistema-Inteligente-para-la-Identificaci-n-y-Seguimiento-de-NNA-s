# 🛡️ Sistema Inteligente para Identificación y Seguimiento de NNA# Sistema Inteligente para la Identificación y Seguimiento de NNA



**Trabajo Terminal 1 - ESIME Zacatenco**  **Trabajo Terminal 1**  

**Instituto Politécnico Nacional****ESIME Zacatenco - Instituto Politécnico Nacional**



[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)[![Versión](https://img.shields.io/badge/version-2.0.0-green.svg)]()

[![Flask](https://img.shields.io/badge/flask-3.0.3-black.svg)](https://flask.palletsprojects.com/)[![Estado](https://img.shields.io/badge/estado-producción-brightgreen.svg)]()

[![scikit-learn](https://img.shields.io/badge/sklearn-1.4.2-orange.svg)](https://scikit-learn.org/)

---

---

## 📋 Descripción

## 📋 Descripción

Sistema de análisis de noticias para identificar y monitorear casos de **feminicidios que dejan a niñas, niños y adolescentes (NNA) en situación de orfandad** en México. Utiliza técnicas de Machine Learning y NLP para:

Sistema automatizado de Machine Learning para la **detección, clasificación y seguimiento** de noticias sobre feminicidios con víctimas niñas, niños y adolescentes (NNA) en México.

- ✅ Recolección automatizada de noticias desde medios especializados

### ✨ Características Principales- ✅ Detección especializada de feminicidios con víctimas indirectas (NNA)

- ✅ Análisis de texto con TF-IDF, LDA y DBSCAN

- 🔍 **Recolección Inteligente**: RSS (10 feeds) + Google News (150) + Histórico (250)- ✅ Clasificación por prioridad y confianza

- 🧠 **Machine Learning**: TF-IDF → LDA → DBSCAN- ✅ Dashboard web para visualización de resultados

- 🎯 **Priorización Automática**: ALTA, MEDIA, BAJA, IRRELEVANTE

- 🔄 **Detección de Duplicados**: 75% similitud entre medios---

- 📊 **Dashboard Web**: Visualización en tiempo real

- 🔎 **Búsqueda Inteligente**: Multi-campo con expansión de sinónimos## ✨ Novedades v2.0.0 (Noviembre 2025)

- 📤 **Exportación**: CSV con UTF-8-sig

### Mejoras de Calidad de Código

---- **Type hints** en ~60% del código (antes ~5%)

- **Logging profesional** con módulo `logging` 

## 🚀 Inicio Rápido- **Manejo robusto de errores** con retry logic (3 intentos)

- **Imports opcionales** con graceful degradation

### Docker (Recomendado)- **Rutas multiplataforma** compatible Windows/Linux/Docker

- **Configuración centralizada** en `config.py` (130+ líneas)

```bash- **Suite de tests** consolidada en `tests/`

# Clonar repositorio- **Documentación completa** con docstrings

git clone https://github.com/hectormrales/TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s.git

cd TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s### Funcionalidades Core Preservadas

- ✅ 8 RSS feeds especializados en género y feminicidios

# Iniciar contenedores- ✅ Búsqueda complementaria en Google News

docker-compose up -d- ✅ Detector con 40+ patrones regex

- ✅ Análisis ML: TF-IDF → LDA → DBSCAN

# Acceder al dashboard- ✅ Dashboard Flask con API REST

# http://localhost:5000- ✅ Exportación CSV

```

---

### Instalación Local

## 🚀 Inicio Rápido

```bash

# Crear entorno virtual### Opción 1: Docker (Recomendado)

python -m venv venv

venv\Scripts\activate  # Windows```bash

source venv/bin/activate  # Linux/Mac# Clonar repositorio

git clone https://github.com/hectormrales/TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s.git

# Instalar dependenciascd TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s

pip install -r requirements.txt

# Iniciar con Docker

# Ejecutar aplicacióndocker-compose up -d

python app_docker.py

```# Verificar estado

docker-compose ps

---

# Acceder al dashboard

## 🏗️ Arquitectura# http://localhost:5000

```

### Pipeline de Machine Learning

### Opción 2: Instalación Local

```

┌─────────────────────┐```bash

│  RECOLECCIÓN        │# Crear entorno virtual

│  - RSS (10 feeds)   │python -m venv venv

│  - Google News      │

│  - Histórico 6m     │# Activar entorno (Windows)

└──────────┬──────────┘venv\Scripts\activate

           │

           ▼# Activar entorno (Linux/Mac)

┌─────────────────────┐source venv/bin/activate

│  DETECCIÓN          │

│  - Feminicidios     │# Instalar dependencias

│  - Menciones NNA    │pip install -r requirements.txt

│  - 17 Exclusiones   │

└──────────┬──────────┘# Ejecutar dashboard

           │python app_docker.py

           ▼

┌─────────────────────┐# Acceder a: http://localhost:5000

│  VECTORIZACIÓN      │```

│  TF-IDF (3000 feat) │

└──────────┬──────────┘---

           │

           ▼## 🧪 Ejecutar Tests

┌─────────────────────┐

│  MODELADO           │```bash

│  - LDA (8 topics)   │# Tests de recolección

│  - DBSCAN Cluster   │python tests/test_collector.py

└──────────┬──────────┘

           │# Tests de análisis ML

           ▼python tests/test_analyzer.py

┌─────────────────────┐

│  CLASIFICACIÓN      │# Ejecutar todos los tests

│  Prioridades + Dups │python -m pytest tests/  # (requiere pytest instalado)

└──────────┬──────────┘```

           │

           ▼**Resultado esperado:**

┌─────────────────────┐```

│  DASHBOARD WEB      │✓ TEST: Detector de Feminicidios

│  + API REST         │✓ TEST: Recolección desde RSS Feeds (10 noticias)

└─────────────────────┘✓ TEST: Recolección desde Google News (28 noticias)

```✓ TEST: Recolección Completa (95 noticias)

  - 29.5% feminicidios

---  - 14.7% noticias objetivo

  - 1 noticia ALTA prioridad

## 📁 Estructura del Proyecto```



```---

TT-1-Sistema-NNA/

├── app/## 📁 Estructura del Proyecto

│   ├── __init__.py

│   └── templates/```

│       └── dashboard_docker.html    # Dashboard webTT-1-Sistema-NNA/

├── src/├── app/

│   ├── analysis/│   └── templates/

│   │   ├── simplified_analyzer.py   # Pipeline ML completo│       └── dashboard_docker.html       # Template del dashboard

│   │   └── synonym_dictionary.py    # 147 sinónimos├── src/

│   └── collection/│   ├── collection/

│       ├── data_collector.py        # Recolector principal│   │   ├── data_collector.py          # Recolección RSS + Google News

│       ├── feminicide_detector.py   # Detector + 17 exclusiones│   │   ├── feminicide_detector.py     # Detector especializado (40+ patrones)

│       └── historical_scraper.py    # Búsqueda histórica│   │   └── historical_scraper.py      # Scraper histórico (opcional)

├── data/                            # CSV generados│   └── analysis/

├── logs/                            # Logs del sistema│       ├── simplified_analyzer.py     # Pipeline ML completo

├── tests/                           # Tests unitarios│       └── synonym_dictionary.py      # Diccionario de sinónimos

├── app_docker.py                    # App Flask principal├── tests/

├── config.py                        # Configuración│   ├── test_collector.py              # Tests de recolección

├── docker-compose.yml               # Orquestación│   └── test_analyzer.py               # Tests de análisis ML

├── Dockerfile                       # Imagen Docker├── data/                               # Datos generados

└── requirements.txt                 # Dependencias├── logs/                               # Logs del sistema

```├── config.py                           # ⭐ Configuración centralizada

├── app_docker.py                       # Flask dashboard

---├── demo_docker.py                      # Demo containerizado

├── requirements.txt                    # Dependencias Python

## ⚙️ Configuración (`config.py`)├── docker-compose.yml                  # Configuración Docker

├── Dockerfile                          # Imagen Docker

### Parámetros de Machine Learning└── README.md                           # Este archivo

```

```python

# TF-IDF---

TFIDF_MAX_FEATURES = 3000

TFIDF_MIN_DF = 1## ⚙️ Configuración

TFIDF_MAX_DF = 0.8

TFIDF_NGRAM_RANGE = (1, 2)### Archivo `config.py`



# DBSCAN ClusteringConfiguración centralizada de todos los parámetros del sistema:

DBSCAN_EPS = 0.8              # Distancia máxima

DBSCAN_MIN_SAMPLES = 2        # Mínimo por cluster```python

DBSCAN_METRIC = 'cosine'# RSS Feeds especializados

RSS_FEEDS = [

# LDA Topic Modeling    'https://cimacnoticias.com.mx/feed/',      # CIMAC

LDA_N_COMPONENTS = 8          # Número de tópicos    'https://www.semmexico.mx/feed/',          # SEM México

LDA_RANDOM_STATE = 42    'https://www.jornada.com.mx/rss/estados.xml',  # La Jornada

LDA_MAX_ITER = 10    # ... 5 feeds más

]

# Detección de Duplicados

SIMILARITY_THRESHOLD = 0.75   # 75% similitud# Parámetros de Machine Learning

```TFIDF_CONFIG = {

    'max_features': 3000,

### Fuentes de Datos    'min_df': 1,

    'max_df': 0.8,

```python    'ngram_range': (1, 2)

# RSS Feeds (10 activos)}

RSS_FEEDS = [

    'https://cimacnoticias.com.mx/feed/',DBSCAN_CONFIG = {

    'https://www.semmexico.mx/feed/',    'eps': 0.6,              # Similitud > 40%

    'https://www.jornada.com.mx/rss/estados.xml',    'min_samples': 2,

    # ... 7 feeds más    'metric': 'cosine'

]}



# Google NewsLDA_CONFIG = {

GNEWS_RESULTS = 150    'n_components': 6,       # 6 tópicos

GNEWS_LANG = 'es'    'random_state': 42

GNEWS_COUNTRY = 'MX'}

```

# Búsqueda Histórica

HISTORICAL_MONTHS = 6         # 6 meses atrás### Variables de Entorno (Opcional)

HISTORICAL_RESULTS = 50       # Por query

``````bash

# Para deployment en producción

---export FLASK_PORT=5000

export FLASK_HOST=0.0.0.0

## 🎯 Sistema de Detecciónexport FLASK_DEBUG=False

```

### Patrones de Feminicidio

---

El sistema utiliza **40+ patrones regex** clasificados en:

## 🔍 Detector de Feminicidios

#### 1. Términos de Feminicidio (Peso: 40%)

- feminicidio, femicidio, asesinato de mujer### Categorías de Patrones

- madre hallada muerta, violencia feminicida

- crimen de género, muerte violenta de mujerEl detector (`FeminicideDetector`) utiliza **40+ patrones regex** en 3 categorías:



#### 2. Menciones de NNA (Peso: 20%)#### 1. **Patrones de Feminicidio** (peso: 40%)

- niños, niñas, adolescentes, menores```

- hijos, bebés, infantes, recién nacidosfeminicidio, mujer asesinada, madre hallada muerta,

violencia feminicida, crimen de género, etc.

#### 3. Indicadores de Orfandad (Peso: 40%)```

- huérfanos, orfandad, hijos quedan sin madre

- víctimas indirectas, DIF se hace cargo#### 2. **Patrones de NNA** (peso: 20%)

```

### Patrones de Exclusión (17 filtros)hijos, menores de edad, niños, adolescentes, bebés,

infantes, recién nacidos, etc.

```python```

EXCLUSION_PATTERNS = [

    r'\bconcentra\s+(la\s+)?cuarta\s+parte',    # Estadísticas#### 3. **Patrones de Orfandad** (peso: 30% + 10% bonus)

    r'\bestadística[s]?\s+(de|sobre)',          # Reportes```

    r'\b\d+%\s+(de\s+las|son)',                 # Porcentajeshuérfanos, orfandad, hijos quedan, sin madre,

    r'\bdatos?\s+(del|de\s+la)\s+INEGI',        # Datos oficialesvíctimas indirectas, DIF se hace cargo, etc.

    r'\btrata\s+de\s+(personas|blancas)',       # Trata (≠ feminicidio)```

    r'\bprograma\s+(social|de\s+gobierno)',     # Programas

    r'\bcampa[ñ]a\s+de\s+concientizaci[óo]n',   # Campañas### Sistema de Clasificación

    # ... 10 patrones más

]```python

```# Ejemplo de resultado

{

### Clasificación de Prioridad    'is_feminicide': True,

    'has_children': True,

| Prioridad | Criterios | Confianza |    'has_orphans': True,

|-----------|-----------|-----------|    'is_target_news': True,      # ⭐ Noticia objetivo

| **ALTA** | Feminicidio + NNA + Orfandad explícita | ≥ 70% |    'confidence': 0.80,          # 80% confianza

| **MEDIA** | Feminicidio + NNA | 40-69% |    'priority': 'ALTA'           # ALTA/MEDIA/BAJA/IRRELEVANTE

| **BAJA** | Indicios de feminicidio o NNA | 20-39% |}

| **IRRELEVANTE** | No relacionado o estadísticas | < 20% |```



---**Prioridades:**

- **ALTA** (≥70%): Feminicidio confirmado + NNA + orfandad explícita

## 📊 API REST- **MEDIA** (≥40%): Feminicidio + NNA, sin orfandad explícita

- **BAJA** (≥20%): Indicios de feminicidio o NNA

### Endpoints Disponibles- **IRRELEVANTE** (<20%): No relacionado



#### GET `/`---

Dashboard principal

## 🧠 Pipeline de Análisis ML

#### GET `/api/stats`

Estadísticas generales```

```json1. Recolección

{   ├─ RSS Feeds (8 fuentes) → 60-70 noticias

  "total_noticias": 281,   └─ Google News          → 25-30 noticias

  "noticias_nna": 126,          ↓

  "clusters": 7,2. Detección (FeminicideDetector)

  "topics": 8,   └─ 40+ patrones regex → Filtrado

  "ultima_actualizacion": "2025-11-19 00:20:28"          ↓

}3. Vectorización (TF-IDF)

```   └─ 3000 features → Matriz (N, 3000)

          ↓

#### GET `/api/noticias`4. Modelado de Tópicos (LDA)

Lista paginada de noticias   └─ 6 tópicos → Clasificación temática

          ↓

**Parámetros:**5. Clustering (DBSCAN)

- `page`: Número de página (default: 1)   └─ eps=0.6, min_samples=2 → Grupos

- `per_page`: Resultados por página (default: 10)          ↓

- `only_nna`: Filtrar solo NNA (default: false)6. Similitud Coseno

   └─ Matriz de similitud → Casos relacionados

**Respuesta:**          ↓

```json7. Exportación

{   └─ CSV + Dashboard Web

  "noticias": [...],```

  "page": 1,

  "total_pages": 13,---

  "total": 126

}## 📊 API REST

```

### Endpoints Disponibles

#### GET `/api/search?q=<query>`

Búsqueda inteligente```bash

# Estadísticas generales

**Características:**GET /api/stats

- Busca en: título, contenido, fuenteResponse: {

- Expande sinónimos automáticamente  "total_noticias": 95,

- Ordena por prioridad  "noticias_nna": 14,

- Límite: 50 resultados  "clusters": 1,

  "topics": 6,

**Ejemplo:**  "similitud_promedio": 0.154

```bash}

curl "http://localhost:5000/api/search?q=feminicidio"

```# Listado de noticias (con paginación)

GET /api/noticias?page=1&per_page=10&only_nna=true

#### POST `/api/analyze`

Ejecuta análisis completo# Búsqueda con sinónimos

GET /api/search?q=feminicidio

**Respuesta:**

```json# Exportar CSV

{GET /api/export/csv

  "success": true,```

  "noticias_recolectadas": 238,

  "noticias_nna": 126,---

  "clusters": 7,

  "topics": 8## 🐳 Docker

}

```### Servicios



#### GET `/api/export/csv````yaml

Exporta datos a CSV (UTF-8-sig)services:

  nna-analyzer:    # Procesador de análisis

---    build: .

    command: python demo_docker.py full

## 🔍 Búsqueda Inteligente    

  nna-webapp:      # Dashboard web

### Diccionario de Sinónimos (147 términos)    build: .

    command: python app_docker.py

```python    ports:

{      - "5000:5000"

  "feminicidio": ["femicidio", "asesinato de mujer", "crimen de género"],```

  "niños": ["menores", "NNA", "infantes", "adolescentes"],

  "huérfanos": ["orfandad", "sin madre", "víctimas indirectas"],### Comandos Útiles

  # ... 144 términos más

}```bash

```# Ver logs

docker-compose logs -f nna-webapp

### Ejemplos de Búsqueda

# Reiniciar servicios

```bashdocker-compose restart

# Buscar por ubicación

/api/search?q=CDMX# Detener sistema

docker-compose down

# Buscar por fuente

/api/search?q=Infobae# Reconstruir contenedores

docker-compose up -d --build

# Buscar por nombre (si aparece en contenido)```

/api/search?q=Montserrat

---

# Buscar término genérico (expande sinónimos)

/api/search?q=feminicidio## 📈 Resultados Esperados

# Encuentra: feminicidio, femicidio, asesinato de mujer, etc.

```### Métricas de Prueba (Test Real)



---```

Total noticias: 95

## 🧪 Testing├─ Feminicidios: 28 (29.5%)

├─ Noticias objetivo: 14 (14.7%)

```bash└─ Prioridad ALTA: 1

# Ejecutar tests

python -m pytest tests/ -vClustering:

├─ Método: DBSCAN

# Test específico de recolección├─ Clusters: 1

python tests/test_collector.py├─ Outliers: 92

└─ Silhouette: 0.15

# Test de análisis ML

python tests/test_analyzer.pyTopics LDA: 6 tópicos descubiertos

```Similitud promedio: 0.154

```

**Resultado Esperado:**

```### Ejemplo de Noticia ALTA Prioridad

✓ TEST: Detector de Feminicidios

✓ TEST: Recolección RSS (10 noticias)```

✓ TEST: Recolección Google News (28 noticias)Título: "Edomex otorga apoyo económico a niños y adolescentes 

✓ TEST: Recolección Completa (95+ noticias)         en orfandad por feminicidio"

✓ TEST: Análisis ML (TF-IDF + LDA + DBSCAN)         

```Fuente: Google News

Confianza: 80%

---Prioridad: ALTA

Motivo: ✅ Feminicidio + ✅ NNA + ✅ Orfandad explícita

## 🐳 Docker```



### Servicios---



```yaml## ⚠️ Limitaciones Conocidas

nna-analyzer:    # Análisis programado (cada 24h)

  - Recolecta noticias### Feeds RSS con Problemas

  - Ejecuta pipeline ML- ❌ `animalpolitico.com/category/seguridad/feed/` - Error 404

  - Guarda resultados- ❌ `proceso.com.mx/seccion/nacional/feed` - Error 404



nna-webapp:      # Dashboard web**Solución implementada:** Retry logic (3 intentos) + logging de errores

  - Flask app

  - API REST### Imports Opcionales

  - Puerto 5000- `schedule` - Requerido solo para modo planificador

```- `flask_cors` - Opcional, CORS se habilita si está disponible



### Comandos Útiles**No afectan funcionalidad principal.**



```bash---

# Ver logs en tiempo real

docker-compose logs -f nna-webapp## 🤝 Contribuir



# Reiniciar servicios```bash

docker-compose restart# Fork del repositorio

git clone https://github.com/TU_USUARIO/TT-1-Sistema-NNA.git

# Detener todo

docker-compose down# Crear rama de feature

git checkout -b feature/nueva-funcionalidad

# Reconstruir

docker-compose up -d --build# Hacer commits

git commit -am "Descripción del cambio"

# Ver estado

docker-compose ps# Push y Pull Request

```git push origin feature/nueva-funcionalidad

```

---

---

## 📈 Métricas de Rendimiento

## 📚 Documentación Adicional

### Recolección

- **Tiempo**: 15-25 minutos- **[DEPURACION_OPTIMIZACION.md](./DEPURACION_OPTIMIZACION.md)** - Análisis detallado de mejoras v2.0

- **Fuentes**: 3 (RSS, Google News, Histórico)- **[RESUMEN_DEPURACION.md](./RESUMEN_DEPURACION.md)** - Resumen ejecutivo de cambios

- **Noticias/ciclo**: ~280-300- **[EXPLICACION_TECNICA_SISTEMA.md](./EXPLICACION_TECNICA_SISTEMA.md)** - Explicación técnica completa (150+ páginas)



### Machine Learning---

- **Silhouette Score**: ~0.48 (Bueno)

- **Perplexity LDA**: ~870,000## 📄 Licencia

- **Precisión NNA**: ~95%

- **Detección duplicados**: 75% umbralEste proyecto es parte de un Trabajo Terminal académico del IPN.



### Sistema---

- **Memoria**: ~200MB Docker

- **CPU**: Picos 80% durante análisis## 👥 Autores

- **Análisis automático**: Cada 24 horas

**Héctor Morales**  

---Trabajo Terminal 1  

ESIME Zacatenco - Instituto Politécnico Nacional

## 🔐 Seguridad

---

- ✅ Sin credenciales hardcodeadas

- ✅ Usuario no privilegiado en Docker## 📞 Contacto

- ✅ Validación de entrada en API

- ✅ Manejo robusto de erroresPara dudas o sugerencias sobre este Trabajo Terminal:

- ✅ Logs estructurados- Email: [Contacto IPN]

- ✅ UTF-8-sig para evitar corrupción de datos- GitHub: [@hectormrales](https://github.com/hectormrales)



------



## 🤝 Contribuciones**Versión**: 2.0.0  

**Última actualización**: Noviembre 2025  

Este es un **proyecto académico** (Trabajo Terminal IPN).**Estado**: ✅ Producción


Para contribuir:

1. Fork el proyecto
2. Crea rama (`git checkout -b feature/nueva-funcionalidad`)
3. Commit (`git commit -m 'Add: nueva funcionalidad'`)
4. Push (`git push origin feature/nueva-funcionalidad`)
5. Pull Request

---

## 📝 Documentación Adicional

- **COMO_FUNCIONA_EL_SISTEMA.md** - Explicación técnica detallada
- **config.py** - Configuración completa del sistema
- **tests/** - Suite de tests con ejemplos

---

## ⚠️ Nota Importante

Este sistema maneja información **sensible sobre violencia de género**.  
Se recomienda **uso responsable y ético** de los datos recolectados.

---

## 👥 Autores

**Héctor Morales**  
Trabajo Terminal 1  
ESIME Zacatenco - Instituto Politécnico Nacional

---

## 🙏 Agradecimientos

- Instituto Politécnico Nacional
- Fuentes: SemMéxico, CIMAC Noticias, Animal Político
- Comunidad de Machine Learning y NLP

---

## 📞 Soporte

**GitHub Issues:**  
[Reportar Bug/Feature](https://github.com/hectormrales/TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s/issues)

---

**Versión:** 3.0.0  
**Última Actualización:** 19 de noviembre de 2025  
**Estado:** ✅ Producción
