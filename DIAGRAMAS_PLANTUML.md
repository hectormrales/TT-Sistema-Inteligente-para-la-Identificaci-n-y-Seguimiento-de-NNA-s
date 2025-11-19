# 📊 Diagramas PlantUML - Sistema de Web Scraping y ML

Este archivo contiene diagramas PlantUML que visualizan todo el proceso del sistema.

---

## 📋 Índice de Diagramas

1. [Arquitectura General del Sistema](#1-arquitectura-general-del-sistema)
2. [Proceso de Recolección (Web Scraping)](#2-proceso-de-recolección-web-scraping)
3. [Pipeline de Machine Learning](#3-pipeline-de-machine-learning)
4. [Flujo de Análisis TF-IDF](#4-flujo-de-análisis-tf-idf)
5. [Proceso de Clustering DBSCAN](#5-proceso-de-clustering-dbscan)
6. [Detección de Duplicados](#6-detección-de-duplicados)
7. [Diagrama de Componentes](#7-diagrama-de-componentes)
8. [Diagrama de Secuencia Completo](#8-diagrama-de-secuencia-completo)

---

## 1. Arquitectura General del Sistema

```plantuml
@startuml arquitectura_general
!define RECTANGLE class

skinparam backgroundColor #FEFEFE
skinparam componentStyle rectangle

title Arquitectura General del Sistema NNA

package "Fuentes de Datos" {
    [RSS Feeds\n10 medios] as RSS
    [Google News\n150 resultados] as GNews
    [Búsqueda Histórica\n6 meses] as Historical
}

package "Recolección" {
    [Data Collector] as Collector
    database "Noticias Crudas\n~280-300" as RawDB
}

package "Detección" {
    [Feminicide Detector\n40+ patrones\n17 exclusiones] as Detector
    database "Noticias Filtradas\n~126 NNA" as FilteredDB
}

package "Análisis ML" {
    [TF-IDF Vectorizer\n3000 features] as TFIDF
    [LDA Model\n8 topics] as LDA
    [DBSCAN Clustering\neps=0.8] as DBSCAN
    [Similarity Analysis\n75% threshold] as Similarity
}

package "Almacenamiento" {
    database "noticias.csv" as CSV1
    database "clusters_info.csv" as CSV2
    database "synonym_dict.json" as JSON
}

package "Presentación" {
    [Flask API\nREST endpoints] as API
    [Dashboard Web\nBootstrap 5] as Dashboard
}

RSS --> Collector
GNews --> Collector
Historical --> Collector
Collector --> RawDB
RawDB --> Detector
Detector --> FilteredDB
FilteredDB --> TFIDF
TFIDF --> LDA
TFIDF --> DBSCAN
TFIDF --> Similarity
LDA --> CSV1
DBSCAN --> CSV2
Similarity --> JSON
CSV1 --> API
CSV2 --> API
JSON --> API
API --> Dashboard

note right of Detector
  Detecta:
  - Feminicidios
  - Menciones NNA
  - Calcula prioridad
  - Excluye estadísticas
end note

note right of TFIDF
  Convierte texto a
  matriz numérica
  (281 x 3000)
end note

note bottom of Dashboard
  http://localhost:5000
  - Búsqueda inteligente
  - Filtros por prioridad
  - Exportación CSV
end note

@enduml
```

---

## 2. Proceso de Recolección (Web Scraping)

```plantuml
@startuml recoleccion_scraping
!define RECTANGLE class

skinparam backgroundColor #FEFEFE
skinparam activityBackgroundColor #E3F2FD
skinparam activityBorderColor #1976D2

title Proceso de Recolección de Noticias

|Fuente 1: RSS|
start
:Configurar 10 RSS Feeds;
note right
  - CIMAC Noticias
  - SEM México
  - La Jornada
  - El Universal
  - +6 medios más
end note

:Parsear XML con feedparser;
:Extraer por cada entrada:
- Título
- Descripción
- Link
- Fecha
- Fuente;

:Resultado: ~70 noticias;

|Fuente 2: Google News|
:Configurar GoogleNews API;
note right
  - lang='es'
  - country='MX'
end note

:Definir 5 queries de búsqueda;
note right
  - "feminicidio niños"
  - "feminicidio menores"
  - "feminicidio huérfanos"
  - "asesinato mujer hijos"
  - "violencia género niños"
end note

repeat
  :Ejecutar búsqueda;
  :Obtener 30 resultados;
  :Extraer metadata;
repeat while (¿Más queries?) is (Sí)
->No;

:Limitar a 150 más recientes;
:Resultado: 150 noticias;

|Fuente 3: Histórico|
:Configurar rango de fechas;
note right
  Inicio: hoy - 6 meses
  Fin: hoy
end note

:Definir 5 queries históricas;
repeat
  :Buscar en rango de fechas;
  :Obtener 50 resultados;
repeat while (¿Más queries?) is (Sí)
->No;

:Resultado: ~250 noticias;

|Consolidación|
:Unificar 3 DataFrames;
:Total: ~470 noticias;

:Deduplicar por URL;
:Eliminar duplicados;
:Total único: ~280-300;

|Detección|
:Aplicar FeminicideDetector;

fork
  :Detectar feminicidio\n(40+ patrones);
fork again
  :Detectar NNA\n(15+ patrones);
fork again
  :Aplicar exclusiones\n(17 patrones);
end fork

:Calcular confianza y prioridad;

if (¿Es objetivo?) then (Sí)
  :Marcar como caso NNA;
  :Asignar prioridad;
  note right
    ALTA: ≥70% confianza
    MEDIA: 40-69%
    BAJA: 20-39%
    IRRELEVANTE: <20%
  end note
else (No)
  :Marcar como irrelevante;
endif

:Guardar en noticias.csv;
note right
  Encoding: UTF-8-sig
  Columnas: 16
end note

stop

@enduml
```

---

## 3. Pipeline de Machine Learning

```plantuml
@startuml pipeline_ml
!define RECTANGLE class

skinparam backgroundColor #FEFEFE
skinparam sequenceMessageAlign center

title Pipeline Completo de Machine Learning

participant "Noticias\nFiltradas" as Data
participant "Text\nCleaner" as Cleaner
participant "TF-IDF\nVectorizer" as TFIDF
participant "LDA\nModel" as LDA
participant "DBSCAN\nClustering" as DBSCAN
participant "Similarity\nAnalyzer" as Similarity
participant "Results\nStorage" as Storage

activate Data
Data -> Cleaner: 126 noticias NNA
activate Cleaner

note right of Cleaner
  Limpieza de texto:
  1. Lowercase
  2. Sin acentos
  3. Sin URLs
  4. Sin números
  5. Sin puntuación
  6. Sin espacios múltiples
end note

Cleaner -> Cleaner: clean_text()
Cleaner --> TFIDF: Texto limpio
deactivate Cleaner

activate TFIDF
note right of TFIDF
  Configuración:
  - max_features: 3000
  - min_df: 1
  - max_df: 0.8
  - ngram_range: (1,2)
end note

TFIDF -> TFIDF: fit_transform()
TFIDF --> LDA: Matriz (126 x 3000)
TFIDF --> DBSCAN: Matriz (126 x 3000)
TFIDF --> Similarity: Matriz (126 x 3000)

activate LDA
note right of LDA
  Parámetros:
  - n_components: 8
  - random_state: 42
  - max_iter: 10
end note

LDA -> LDA: fit_transform()
LDA --> Storage: 8 tópicos + distribución
deactivate LDA

activate DBSCAN
note right of DBSCAN
  Parámetros:
  - eps: 0.8
  - min_samples: 2
  - metric: 'cosine'
end note

DBSCAN -> DBSCAN: fit_predict()
DBSCAN --> Storage: 6 clusters + 214 outliers
note right
  Silhouette Score: 0.48
end note
deactivate DBSCAN

activate Similarity
Similarity -> Similarity: cosine_similarity()
note right of Similarity
  Genera matriz (126 x 126)
  de similitudes
end note

Similarity -> Similarity: detect_duplicates(threshold=0.75)
Similarity --> Storage: 6 duplicados en 2 grupos
deactivate Similarity

activate Storage
Storage -> Storage: Guardar resultados
note right of Storage
  Archivos generados:
  - noticias_analyzed.csv
  - clusters_info.csv
  - synonym_dictionary.json
  - metadata.json
end note

Storage --> Data: Pipeline completado
deactivate Storage
deactivate Data

@enduml
```

---

## 4. Flujo de Análisis TF-IDF

```plantuml
@startuml tfidf_flow
!define RECTANGLE class

skinparam backgroundColor #FEFEFE
skinparam activityBackgroundColor #FFF9C4
skinparam activityBorderColor #F57F17

title Proceso de Vectorización TF-IDF

start

:Recibir textos limpios\n(126 documentos);

:Crear vocabulario;
note right
  Extraer todas las palabras únicas
  y bigramas del corpus
end note

:Aplicar filtros;
partition "Filtrado" {
  :Eliminar palabras en >80% docs\n(max_df=0.8);
  :Mantener palabras en ≥1 doc\n(min_df=1);
  :Seleccionar top 3000 features;
}

:Calcular Term Frequency (TF);
note right
  TF = (veces que aparece palabra) / 
       (total palabras del documento)
end note

:Calcular Inverse Document Frequency (IDF);
note right
  IDF = log(total docs / 
            docs con la palabra)
end note

:Multiplicar TF × IDF;

:Generar matriz dispersa;
note right
  Shape: (126 noticias, 3000 features)
  Formato: scipy.sparse.csr_matrix
  Valores: pesos TF-IDF (0.0 a 1.0)
end note

split
  :Enviar a LDA;
split again
  :Enviar a DBSCAN;
split again
  :Enviar a Similarity Analyzer;
end split

:Matriz TF-IDF lista;

stop

note bottom
  Ejemplo de valores:
  Doc_0: [0.42, 0.0, 0.31, 0.50, ...]
  - "feminicidio": 0.42
  - "oaxaca": 0.0 (no aparece)
  - "mujer": 0.31
  - "niños": 0.50
end note

@enduml
```

---

## 5. Proceso de Clustering DBSCAN

```plantuml
@startuml dbscan_clustering
!define RECTANGLE class

skinparam backgroundColor #FEFEFE
skinparam activityBackgroundColor #E8F5E9
skinparam activityBorderColor #388E3C

title Proceso de Clustering DBSCAN

start

:Recibir matriz TF-IDF\n(126 x 3000);

:Configurar DBSCAN;
note right
  eps = 0.8
  min_samples = 2
  metric = 'cosine'
end note

:Inicializar etiquetas\ntodos = -1 (sin cluster);

partition "Algoritmo DBSCAN" {
  repeat
    :Seleccionar documento i\nno procesado;
    
    :Calcular distancias coseno\ncon todos los documentos;
    
    :Encontrar vecinos\n(distancia ≤ eps);
    
    if (¿Tiene ≥ min_samples vecinos?) then (Sí)
      :Crear nuevo cluster\nID = n;
      :Asignar documento i\nal cluster n;
      
      repeat
        :Seleccionar vecino j\ndel cluster;
        :Encontrar vecinos de j;
        
        if (¿Tiene ≥ min_samples?) then (Sí)
          :Agregar vecinos\nal cluster;
          :Procesar vecinos\nrecursivamente;
        else (No)
          :Marcar como borde\ndel cluster;
        endif
        
      repeat while (¿Más vecinos?) is (Sí)
      ->No;
      
    else (No)
      :Marcar como outlier\n(cluster = -1);
    endif
    
  repeat while (¿Documentos sin procesar?) is (Sí)
  ->No;
}

:Contar clusters formados;
:Contar outliers;

:Calcular Silhouette Score;
note right
  Mide calidad del clustering
  Rango: -1 (malo) a 1 (excelente)
end note

:Generar resumen de clusters;

fork
  :Cluster 0: 6 docs\n(datos, estadísticas);
fork again
  :Cluster 1: 5 docs\n(cimac, sem);
fork again
  :Cluster 2: 3 docs\n(oaxaca, casos);
fork again
  :Cluster 3: 3 docs\n(huérfanos, político);
fork again
  :Cluster 4: 3 docs\n(madres, víctimas);
fork again
  :Cluster 5: 4 docs\n(edomex, sol);
fork again
  :Outliers: 102 docs\n(casos únicos);
end fork

:Guardar resultados;

stop

note bottom
  Resultado:
  - 6 clusters pequeños
  - 102 outliers (81%)
  - Silhouette: 0.48 (bueno)
end note

@enduml
```

---

## 6. Detección de Duplicados

```plantuml
@startuml deteccion_duplicados
!define RECTANGLE class

skinparam backgroundColor #FEFEFE
skinparam activityBackgroundColor #FCE4EC
skinparam activityBorderColor #C2185B

title Proceso de Detección de Duplicados

start

:Recibir matriz de similitud\n(126 x 126);

:Configurar umbral = 0.75\n(75% similitud);

:Inicializar columnas\nen DataFrame;
note right
  - es_duplicado = False
  - titulo_original = ''
  - fuente_original = ''
  - grupo_duplicado = -1
end note

:Inicializar grupo_id = 0;
:Crear set procesados = {};

repeat
  :Seleccionar documento i\nno procesado;
  
  :Obtener fila i de\nmatriz de similitud;
  
  :Encontrar documentos con\nsimilitud ≥ 0.75;
  
  :Filtrar:
  - No incluir documento i
  - No incluir ya procesados;
  
  if (¿Hay documentos similares?) then (Sí)
    
    :Asignar grupo_duplicado = grupo_id\nal documento i;
    
    repeat
      :Seleccionar documento j\nsimilar;
      
      :Marcar j como duplicado;
      :Copiar título de i a j;
      :Copiar fuente de i a j;
      :Asignar mismo grupo_id;
      :Agregar j a procesados;
      
      note right
        Documento i = ORIGINAL
        Documento j = DUPLICADO
      end note
      
    repeat while (¿Más similares?) is (Sí)
    ->No;
    
    :Incrementar grupo_id;
    :Agregar i a procesados;
    
  else (No)
    :Documento único\n(no es duplicado);
  endif
  
repeat while (¿Más documentos?) is (Sí)
->No;

:Contar estadísticas;

partition "Resultados" {
  :Total noticias únicas;
  :Total duplicados;
  :Total grupos;
  
  note right
    Ejemplo real:
    - Únicas: 120
    - Duplicados: 6
    - Grupos: 2
  end note
}

:Mostrar grupos de duplicados;

split
  :Grupo 1\n6 versiones\n"Feminicidio niñas México";
split again
  :Grupo 2\n2 versiones\n"Huérfanos feminicidio";
end split

:Actualizar DataFrame;

stop

@enduml
```

---

## 7. Diagrama de Componentes

```plantuml
@startuml componentes_sistema
!define RECTANGLE class

skinparam backgroundColor #FEFEFE
skinparam component {
  BackgroundColor #E1F5FE
  BorderColor #0277BD
  FontSize 12
}

title Diagrama de Componentes del Sistema

package "src/collection" {
  [data_collector.py] as DC
  [feminicide_detector.py] as FD
  [historical_scraper.py] as HS
}

package "src/analysis" {
  [simplified_analyzer.py] as SA
  [synonym_dictionary.py] as SD
}

package "app" {
  [app_docker.py] as APP
  folder templates {
    [dashboard_docker.html] as DASH
  }
}

package "External Services" {
  [RSS Feeds] as RSS
  [Google News API] as GN
}

database "CSV Files" {
  [noticias.csv] as CSV1
  [clusters_info.csv] as CSV2
}

database "JSON Files" {
  [synonym_dictionary.json] as JSON1
  [metadata.json] as JSON2
}

cloud "Docker" {
  [nna-analyzer\nContainer] as CONT1
  [nna-webapp\nContainer] as CONT2
}

actor User as U

' Relaciones de recolección
RSS --> DC : Parse XML
GN --> DC : API calls
DC --> HS : Complementa
DC ..> FD : usa

' Relaciones de análisis
DC --> CSV1 : Guarda
CSV1 --> SA : Lee
SA ..> SD : usa
SA --> CSV2 : Guarda
SA --> JSON2 : Guarda

' Relaciones de presentación
CSV1 --> APP : Lee
CSV2 --> APP : Lee
JSON1 --> APP : Lee
APP --> DASH : Renderiza
DASH --> U : Display

' Docker
CONT1 ..> DC : Ejecuta\ncada 24h
CONT2 ..> APP : Ejecuta\nFlask
U --> CONT2 : http://localhost:5000

note right of DC
  Orquesta las 3 fuentes:
  - RSS (70 noticias)
  - Google News (150)
  - Histórico (250)
end note

note right of FD
  40+ patrones detección
  17 patrones exclusión
  Calcula prioridad
end note

note right of SA
  Pipeline ML completo:
  - TF-IDF (3000 features)
  - LDA (8 topics)
  - DBSCAN (eps=0.8)
  - Similitud (75% threshold)
end note

note right of APP
  API REST:
  - /api/stats
  - /api/noticias
  - /api/search
  - /api/analyze
  - /api/export/csv
end note

@enduml
```

---

## 8. Diagrama de Secuencia Completo

```plantuml
@startuml secuencia_completa
!define RECTANGLE class

skinparam backgroundColor #FEFEFE
skinparam sequenceMessageAlign center
skinparam maxMessageSize 150

title Secuencia Completa: Análisis de Noticias

actor Usuario as U
participant "Dashboard\nWeb" as DASH
participant "Flask\nAPI" as API
participant "Data\nCollector" as DC
participant "RSS\nFeeds" as RSS
participant "Google\nNews" as GN
participant "Feminicide\nDetector" as FD
participant "Simplified\nAnalyzer" as SA
participant "TF-IDF" as TFIDF
participant "LDA" as LDA
participant "DBSCAN" as DBSCAN
participant "Similarity" as SIM
database "CSV\nFiles" as DB

U -> DASH: Accede al dashboard
activate DASH
DASH -> API: GET /api/stats
activate API
API -> DB: Leer noticias.csv
activate DB
DB --> API: DataFrame
deactivate DB
API --> DASH: JSON stats
deactivate API
DASH --> U: Mostrar estadísticas
deactivate DASH

...Usuario solicita análisis completo...

U -> DASH: Click "Ejecutar Análisis"
activate DASH
DASH -> API: POST /api/analyze
activate API

API -> DC: collect_all_news()
activate DC

group Recolección de Fuentes
  DC -> RSS: Parse 10 feeds
  activate RSS
  RSS --> DC: ~70 noticias
  deactivate RSS
  
  DC -> GN: Buscar 5 queries
  activate GN
  GN --> DC: 150 noticias
  deactivate GN
  
  DC -> DC: Búsqueda histórica
  note right: 6 meses, 5 queries\n~250 noticias
end

DC -> DC: Deduplicar por URL
DC -> DC: ~280 noticias únicas

group Detección de Feminicidios
  loop Para cada noticia
    DC -> FD: detect(titulo, contenido)
    activate FD
    FD -> FD: Aplicar 40+ patrones
    FD -> FD: Aplicar 17 exclusiones
    FD -> FD: Calcular confianza
    FD -> FD: Calcular prioridad
    FD --> DC: {is_feminicide, has_children,\nconfidence, priority}
    deactivate FD
  end
end

DC -> DB: Guardar noticias.csv
activate DB
DC --> API: DataFrame (126 NNA)
deactivate DC

group Análisis ML
  API -> SA: analyze_full_pipeline(df)
  activate SA
  
  SA -> SA: Limpiar texto
  note right
    - Lowercase
    - Sin acentos
    - Sin URLs
    - Sin números
  end note
  
  SA -> TFIDF: fit_transform(textos)
  activate TFIDF
  TFIDF --> SA: Matriz (126 x 3000)
  deactivate TFIDF
  
  par Análisis Paralelo
    SA -> LDA: fit_transform(matriz)
    activate LDA
    LDA --> SA: 8 tópicos
    deactivate LDA
  else
    SA -> DBSCAN: fit_predict(matriz)
    activate DBSCAN
    DBSCAN --> SA: 6 clusters
    deactivate DBSCAN
  else
    SA -> SIM: cosine_similarity(matriz)
    activate SIM
    SIM -> SIM: detect_duplicates(0.75)
    SIM --> SA: 6 duplicados
    deactivate SIM
  end
  
  SA -> DB: Guardar resultados
  SA --> API: DataFrame analizado
  deactivate SA
end

deactivate DB

API --> DASH: {success: true,\nnoticias: 281,\nnna: 126,\nclusters: 6,\ntopics: 8}
deactivate API

DASH -> DASH: Actualizar estadísticas
DASH -> API: GET /api/noticias
activate API
API -> DB: Leer resultados
activate DB
DB --> API: Noticias paginadas
deactivate DB
API --> DASH: JSON con noticias
deactivate API

DASH --> U: Mostrar resultados
deactivate DASH

note over U
  Usuario puede:
  - Filtrar por NNA
  - Buscar por palabras
  - Ver clusters
  - Exportar CSV
end note

@enduml
```

---

## 📝 Cómo Usar estos Diagramas

### Opción 1: PlantUML Online
1. Visita: http://www.plantuml.com/plantuml/uml/
2. Copia el código de cualquier diagrama
3. Pega en el editor
4. Visualiza el diagrama generado

### Opción 2: VS Code Extension
1. Instala la extensión "PlantUML" en VS Code
2. Abre este archivo .md
3. Presiona `Alt+D` para previsualizar diagramas

### Opción 3: Generar Imágenes
```bash
# Instalar PlantUML
npm install -g node-plantuml

# Generar PNG
plantuml diagrama.puml -tpng

# Generar SVG
plantuml diagrama.puml -tsvg
```

---

## 🎨 Leyenda de Colores

- **Azul** (#E3F2FD): Procesos de recolección
- **Amarillo** (#FFF9C4): Procesos de transformación (TF-IDF)
- **Verde** (#E8F5E9): Procesos de clustering
- **Rosa** (#FCE4EC): Procesos de detección de duplicados
- **Cyan** (#E1F5FE): Componentes del sistema

---

**Creado:** 19 de noviembre de 2025  
**Sistema:** TT-1 NNA v3.0.0  
**Formato:** PlantUML
