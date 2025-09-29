# Sistema Inteligente para la Identificación y Seguimiento de NNA - Análisis Completo

## 🎯 Descripción del Prototipo de Análisis

Este prototipo implementa un **pipeline completo de análisis de datos** para noticias relacionadas con niños, niñas y adolescentes (NNA), siguiendo las mejores prácticas de Procesamiento de Lenguaje Natural (PLN) y Machine Learning.

## 🔬 Metodología de Análisis Implementada

### 1. **Recolección de Datos (RSS)**
- ✅ Extracción automatizada desde feeds RSS de medios mexicanos
- ✅ Manejo de múltiples fuentes de noticias
- ✅ Headers personalizados para evitar bloqueos
- ✅ Normalización de fechas y contenido

### 2. **Almacenamiento Estructurado (CSV)**
- ✅ Formato CSV para prototipo (fácil de manejar)
- ✅ Estructura de datos optimizada
- ✅ Metadatos de trazabilidad (URL fuente, fecha de extracción)

### 3. **Representación Vectorial (TF-IDF)**
- ✅ Conversión de texto a matriz numérica
- ✅ Normalización y limpieza de texto
- ✅ Eliminación de acentos y caracteres especiales
- ✅ Vectorización con TF-IDF para análisis matemático

### 4. **Modelado de Tópicos (LDA)**
- ✅ Algoritmo Latent Dirichlet Allocation implementado
- ✅ Descubrimiento automático de temas en las noticias
- ✅ Asignación de tópicos dominantes por documento
- ✅ Métricas de coherencia del modelo

### 5. **Agrupación (K-Means Clustering)**
- ✅ Clustering basado en similitud semántica
- ✅ Agrupación de noticias relacionadas
- ✅ Métricas de calidad (Silhouette Score)
- ✅ Términos representativos por cluster

### 6. **Análisis de Similitud (Similitud Coseno)**
- ✅ Comparación matemática entre documentos
- ✅ Detección de noticias similares/duplicadas
- ✅ Búsqueda por similitud de contenido
- ✅ Identificación de eventos relacionados

### 7. **Búsqueda Mejorada (Diccionario de Sinónimos)**
- ✅ Diccionario especializado en términos de NNA y violencia de género
- ✅ Sinónimos basados en fuentes oficiales (ONU Mujeres, INMUJERES, CEPAL)
- ✅ Expansión automática de consultas de búsqueda
- ✅ Búsqueda semántica inteligente

## 🚀 Instalación y Uso Rápido

### Prerrequisitos
```bash
# 1. Clonar el repositorio
git clone [url-del-repo]
cd TT-1-Sistema-Inteligente-para-la-Identificación-y-Seguimiento-de-NNA-s-main

# 2. Crear entorno virtual (recomendado)
python -m venv venv
venv\\Scripts\\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt
```

### Ejecución del Análisis Completo
```bash
# Ejecutar demo completo
python demo_analysis.py

# O ejecutar análisis programáticamente
python -c "from src.analysis.complete_analyzer import run_quick_analysis; run_quick_analysis()"
```

### Uso Programático
```python
from src.analysis.complete_analyzer import CompleteNewsAnalyzer

# Crear analizador
analyzer = CompleteNewsAnalyzer()

# Ejecutar análisis completo
results = analyzer.run_complete_analysis(
    num_topics=8,      # Número de tópicos LDA
    n_clusters=5,      # Número de clusters K-Means
    save_intermediate=True
)

# Búsqueda mejorada con sinónimos
search_results = analyzer.search_enhanced("feminicidio")
print(search_results)
```

## 📊 Estructura de Resultados

### Archivo Principal: `data/noticias_analyzed.csv`
Contiene todas las noticias con análisis completo:

| Columna | Descripción |
|---------|-------------|
| `titulo` | Título original de la noticia |
| `contenido` | Contenido completo extraído |
| `fecha` | Fecha de publicación (ISO 8601) |
| `fuente` | URL del feed RSS origen |
| `menores_identificados` | Si/No - Detección de menciones a NNA |
| `cluster` | ID del cluster asignado (K-Means) |
| `topic_id` | ID del tópico dominante (LDA) |
| `topic_description` | Descripción del tópico |
| `topic_probability` | Probabilidad del tópico dominante |
| `most_similar_doc_idx` | Índice del documento más similar |
| `max_similarity` | Puntuación de similitud máxima |
| `titulo_limpio` | Título procesado y normalizado |
| `contenido_limpio` | Contenido procesado para análisis |

### Archivos Complementarios
- `data/noticias_analyzed_metadata.json`: Metadatos del análisis
- `data/synonym_dictionary.json`: Diccionario de sinónimos utilizado
- `data/noticias_raw.csv`: Datos originales sin procesar

## 🎯 Casos de Uso del Prototipo

### 1. **Identificación Automática de NNA**
```python
# Filtrar noticias con menciones a NNA
nna_news = results[results['menores_identificados'] == 'Si']
print(f"Encontradas {len(nna_news)} noticias con menciones a NNA")
```

### 2. **Análisis de Tópicos Emergentes**
```python
# Ver distribución de tópicos
topic_distribution = results['topic_id'].value_counts()
print("Tópicos más frecuentes:", topic_distribution.head())
```

### 3. **Detección de Casos Relacionados**
```python
# Encontrar noticias similares a una específica
similar_docs = results[results['max_similarity'] > 0.7]
print(f"Encontrados {len(similar_docs)} casos con alta similitud")
```

### 4. **Búsqueda Semántica**
```python
# Búsqueda expandida con sinónimos
resultados = analyzer.search_enhanced("violencia familiar")
# Encuentra también: "maltrato doméstico", "agresión intrafamiliar", etc.
```

## 🔧 Configuración Avanzada

### Personalizar Fuentes RSS
Editar `config.py`:
```python
RSS_FEEDS = [
    'https://mi-fuente-1.com/rss.xml',
    'https://mi-fuente-2.com/feed/',
    # Agregar más fuentes...
]
```

### Ajustar Parámetros del Análisis
```python
analyzer = CompleteNewsAnalyzer()

# Análisis personalizado
results = analyzer.run_complete_analysis(
    num_topics=10,     # Más tópicos para mayor granularidad
    n_clusters=8,      # Más clusters para mejor segmentación
    save_intermediate=False  # No guardar archivos intermedios
)
```

### Expandir Diccionario de Sinónimos
```python
from src.analysis.synonym_dictionary import SynonymDictionary

# Cargar diccionario
synonym_dict = SynonymDictionary()

# Agregar nuevos términos
synonym_dict.add_synonym_group([
    "término_nuevo", "sinónimo1", "sinónimo2"
])

# Guardar cambios
synonym_dict.save_to_file("data/synonym_dictionary_custom.json")
```

## 📈 Métricas y Evaluación

### Calidad del Clustering
- **Silhouette Score**: Mide qué tan bien separados están los clusters
- **Rango**: -1 a 1 (valores cercanos a 1 son mejores)
- **Interpretación**: >0.5 = clustering bueno, >0.7 = excelente

### Coherencia de Tópicos LDA
- **Coherence Score**: Mide qué tan coherentes son los tópicos
- **Rango**: 0 a 1 (valores más altos son mejores)
- **Interpretación**: >0.4 = tópicos coherentes, >0.6 = muy coherentes

### Similitud de Documentos
- **Similitud Coseno**: Mide similitud entre textos
- **Rango**: 0 a 1 (1 = idénticos, 0 = completamente diferentes)
- **Interpretación**: >0.5 = similares, >0.8 = muy similares

## 🛠️ Solución de Problemas

### Error: "No se recolectaron noticias"
1. Verificar conexión a internet
2. Comprobar que las URLs RSS están activas
3. Revisar headers en `config.py`

### Error: "Memoria insuficiente"
1. Reducir `TFIDF_MAX_FEATURES` en `config.py`
2. Procesar en lotes más pequeños
3. Usar menos clusters/tópicos

### Error: "Módulo no encontrado"
```bash
pip install -r requirements.txt
```

## 📚 Fundamentos Teóricos

### TF-IDF (Term Frequency-Inverse Document Frequency)
- **Propósito**: Convertir texto a números para análisis matemático
- **Ventaja**: Resalta términos importantes y únicos
- **Uso**: Base para clustering y análisis de similitud

### LDA (Latent Dirichlet Allocation)
- **Propósito**: Descubrir temas ocultos en colecciones de documentos
- **Ventaja**: Interpretación automática de contenidos
- **Uso**: Clasificación temática de noticias

### K-Means Clustering
- **Propósito**: Agrupar documentos similares
- **Ventaja**: Identifica patrones sin supervisión
- **Uso**: Detección de casos relacionados

### Similitud Coseno
- **Propósito**: Medir similitud entre vectores de texto
- **Ventaja**: Independiente de la longitud del documento
- **Uso**: Búsqueda por similitud y detección de duplicados

## 🎓 Requerimientos Funcionales Cubiertos

- ✅ **RF-01**: Conexión a múltiples fuentes (RSS feeds)
- ✅ **RF-02**: Extracción automatizada de datos
- ✅ **RF-04**: Identificación de menciones a NNA (PLN)
- ✅ **RF-05**: Estructuración de datos
- ✅ **RF-06**: Almacenamiento estructurado (CSV)
- ✅ **RF-07**: Búsqueda avanzada (sinónimos + similitud)
- ✅ **RF-13**: Clasificación automática (clustering + tópicos)
- ✅ **RF-16**: Trazabilidad completa

## 🔮 Próximos Desarrollos

1. **Interfaz Web**: Integración con Flask para visualización
2. **Base de Datos**: Migración de CSV a PostgreSQL/SQLite
3. **Modelos Avanzados**: Implementación de BERT/transformers
4. **Alertas Automáticas**: Sistema de notificaciones para casos críticos
5. **Visualizaciones**: Gráficos interactivos con Plotly/D3.js

---

## 👥 Contribución

Este prototipo forma parte del trabajo terminal del Sistema Inteligente para la Identificación y Seguimiento de NNA, enfocado en proporcionar herramientas analíticas robustas para la detección y análisis de casos relacionados con menores de edad en medios de comunicación.

**Desarrollado con**: Python, scikit-learn, Gensim, pandas, Flask