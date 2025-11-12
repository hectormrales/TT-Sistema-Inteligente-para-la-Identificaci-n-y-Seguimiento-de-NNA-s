# Sistema Inteligente para Deteccion de Feminicidios con NNA# Sistema Inteligente para Identificacin y Seguimiento de NNA



**Universidad:** Instituto Politecnico Nacional - ESIME Zacatenco  ##  **Descripcin del Proyecto**

**Programa:** Trabajo Terminal 1  

**Autor:** Hector Morales  Sistema automatizado para detectar y analizar menciones de **Nios, Nias y Adolescentes (NNA)** en medios digitales mexicanos, utilizando tcnicas de Machine Learning y procesamiento de lenguaje natural.

**Fecha:** Noviembre 2025

##  **Inicio Rpido con Docker**

---

### **Prerrequisitos**

## Descripcion del Proyecto- Docker Desktop instalado

- Puerto 5000 disponible

Sistema de Machine Learning para la deteccion y analisis de noticias sobre feminicidios con victimas indirectas (NNA - Ninas, Ninos y Adolescentes huerfanos) en Mexico.

### **Ejecutar Sistema**

El sistema recopila automaticamente noticias de fuentes especializadas en genero y seguridad, aplica algoritmos de deteccion de patrones especificos, y agrupa casos similares para facilitar el analisis y seguimiento de victimas indirectas.```bash

# Clonar e ingresar al directorio

---cd /ruta/del/proyecto



## Caracteristicas Principales# Iniciar sistema completo

docker-compose up -d

### 1. Recoleccion Inteligente

- Scraping automatico de RSS feeds especializados (CIMAC, SEM Mexico, etc.)# Verificar estado

- Detector especializado con mas de 40 patrones de feminicidio, NNA y orfandaddocker-compose ps

- Sistema de confianza y priorizacion (ALTA, MEDIA, BAJA, IRRELEVANTE)

# Acceder al dashboard

### 2. Analisis con Machine Learning# Abrir: http://localhost:5000

- **TF-IDF** optimizado para preservar palabras clave unicas```

- **LDA** para modelado de topicos (6 temas principales)

- **DBSCAN** para clustering automatico de casos similares### **Comandos tiles**

- Analisis de similitud coseno entre documentos```bash

# Ver logs en vivo

### 3. Busqueda Mejoradadocker-compose logs -f

- Diccionario de sinonimos especializado (143+ terminos)

- Expansion automatica de consultas# Detener sistema

- Deteccion de terminos relacionados en textodocker-compose down



---# Reiniciar con reconstruccin

docker-compose up --build -d

## Estructura del Proyecto```



```##  **Funcionalidades**

TT-1-Sistema/

├── config.py                      # Configuracion (RSS feeds)###  **Anlisis Automtico**

├── requirements.txt               # Dependencias Python- **Recoleccin RSS** de 8 fuentes mexicanas cada 6 horas

├── test_sistema_mejorado.py       # Script de pruebas completo- **Procesamiento NLP** completo con 7 etapas

│- **Deteccin NNA** con diccionario de sinnimos especializado

├── src/- **Clustering** automtico de noticias similares

│   ├── collection/- **Anlisis de tpicos** con LDA

│   │   ├── data_collector.py      # Recoleccion de noticias

│   │   └── feminicide_detector.py # Detector especializado###  **Interfaz Web**

│   │- **Dashboard interactivo** con Bootstrap

│   └── analysis/- **Bsqueda inteligente** con expansin de sinnimos

│       ├── simplified_analyzer.py # Pipeline ML completo- **Estadsticas en tiempo real**

│       └── synonym_dictionary.py  # Diccionario de sinonimos- **Exportacin CSV** de resultados

│- **Paginacin** automtica de noticias

├── data/

│   ├── noticias_raw.csv           # Datos originales###  **API REST**

│   ├── noticias.csv               # Datos procesados```bash

│   └── clusters_info.csv          # Informacion de clustersGET  /api/stats           # Estadsticas generales

│GET  /api/noticias        # Lista paginada de noticias

├── app/GET  /api/search?q=texto  # Bsqueda con sinnimos

│   └── templates/POST /api/analyze         # Ejecutar anlisis completo

│       └── dashboard_docker.html  # Dashboard webGET  /api/export/csv      # Descargar datos CSV

│GET  /api/health          # Estado del sistema

└── docs/```

    ├── DEPURACION_COMPLETA.md     # Diagnostico del sistema

    ├── IMPLEMENTACION_COMPLETA.md # Guia tecnica##  **Arquitectura del Sistema**

    └── MEJORA_1_PROCESO.md        # Documentacion de mejoras

```### **Componentes Docker**

```

--- Sistema Multi-Container

  nna-analyzer    # Anlisis automtico en background

## Instalacion  nna-webapp      # Interfaz web (puerto 5000)

  nna-network     # Red interna Docker

### Requisitos```

- Python 3.9+

- pip### **Pipeline de Anlisis (7 Etapas)**

```

### Pasos1 Recoleccin RSS      Feeds de noticias mexicanas

2 Almacenamiento CSV   Persistencia de datos

1. Clonar el repositorio:3 Vectorizacin TF-IDF  Representacin numrica

```bash4 Modelado LDA         Identificacin de tpicos

git clone https://github.com/hectormrales/TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s.git5 Clustering DBSCAN    Agrupacin automtica + deteccin de outliers  NUEVO

cd TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s6 Anlisis Similitud   Clculo de distancias

```7 Deteccin NNA        Clasificacin especializada

```

2. Instalar dependencias:

```bash### ** Mejora Reciente: Migracin a DBSCAN**

pip install -r requirements.txt

```El sistema ahora utiliza **DBSCAN** (Density-Based Spatial Clustering) en lugar de K-Means:



---**Ventajas:**

-  **Deteccin automtica** del nmero de clusters (no ms k=4 arbitrario)

## Uso-  **Identificacin de outliers** (casos atpicos nicos)

-  **Mejora +21%** en Silhouette Score

### Ejecutar analisis completo-  **Robusto ante ruido** (duplicados, errores scraping)



```bash**Uso:**

python test_sistema_mejorado.py```python

```# Mtodo recomendado (DBSCAN)

analyzer.run_complete_analysis(clustering_method='dbscan')

Este script:

1. Recolecta noticias de fuentes RSS# Mtodo legacy (K-Means) para comparacin

2. Aplica detector de feminicidiosanalyzer.run_complete_analysis(clustering_method='kmeans')

3. Ejecuta pipeline de ML (TF-IDF, LDA, DBSCAN)```

4. Genera estadisticas y reportes

5. Guarda resultados en `data/`**Archivos generados:**

- `data/clusters_info.csv` - Informacin detallada de cada cluster

### Usar el analizador en codigo- Outliers marcados como cluster `-1` (casos nicos)



```python##  **Estructura del Proyecto**

from src.analysis.simplified_analyzer import SimplifiedNewsAnalyzer

```

# Inicializar sistema-nna/

analyzer = SimplifiedNewsAnalyzer()  docker-compose.yml      # Orquestacin de contenedores

  Dockerfile              # Configuracin de imagen

# Ejecutar pipeline completo   app_docker.py           # Aplicacin web Flask

df_result = analyzer.run_complete_analysis(  demo_docker.py           # Analizador automtico

    num_topics=6,   config.py               # Configuracin del sistema

    clustering_method='dbscan',  requirements.txt         # Dependencias Python

    eps=0.6,  src/

    min_samples=2,    analysis/

    save_intermediate=True       simplified_analyzer.py    # Motor de anlisis principal

)       synonym_dictionary.py     # Diccionario NNA especializado

    collection/

# Filtrar noticias objetivo        data_collector.py         # Recolector RSS

objetivo = df_result[df_result['es_objetivo'] == True]  app/

alta_prioridad = df_result[df_result['prioridad'] == 'ALTA']    __init__.py

    templates/

print(f"Noticias objetivo: {len(objetivo)}")        dashboard_docker.html     # Interfaz web moderna

print(f"Alta prioridad: {len(alta_prioridad)}")  data/

```     noticias.csv             # Datos procesados

     synonym_dictionary.json  # Diccionario de sinnimos

### Usar el detector de feminicidios```



```python##  **Tecnologas Utilizadas**

from src.collection.feminicide_detector import FeminicideDetector

### **Core Analysis**

detector = FeminicideDetector()- **pandas 2.2.2** - Manipulacin de datos

- **scikit-learn 1.4.2** - Machine Learning (TF-IDF, LDA, K-Means)

texto = "Feminicidio en Ecatepec deja dos ninos huerfanos"- **numpy** - Clculos numricos

result = detector.detect(texto)

### **Web Scraping**

print(f"Es feminicidio: {result['is_feminicide']}")- **requests 2.31.0** - Peticiones HTTP

print(f"Tiene NNA: {result['has_children']}")- **beautifulsoup4 4.12.2** - Parsing HTML/XML

print(f"Es objetivo: {result['is_target_news']}")- **lxml 5.3.0** - Procesador XML rpido

print(f"Confianza: {result['confidence']:.1%}")

print(f"Prioridad: {result['priority']}")### **Web Application**

```- **Flask 3.0.3** - Framework web

- **Flask-CORS 4.0.1** - Cross-origin requests

---

### **Automation**

## Campos en CSV de Salida- **schedule 1.2.2** - Tareas programadas

- **Docker** - Containerizacin

### Campos de Identificacion

- `titulo`: Titulo de la noticia##  **Resultados del Anlisis**

- `contenido`: Cuerpo completo

- `enlace`: URL original### **Mtricas Actuales**

- `fuente`: RSS feed de origen-  **146 noticias** recolectadas y procesadas

- `fecha`: Fecha de publicacion (ISO 8601)-  **41 casos NNA** detectados (28.1% tasa de deteccin)

-   **4 clusters** de noticias similares generados

### Campos de Deteccion (NUEVOS)-  **5 tpicos** principales identificados

- `es_feminicidio` (bool): Es feminicidio?

- `tiene_nna` (bool): Menciona NNA?### **Fuentes RSS Monitoreadas**

- `tiene_huerfanos` (bool): Menciona huerfanos?- La Jornada (Poltica)

- **`es_objetivo` (bool)**: Es noticia objetivo? (feminicidio + NNA)- Proceso

- `confianza` (float): Nivel de confianza (0.0-1.0)- Aristegui Noticias

- `prioridad` (str): ALTA | MEDIA | BAJA | IRRELEVANTE- Animal Poltico

- Sin Embargo

### Campos de Analisis ML- Forbes Mxico

- `cluster`: ID del cluster DBSCAN (-1 = outlier)- El Sol de Mxico

- `topic_id`: Topico LDA dominante- El Financiero

- `topic_probability`: Probabilidad del topico

- `most_similar_doc_idx`: Documento mas similar##  **Diccionario NNA Especializado**

- `max_similarity`: Similitud maxima (0.0-1.0)

Basado en vocabularios oficiales:

---- **UN Women** - Glosario de gnero

- **CEPAL** - Terminologa especializada

## Parametros Clave- **INMUJERES** - Vocabulario institucional

- **143 trminos** relacionados con NNA y violencia de gnero

### TF-IDF

```python##  **Solucin de Problemas**

TfidfVectorizer(

    max_features=3000,### **Error: Puerto 5000 ocupado**

    stop_words=spanish_stopwords,  # 80+ palabras```bash

    min_df=1,           # Incluye palabras unicas# Encontrar proceso usando el puerto

    max_df=0.8,netstat -ano | findstr :5000

    strip_accents=None  # Preserva acentos

)# Cambiar puerto en docker-compose.yml

```ports:

  - "5001:5000"  # Usar puerto 5001 en su lugar

### DBSCAN```

```python

DBSCAN(### **Error: Docker no responde**

    eps=0.6,        # Distancia maxima (similitud > 40%)```bash

    min_samples=2,  # Minimo 2 noticias por cluster# Reiniciar Docker Desktop

    metric='cosine'# Verificar que est ejecutndose

)docker --version

```

# Limpiar contenedores

### LDAdocker-compose down --volumes

```pythondocker system prune -f

LatentDirichletAllocation(```

    n_components=6,      # 6 topicos

    random_state=42,### **Ver logs detallados**

    max_iter=20,```bash

    learning_method='online'# Logs del analizador

)docker-compose logs nna-analyzer

```

# Logs de la webapp

---docker-compose logs nna-webapp



## Mejoras Implementadas (v2.0)# Todos los logs

docker-compose logs

### Problema Original```

- 0.0% de noticias cumplian objetivo del proyecto

- Fuentes RSS genericas (politica, economia)---

- Detector generico con 100% falsos positivos

- Parametros ML inadecuados##  **Sistema completamente automatizado y listo para produccin**



### SolucionesPara soporte tcnico, verificar logs del sistema y estado de contenedores Docker.

1. **RSS Feeds Especializados**: CIMAC, SEM Mexico, secciones de seguridad
2. **Detector Especifico**: 40+ patrones de feminicidio/NNA/orfandad
3. **TF-IDF Optimizado**: min_df=1, stopwords espanol, preservar acentos
4. **DBSCAN Recalibrado**: eps=0.6, min_samples=2 (mas permisivo)

### Resultados Esperados
- Noticias objetivo: 0% -> 50-60%
- Noticias feminicidio: 1.4% -> 60-70%
- Falsos positivos: 100% -> ~7%
- Clusters DBSCAN: 0 -> 5-8

---

## Documentacion Tecnica

- **DEPURACION_COMPLETA.md**: Diagnostico detallado del sistema original
- **IMPLEMENTACION_COMPLETA.md**: Guia tecnica de todas las correcciones
- **MEJORA_1_PROCESO.md**: Documentacion visual con diagramas

---

## Tecnologias Utilizadas

- **Python 3.9+**
- **scikit-learn 1.4.2**: TF-IDF, LDA, DBSCAN
- **pandas 2.2.2**: Manipulacion de datos
- **BeautifulSoup4**: Web scraping
- **requests**: HTTP requests
- **numpy**: Operaciones numericas

---

## Licencia

Proyecto academico - Instituto Politecnico Nacional

---

## Contacto

**Autor**: Hector Morales  
**Institucion**: ESIME Zacatenco - IPN  
**Ano**: 2025

---

## Notas de Desarrollo

### Proximos Pasos
- Validacion manual de 20 noticias de ALTA prioridad
- Ajuste fino de umbrales de confianza
- Dashboard interactivo con graficas
- API REST para consultas
- Alertas automaticas para prioridad ALTA

### Problemas Conocidos
- Algunas fuentes RSS pueden devolver 0 noticias (problemas de conexion)
- Se requieren fuentes especializadas adicionales para mejor cobertura
- Sistema depende de calidad y disponibilidad de feeds RSS
