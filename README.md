# Sistema Inteligente para Identificación y Seguimiento de NNA

## Descripción

Sistema automatizado para detectar y analizar noticias sobre **feminicidios** que mencionen **víctimas indirectas (Niños, Niñas y Adolescentes — NNA)** en medios digitales mexicanos, utilizando Machine Learning y procesamiento de lenguaje natural.

El sistema recopila noticias de múltiples fuentes, aplica un **scoring de relevancia dual** (eje feminicidio + eje NNA), filtra automáticamente las noticias no relevantes, y presenta los resultados en un dashboard interactivo.

---

## Cambios Realizados (v3.0 — Reestructurado)

### Problema detectado en la versión anterior

La versión anterior del sistema **no filtraba por tema**: recolectaba TODAS las noticias de feeds RSS generales (política, economía, deportes, etc.) y solo post-hoc buscaba menciones de NNA. Esto causaba que la gran mayoría de noticias recolectadas fueran irrelevantes — no hablaban de feminicidios ni de víctimas indirectas.

**Problemas específicos:**
1. Los feeds RSS eran 100% generales (La Jornada política, Forbes, etc.) — ninguno especializado en género o seguridad.
2. No existía filtrado por feminicidio — se guardaba todo sin importar el tema.
3. La detección de NNA era unidimensional — solo buscaba si había menores, sin validar la condición dual (feminicidio + NNA).
4. TF-IDF, LDA y K-Means se aplicaban pero **no influían en la clasificación de relevancia**.
5. No había scoring numérico — solo un "Sí/No" binario para NNA.

### Qué se cambió y por qué

| Archivo | Cambio | Por qué mejora |
|---------|--------|----------------|
| **config.py** | +16 feeds RSS (medios de género + 6 queries Google News de "feminicidio + NNA"). Parámetros de scoring configurables. | Google News busca directamente "feminicidio niños huérfanos", trayendo noticias objetivo desde la fuente. Se eliminó Forbes (no publica notas de violencia de género) y se agregaron CIMAC Noticias y Luchadoras (especializados en género). |
| **collector.py** | Sistema de **scoring heurístico dual** con ~35 patrones regex ponderados. Cada noticia recibe `score_feminicidio` (0-1) y `score_nna` (0-1). Se filtran automáticamente noticias con score < 0.25. | Antes se guardaba TODO sin filtrar. Ahora se aplican patrones con pesos diferenciados (ej: "feminicidio" pesa 1.0, "violencia doméstica" pesa 0.5). Bonus multiplicativo ×1.35 cuando AMBOS ejes tienen señal, priorizando noticias que hablan de feminicidio Y mencionan NNA. |
| **analyzer.py** | Nuevo paso 7: **reclasificación TF-IDF**. Construye un "documento ideal" con vocabulario de dominio y calcula similitud coseno contra cada noticia. Score final = 60% heurístico + 40% TF-IDF. TF-IDF mejorado con n-gramas 1-3, `sublinear_tf`, stop words en español, vocabulario domain-boosted. | Antes el TF-IDF no influía en la clasificación. Ahora el score estadístico refuerza o corrige al heurístico. Los trigramas capturan frases como "violencia de género" o "menores de edad" que los unigramas pierden. `sublinear_tf` evita que palabras muy frecuentes dominen el vector. |
| **synonyms.py** | Diccionario expandido a 200+ términos en 8 categorías (orfandad, alertas de género, actores judiciales). Búsqueda con ranking por coincidencias ponderadas (título ×3). | La búsqueda ahora ordena por relevancia real en vez de devolver resultados desordenados. Nuevos términos capturan más variantes del lenguaje periodístico mexicano. |
| **routes.py** | API expone `score_feminicidio`, `score_nna`, `relevancia_final`, `clasificacion`. Nuevo filtro `/api/noticias?clasificacion=Alta`. | El dashboard puede filtrar por nivel de relevancia, mostrando primero las noticias más importantes. |
| **dashboard.html** | Tarjetas de Alta/Media relevancia, badges con color por nivel, desglose de scores (Fem%/NNA%), botones de filtro por clasificación, enlaces a fuente original. | El usuario ve de un vistazo qué tan relevante es cada noticia y puede filtrar por nivel. Las noticias de alta relevancia tienen borde rojo. |

### Algoritmos utilizados

| Algoritmo | Uso en el sistema |
|-----------|-------------------|
| **Scoring heurístico dual ponderado** | ~35 patrones regex con pesos [0-1] por eje (feminicidio/NNA). Función sigmoide `1 - 1/(1+w)` para normalizar acumulaciones. Bonus ×1.35 cuando ambos ejes tienen señal. Score compuesto: 55% feminicidio + 45% NNA. |
| **TF-IDF (sublinear, n-grams 1-3, domain-boosted)** | Vectorización con `sublinear_tf=True` para atenuar frecuencias extremas. N-gramas hasta trigramas capturan frases compuestas. Vocabulario inyectado con términos de dominio como documentos ficticios. Stop words en español personalizadas. |
| **Reclasificación TF-IDF (documento ideal)** | Se construye un documento artificial con los términos de dominio y se calcula similitud coseno contra cada noticia. Score final = 60% heurístico + 40% TF-IDF. Esto usa la estadística del corpus para refinar la clasificación heurística. |
| **LDA (Latent Dirichlet Allocation)** | Modelado de tópicos latentes para descubrir temas en el corpus filtrado. |
| **K-Means** | Clustering para agrupar noticias similares. Auto-ajuste del número de clusters según tamaño del corpus. |
| **Similitud coseno** | Detección de noticias duplicadas o relacionadas entre sí. |
| **Expansión de sinónimos** | Búsqueda con 200+ sinónimos en 8 categorías, con ranking por coincidencias ponderadas. |

### Pipeline de análisis (8 pasos)

```
1. Recolección RSS (22 fuentes + Google News)
       ↓
2. Scoring dual por noticia (Feminicidio × NNA)
       ↓
3. Filtrado (descarta score < 0.25)
       ↓
4. Almacenamiento CSV intermedio
       ↓
5. TF-IDF (domain-boosted, n-grams 1-3, sublinear)
       ↓
6. LDA (modelado de tópicos)
       ↓
7. K-Means (clustering)
       ↓
8. Similitud coseno (duplicados)
       ↓
9. Reclasificación TF-IDF (doc ideal) → relevancia_final
       ↓
10. Resultados ordenados por relevancia final
```

---

## Inicio Rápido (Docker)

### Prerrequisitos
- Docker Desktop
- Puerto 5000 disponible

### Ejecutar

```bash
# 1. Copiar y configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores (SECRET_KEY, POSTGRES_PASSWORD)

# 2. Iniciar todo el sistema
docker-compose up -d --build

# 3. Acceder al dashboard
# http://localhost:5000
# Usuario: admin / Admin_NNA_2026!
```

### Comandos útiles

```bash
docker-compose logs -f           # Logs en vivo
docker-compose ps                # Estado de servicios
docker-compose down              # Detener
docker-compose up --build -d     # Reconstruir e iniciar
```

## API REST

| Método | Endpoint                           | Descripción                            |
|--------|------------------------------------|----------------------------------------|
| GET    | `/api/stats`                       | Estadísticas generales + relevancia    |
| GET    | `/api/noticias`                    | Listado paginado (ordenado por score)  |
| GET    | `/api/noticias?clasificacion=Alta` | Filtrar por relevancia Alta/Media/Baja |
| GET    | `/api/noticias?only_nna=true`      | Solo noticias que mencionan NNA        |
| GET    | `/api/search?q=…`                  | Búsqueda con sinónimos                 |
| GET    | `/api/analyze`                     | Ejecutar análisis completo             |
| GET    | `/api/export/csv`                  | Descargar datos                        |
| GET    | `/health`                          | Estado del sistema                     |

## Arquitectura

```
docker-compose
├── nna-postgres   → PostgreSQL 16 (autenticación)
├── nna-analyzer   → Recolección y análisis programado
└── nna-webapp     → Interfaz web Flask (puerto 5000)
```

## Estructura del Proyecto

```
├── app/                        # Aplicación web Flask
│   ├── __init__.py             # Factory create_app()
│   ├── models.py               # Modelo User (Argon2id)
│   ├── auth/                   # Blueprint de autenticación
│   │   ├── forms.py            # Formularios WTForms
│   │   └── routes.py           # Login / registro / logout
│   ├── main/                   # Blueprint principal
│   │   └── routes.py           # Dashboard + API REST
│   └── templates/
│       ├── dashboard.html      # Dashboard interactivo
│       └── auth/
│           ├── login.html
│           └── register.html
├── src/                        # Lógica de análisis
│   ├── analysis/
│   │   ├── analyzer.py         # Pipeline NLP (8 pasos + scoring dual)
│   │   └── synonyms.py         # Diccionario sinónimos (200+ términos)
│   └── collection/
│       └── collector.py        # Recolector RSS + scoring dual
├── config.py                   # Configuración + parámetros de scoring
├── wsgi.py                     # Punto de entrada Flask
├── scheduler.py                # Servicio de recolección programada
├── data/                       # Datos CSV y metadatos
├── logs/                       # Logs de aplicación
├── docs/                       # Documentación del desarrollo
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Tecnologías

| Categoría        | Tecnologías                                        |
|------------------|----------------------------------------------------|
| Análisis / ML    | pandas, scikit-learn, numpy                        |
| Web Scraping     | requests, beautifulsoup4, lxml                     |
| Web App          | Flask, Flask-Login, Flask-WTF, Flask-SQLAlchemy    |
| Seguridad        | Argon2-cffi, CSRF, sesiones seguras                |
| Base de datos    | PostgreSQL 16, SQLAlchemy                          |
| Infraestructura  | Docker, docker-compose                             |
| Automatización   | schedule                                           |

## Fuentes RSS Monitoreadas (22 fuentes)

**Medios generales (14):**
La Jornada (Política + Estados), Proceso, Aristegui Noticias, Animal Político,
Sin Embargo, El Sol de México, El Financiero, El Universal, Milenio,
Excélsior, Reporte Índigo, Pie de Página, Contralínea

**Medios especializados en género (2):**
CIMAC Noticias, Luchadoras

**Google News — queries específicas (6):**
- feminicidio México
- feminicidio hijos huérfanos
- feminicidio niños niñas
- orfandad feminicidio menores
- "víctimas indirectas" feminicidio
- feminicidio menores huérfanos

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
```
