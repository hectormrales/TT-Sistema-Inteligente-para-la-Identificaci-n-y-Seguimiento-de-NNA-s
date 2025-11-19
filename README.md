# Sistema Inteligente para la Identificación y Seguimiento de NNA

**Trabajo Terminal 1**  
**ESIME Zacatenco - Instituto Politécnico Nacional**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Versión](https://img.shields.io/badge/version-2.0.0-green.svg)]()
[![Estado](https://img.shields.io/badge/estado-producción-brightgreen.svg)]()

---

## 📋 Descripción

Sistema de análisis de noticias para identificar y monitorear casos de **feminicidios que dejan a niñas, niños y adolescentes (NNA) en situación de orfandad** en México. Utiliza técnicas de Machine Learning y NLP para:

- ✅ Recolección automatizada de noticias desde medios especializados
- ✅ Detección especializada de feminicidios con víctimas indirectas (NNA)
- ✅ Análisis de texto con TF-IDF, LDA y DBSCAN
- ✅ Clasificación por prioridad y confianza
- ✅ Dashboard web para visualización de resultados

---

## ✨ Novedades v2.0.0 (Noviembre 2025)

### Mejoras de Calidad de Código
- **Type hints** en ~60% del código (antes ~5%)
- **Logging profesional** con módulo `logging` 
- **Manejo robusto de errores** con retry logic (3 intentos)
- **Imports opcionales** con graceful degradation
- **Rutas multiplataforma** compatible Windows/Linux/Docker
- **Configuración centralizada** en `config.py` (130+ líneas)
- **Suite de tests** consolidada en `tests/`
- **Documentación completa** con docstrings

### Funcionalidades Core Preservadas
- ✅ 8 RSS feeds especializados en género y feminicidios
- ✅ Búsqueda complementaria en Google News
- ✅ Detector con 40+ patrones regex
- ✅ Análisis ML: TF-IDF → LDA → DBSCAN
- ✅ Dashboard Flask con API REST
- ✅ Exportación CSV

---

## 🚀 Inicio Rápido

### Opción 1: Docker (Recomendado)

```bash
# Clonar repositorio
git clone https://github.com/hectormrales/TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s.git
cd TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s

# Iniciar con Docker
docker-compose up -d

# Verificar estado
docker-compose ps

# Acceder al dashboard
# http://localhost:5000
```

### Opción 2: Instalación Local

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno (Windows)
venv\Scripts\activate

# Activar entorno (Linux/Mac)
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar dashboard
python app_docker.py

# Acceder a: http://localhost:5000
```

---

## 🧪 Ejecutar Tests

```bash
# Tests de recolección
python tests/test_collector.py

# Tests de análisis ML
python tests/test_analyzer.py

# Ejecutar todos los tests
python -m pytest tests/  # (requiere pytest instalado)
```

**Resultado esperado:**
```
✓ TEST: Detector de Feminicidios
✓ TEST: Recolección desde RSS Feeds (10 noticias)
✓ TEST: Recolección desde Google News (28 noticias)
✓ TEST: Recolección Completa (95 noticias)
  - 29.5% feminicidios
  - 14.7% noticias objetivo
  - 1 noticia ALTA prioridad
```

---

## 📁 Estructura del Proyecto

```
TT-1-Sistema-NNA/
├── app/
│   └── templates/
│       └── dashboard_docker.html       # Template del dashboard
├── src/
│   ├── collection/
│   │   ├── data_collector.py          # Recolección RSS + Google News
│   │   ├── feminicide_detector.py     # Detector especializado (40+ patrones)
│   │   └── historical_scraper.py      # Scraper histórico (opcional)
│   └── analysis/
│       ├── simplified_analyzer.py     # Pipeline ML completo
│       └── synonym_dictionary.py      # Diccionario de sinónimos
├── tests/
│   ├── test_collector.py              # Tests de recolección
│   └── test_analyzer.py               # Tests de análisis ML
├── data/                               # Datos generados
├── logs/                               # Logs del sistema
├── config.py                           # ⭐ Configuración centralizada
├── app_docker.py                       # Flask dashboard
├── demo_docker.py                      # Demo containerizado
├── requirements.txt                    # Dependencias Python
├── docker-compose.yml                  # Configuración Docker
├── Dockerfile                          # Imagen Docker
└── README.md                           # Este archivo
```

---

## ⚙️ Configuración

### Archivo `config.py`

Configuración centralizada de todos los parámetros del sistema:

```python
# RSS Feeds especializados
RSS_FEEDS = [
    'https://cimacnoticias.com.mx/feed/',      # CIMAC
    'https://www.semmexico.mx/feed/',          # SEM México
    'https://www.jornada.com.mx/rss/estados.xml',  # La Jornada
    # ... 5 feeds más
]

# Parámetros de Machine Learning
TFIDF_CONFIG = {
    'max_features': 3000,
    'min_df': 1,
    'max_df': 0.8,
    'ngram_range': (1, 2)
}

DBSCAN_CONFIG = {
    'eps': 0.6,              # Similitud > 40%
    'min_samples': 2,
    'metric': 'cosine'
}

LDA_CONFIG = {
    'n_components': 6,       # 6 tópicos
    'random_state': 42
}
```

### Variables de Entorno (Opcional)

```bash
# Para deployment en producción
export FLASK_PORT=5000
export FLASK_HOST=0.0.0.0
export FLASK_DEBUG=False
```

---

## 🔍 Detector de Feminicidios

### Categorías de Patrones

El detector (`FeminicideDetector`) utiliza **40+ patrones regex** en 3 categorías:

#### 1. **Patrones de Feminicidio** (peso: 40%)
```
feminicidio, mujer asesinada, madre hallada muerta,
violencia feminicida, crimen de género, etc.
```

#### 2. **Patrones de NNA** (peso: 20%)
```
hijos, menores de edad, niños, adolescentes, bebés,
infantes, recién nacidos, etc.
```

#### 3. **Patrones de Orfandad** (peso: 30% + 10% bonus)
```
huérfanos, orfandad, hijos quedan, sin madre,
víctimas indirectas, DIF se hace cargo, etc.
```

### Sistema de Clasificación

```python
# Ejemplo de resultado
{
    'is_feminicide': True,
    'has_children': True,
    'has_orphans': True,
    'is_target_news': True,      # ⭐ Noticia objetivo
    'confidence': 0.80,          # 80% confianza
    'priority': 'ALTA'           # ALTA/MEDIA/BAJA/IRRELEVANTE
}
```

**Prioridades:**
- **ALTA** (≥70%): Feminicidio confirmado + NNA + orfandad explícita
- **MEDIA** (≥40%): Feminicidio + NNA, sin orfandad explícita
- **BAJA** (≥20%): Indicios de feminicidio o NNA
- **IRRELEVANTE** (<20%): No relacionado

---

## 🧠 Pipeline de Análisis ML

```
1. Recolección
   ├─ RSS Feeds (8 fuentes) → 60-70 noticias
   └─ Google News          → 25-30 noticias
          ↓
2. Detección (FeminicideDetector)
   └─ 40+ patrones regex → Filtrado
          ↓
3. Vectorización (TF-IDF)
   └─ 3000 features → Matriz (N, 3000)
          ↓
4. Modelado de Tópicos (LDA)
   └─ 6 tópicos → Clasificación temática
          ↓
5. Clustering (DBSCAN)
   └─ eps=0.6, min_samples=2 → Grupos
          ↓
6. Similitud Coseno
   └─ Matriz de similitud → Casos relacionados
          ↓
7. Exportación
   └─ CSV + Dashboard Web
```

---

## 📊 API REST

### Endpoints Disponibles

```bash
# Estadísticas generales
GET /api/stats
Response: {
  "total_noticias": 95,
  "noticias_nna": 14,
  "clusters": 1,
  "topics": 6,
  "similitud_promedio": 0.154
}

# Listado de noticias (con paginación)
GET /api/noticias?page=1&per_page=10&only_nna=true

# Búsqueda con sinónimos
GET /api/search?q=feminicidio

# Exportar CSV
GET /api/export/csv
```

---

## 🐳 Docker

### Servicios

```yaml
services:
  nna-analyzer:    # Procesador de análisis
    build: .
    command: python demo_docker.py full
    
  nna-webapp:      # Dashboard web
    build: .
    command: python app_docker.py
    ports:
      - "5000:5000"
```

### Comandos Útiles

```bash
# Ver logs
docker-compose logs -f nna-webapp

# Reiniciar servicios
docker-compose restart

# Detener sistema
docker-compose down

# Reconstruir contenedores
docker-compose up -d --build
```

---

## 📈 Resultados Esperados

### Métricas de Prueba (Test Real)

```
Total noticias: 95
├─ Feminicidios: 28 (29.5%)
├─ Noticias objetivo: 14 (14.7%)
└─ Prioridad ALTA: 1

Clustering:
├─ Método: DBSCAN
├─ Clusters: 1
├─ Outliers: 92
└─ Silhouette: 0.15

Topics LDA: 6 tópicos descubiertos
Similitud promedio: 0.154
```

### Ejemplo de Noticia ALTA Prioridad

```
Título: "Edomex otorga apoyo económico a niños y adolescentes 
         en orfandad por feminicidio"
         
Fuente: Google News
Confianza: 80%
Prioridad: ALTA
Motivo: ✅ Feminicidio + ✅ NNA + ✅ Orfandad explícita
```

---

## ⚠️ Limitaciones Conocidas

### Feeds RSS con Problemas
- ❌ `animalpolitico.com/category/seguridad/feed/` - Error 404
- ❌ `proceso.com.mx/seccion/nacional/feed` - Error 404

**Solución implementada:** Retry logic (3 intentos) + logging de errores

### Imports Opcionales
- `schedule` - Requerido solo para modo planificador
- `flask_cors` - Opcional, CORS se habilita si está disponible

**No afectan funcionalidad principal.**

---

## 🤝 Contribuir

```bash
# Fork del repositorio
git clone https://github.com/TU_USUARIO/TT-1-Sistema-NNA.git

# Crear rama de feature
git checkout -b feature/nueva-funcionalidad

# Hacer commits
git commit -am "Descripción del cambio"

# Push y Pull Request
git push origin feature/nueva-funcionalidad
```

---

## 📚 Documentación Adicional

- **[DEPURACION_OPTIMIZACION.md](./DEPURACION_OPTIMIZACION.md)** - Análisis detallado de mejoras v2.0
- **[RESUMEN_DEPURACION.md](./RESUMEN_DEPURACION.md)** - Resumen ejecutivo de cambios
- **[EXPLICACION_TECNICA_SISTEMA.md](./EXPLICACION_TECNICA_SISTEMA.md)** - Explicación técnica completa (150+ páginas)

---

## 📄 Licencia

Este proyecto es parte de un Trabajo Terminal académico del IPN.

---

## 👥 Autores

**Héctor Morales**  
Trabajo Terminal 1  
ESIME Zacatenco - Instituto Politécnico Nacional

---

## 📞 Contacto

Para dudas o sugerencias sobre este Trabajo Terminal:
- Email: [Contacto IPN]
- GitHub: [@hectormrales](https://github.com/hectormrales)

---

**Versión**: 2.0.0  
**Última actualización**: Noviembre 2025  
**Estado**: ✅ Producción
