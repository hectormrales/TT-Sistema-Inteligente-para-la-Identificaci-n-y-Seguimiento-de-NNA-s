# 📖 Cómo Funciona el Sistema - Documentación Técnica# 🔍 CÓMO FUNCIONA EL SISTEMA - Explicación Completa



## 📑 Índice**Sistema Inteligente para Identificación y Seguimiento de NNA's**  

**ESIME Zacatenco - IPN**  

1. [Visión General](#visión-general)**Autor: Héctor Morales**  

2. [Arquitectura del Sistema](#arquitectura-del-sistema)**Fecha: 18 de noviembre de 2025**

3. [Módulos Principales](#módulos-principales)

4. [Pipeline de Machine Learning](#pipeline-de-machine-learning)---

5. [Sistema de Detección](#sistema-de-detección)

6. [API y Dashboard](#api-y-dashboard)## 📋 Índice

7. [Deployment con Docker](#deployment-con-docker)

1. [Introducción: ¿Qué hace este sistema?](#introducción)

---2. [PASO 1: Recolección de Noticias](#paso-1-recolección)

3. [PASO 2: Detector de Feminicidios](#paso-2-detector)

## 🎯 Visión General4. [PASO 3: Vectorización TF-IDF](#paso-3-vectorización)

5. [PASO 4: Modelado de Tópicos (LDA)](#paso-4-tópicos)

El sistema recolecta, analiza y clasifica **automáticamente** noticias sobre feminicidios que dejan a NNA (Niñas, Niños y Adolescentes) en situación de orfandad.6. [PASO 5: Clustering (DBSCAN)](#paso-5-clustering)

7. [PASO 6: Análisis de Similitud](#paso-6-similitud)

### Objetivos Principales8. [Flujo Completo con Ejemplo](#flujo-completo)

9. [¿Qué palabras toma en cuenta?](#palabras-clave)

1. **Recolección Automatizada**: Obtener noticias de múltiples fuentes confiables10. [¿Cómo se calculan los valores?](#cálculo-valores)

2. **Detección Inteligente**: Identificar casos específicos de feminicidios con NNA11. [¿Es necesario cada paso?](#necesidad-pasos)

3. **Clasificación por Prioridad**: Determinar urgencia y relevancia de cada caso12. [¿Está dando resultados esperados?](#resultados-esperados)

4. **Eliminación de Duplicados**: Detectar la misma noticia en diferentes medios13. [Recomendaciones de Ajuste](#recomendaciones)

5. **Análisis ML**: Agrupar casos similares y descubrir tópicos

6. **Visualización**: Dashboard web para consulta y análisis---



---## <a name="introducción"></a>🎯 Introducción: ¿Qué hace este sistema?



## 🏗️ Arquitectura del Sistema### Objetivo Principal

Identificar **automáticamente** noticias sobre feminicidios que dejan niños huérfanos (NNA = Niñas, Niños y Adolescentes) en México.

### Diagrama de Componentes

### ¿Por qué es importante?

```- **Problema social**: Cada feminicidio puede dejar NNA en situación vulnerable

┌─────────────────────────────────────────────────────┐- **Volumen de información**: Miles de noticias diarias, imposible revisar manualmente

│                  FUENTES DE DATOS                   │- **Acción rápida**: Mientras más pronto se detecte un caso, más rápido se puede dar apoyo

├─────────────┬──────────────┬────────────────────────┤

│  RSS Feeds  │ Google News  │ Búsqueda Histórica     │### ¿Cómo lo hace?

│  (10 feeds) │  (150 res)   │  (6 meses, 250 res)    │Usa **6 pasos secuenciales**, cada uno con un propósito específico:

└──────┬──────┴──────┬───────┴────────┬───────────────┘

       │             │                │```

       └─────────────┴────────────────┘Internet → [RECOLECCIÓN] → [DETECTOR] → [VECTORIZACIÓN] → [TÓPICOS] → [CLUSTERING] → [SIMILITUD] → Dashboard

                     │```

                     ▼

       ┌─────────────────────────┐---

       │   DATA COLLECTOR        │

       │  - Unificación          │## <a name="paso-1-recolección"></a>📰 PASO 1: Recolección de Noticias

       │  - Limpieza             │

       │  - Deduplicación        │### ¿Qué hace?

       └────────────┬────────────┘Busca y descarga noticias de **2 tipos de fuentes**:

                    │1. **RSS Feeds**: 8 medios especializados en temas de género

                    ▼2. **Google News**: Búsqueda específica con palabras clave

       ┌─────────────────────────┐

       │  FEMINICIDE DETECTOR    │### ¿Por qué es necesario?

       │  - 40+ patrones regex   │**Sin noticias NO hay nada que analizar.** Este es el combustible del sistema.

       │  - 17 exclusiones       │

       │  - Cálculo confianza    │### Parámetros que usa

       └────────────┬────────────┘

                    │#### 🔹 RSS Feeds (8 fuentes configuradas)

                    ▼```python

       ┌─────────────────────────┐RSS_FEEDS = [

       │   SIMPLIFIED ANALYZER   │    'https://cimacnoticias.com.mx/feed',              # CIMAC - Especializado en género

       │  ┌──────────────────┐   │    'https://semmexico.mx/feed',                       # SEM México - Feminismo

       │  │  1. TF-IDF       │   │    'https://www.jornada.com.mx/rss/edicion.xml',     # La Jornada - General

       │  │     (3000 feat)  │   │    # ... 5 fuentes más

       │  └────────┬─────────┘   │]

       │           │             │```

       │  ┌────────▼─────────┐   │

       │  │  2. LDA          │   │**¿Qué valores toma?**

       │  │     (8 topics)   │   │- **URL de cada feed**: Dirección del RSS

       │  └────────┬─────────┘   │- **Timeout**: 10 segundos por fuente

       │           │             │- **Intentos**: 3 reintentos si falla

       │  ┌────────▼─────────┐   │- **User-Agent**: Simula navegador para evitar bloqueos

       │  │  3. DBSCAN       │   │

       │  │     (clustering) │   │#### 🔹 Google News

       │  └────────┬─────────┘   │```python

       │           │             │GOOGLE_NEWS_CONFIG = {

       │  ┌────────▼─────────┐   │    'query': 'feminicidio OR "violencia contra la mujer" OR "asesinato de mujer"',

       │  │  4. Similitud    │   │    'max_results': 30,

       │  │     (duplicados) │   │    'language': 'es',

       │  └────────┬─────────┘   │    'region': 'MX'

       └───────────┼─────────────┘}

                   │```

                   ▼

       ┌─────────────────────────┐**¿Qué valores toma?**

       │   DATA STORAGE          │- **Query**: Palabras clave combinadas con OR

       │  - noticias.csv         │- **max_results**: Máximo 30 noticias

       │  - clusters_info.csv    │- **language**: Solo español

       │  - synonym_dict.json    │- **region**: Solo México

       └────────────┬────────────┘

                    │### Ejemplo de Salida

                    ▼

       ┌─────────────────────────┐**Entrada**: URLs de RSS + Query de Google  

       │   FLASK WEB APP         │**Salida**: DataFrame con ~50-100 noticias

       │  - API REST             │

       │  - Dashboard HTML       │```

       │  - Búsqueda inteligente │| titulo                                    | fuente    | contenido            | fecha      |

       └─────────────────────────┘|-------------------------------------------|-----------|----------------------|------------|

```| "Feminicidio en Edomex deja 3 huérfanos" | CIMAC     | "Una mujer de 35..." | 2025-11-15 |

| "Asesinan a madre en Puebla"             | La Jornada| "Autoridades..."     | 2025-11-16 |

---```



## 📦 Módulos Principales### ¿Está dando resultados esperados?



### 1. `data_collector.py` - Recolector de Datos✅ **BIEN** si:

- Recolecta >50 noticias

**Función:** Centralizar la recolección desde múltiples fuentes- Al menos 20% son sobre feminicidios

- Hay variedad de fuentes

**Fuentes:**

- **RSS Feeds (10)**: Medios especializados en género⚠️ **AJUSTAR** si:

- **Google News (150)**: Noticias recientes- <30 noticias → Agregar más fuentes RSS

- **Historical Scraper (250)**: 6 meses de historial- <10% feminicidios → Ajustar query de Google News

- Todas de la misma fuente → Verificar que otros RSS funcionen

**Proceso:**

```python---

def collect_all_news():

    """## <a name="paso-2-detector"></a>🔍 PASO 2: Detector de Feminicidios

    1. Recolecta desde RSS feeds

    2. Complementa con Google News### ¿Qué hace?

    3. Añade búsqueda histórica (opcional)Analiza **cada noticia** con **40+ patrones regex** para determinar:

    4. Deduplica por URL1. ¿Es sobre un feminicidio? ✓

    5. Detecta feminicidios + NNA2. ¿Menciona hijos/NNA? ✓

    6. Retorna DataFrame limpio3. ¿Habla de huérfanos? ✓

    """

```### ¿Por qué es necesario?

**Filtra el ruido.** De 100 noticias recolectadas, solo 10-20 son realmente relevantes.

**Salida:**

```csv### Parámetros que usa

titulo,contenido,fecha,fuente,url,es_feminicidio,menores_identificados,confidence,prioridad

```#### 🔹 Patrones de Feminicidio (Peso: 40%)

```python

---feminicide_patterns = [

    r'\bfeminicidio\b',

### 2. `feminicide_detector.py` - Detector Especializado    r'\basesinat[oa]\b.*\bmujer\b',

    r'\bmataron?\b.*\b(?:mujer|femenina)\b',

**Función:** Identificar casos de feminicidios con NNA y calcular prioridad    r'\bhallaron?\b.*\bcuerpo\b.*\bmujer\b',

    # ... 40+ patrones más

#### Patrones de Detección]

```

**A. Feminicidio (Peso: 40%)**

```python**¿Qué palabras busca?**

feminicidio_patterns = [- feminicidio, asesinato, mataron, hallaron cuerpo

    r'\bfeminicidio[s]?\b',- violencia de género, crimen machista

    r'\bfemicidio[s]?\b',- encontraron muerta, muerte violenta

    r'\bmujer\s+(asesinada|hallada\s+muerta)',

    r'\bviolencia\s+feminicida',#### 🔹 Patrones de NNA/Hijos (Peso: 20%)

    r'\bcrimen\s+de\s+g[eé]nero',```python

    # ... 20+ patrones máschildren_patterns = [

]    r'\bhijos?\b',

```    r'\bniñ[oa]s?\b',

    r'\bmenor(?:es)?\b',

**B. Menciones NNA (Peso: 20%)**    r'\badolescente\b',

```python    # ...

children_patterns = []

    r'\bhijos?\b',```

    r'\bni[ñn]os?\b',

    r'\bni[ñn]as?\b',**¿Qué palabras busca?**

    r'\badolescentes?\b',- hijos, hijas, niños, niñas

    r'\bmenores?\s+de\s+edad',- menores, adolescentes, bebé

    r'\bbeb[eé]s?\b',- infantes, pequeños

    # ... 15+ patrones más

]#### 🔹 Patrones de Orfandad (Peso: 30% + 10% bonus)

``````python

orphan_patterns = [

**C. Orfandad (Peso: 40%)**    r'\bhu[eé]rfan[oa]s?\b',

```python    r'\bquedar[oa]n?\b.*\bdesamparad[oa]s?\b',

orphan_patterns = [    r'\bsin\b.*\bmadre\b',

    r'\bhu[eé]rfanos?\b',    r'\babandon[oa](?:dos|das)\b',

    r'\borfandad\b',    # ...

    r'\bhijos?\s+quedan',]

    r'\bsin\s+madre',```

    r'\bv[ií]ctimas?\s+indirectas?',

    r'\bDIF\s+se\s+hace\s+cargo',**¿Qué palabras busca?**

    # ... 10+ patrones más- huérfanos, quedaron sin madre

]- desamparados, abandonados

```- apoyo a menores, custodia



#### Patrones de Exclusión (17)### ¿Cómo calcula la puntuación?



**Filtran noticias que NO son casos individuales:**```python

# Ejemplo de noticia

```pythontexto = "Feminicidio en Edomex deja 3 huérfanos"

exclusion_patterns = [

    # Estadísticas# 1. Cuenta coincidencias

    r'\bconcentra\s+(la\s+)?cuarta\s+parte',feminicidio_count = 1   # Encontró "feminicidio"

    r'\bestadística[s]?\s+(de|sobre|señala)',nna_count = 0           # NO encontró "hijos", "niños", etc.

    r'\b\d+%\s+(de\s+las|son|corresponde)',orfandad_count = 1      # Encontró "huérfanos"

    

    # Datos oficiales# 2. Normaliza (divide entre número de patrones)

    r'\bdatos?\s+(del|de\s+la)\s+(INEGI|gobierno)',feminicidio_score = 1 / 40 * 0.40 = 0.010

    r'\bseg[uú]n\s+(el\s+)?INEGI',nna_score = 0 / 15 * 0.20 = 0.000

    r'\bcifras?\s+(oficiales?|del\s+gobierno)',orfandad_score = 1 / 20 * 0.30 = 0.015

    

    # Trata de personas (categoría separada)# 3. Bonus si menciona huérfanos

    r'\btrata\s+de\s+(personas|blancas)',orfandad_bonus = 0.10

    r'\bv[i]ctima[s]?\s+de\s+trata',

    # 4. Suma total

    # Programas y políticasconfianza = 0.010 + 0.000 + 0.015 + 0.10 = 0.125 (12.5%)

    r'\bprograma\s+(social|de\s+gobierno)',```

    r'\bpol[i]tica\s+p[u]blica',

    r'\biniciativa\s+de\s+ley',### Clasificación por Confianza

    

    # Campañas```python

    r'\bcampa[ñ]a\s+(de\s+concientizaci[óo]n|social)',if confianza >= 0.70:

    r'\bjornada\s+de\s+sensibilizaci[óo]n',    prioridad = "ALTA"      # ✅ Caso confirmado

    elif confianza >= 0.40:

    # ... 5 patrones más    prioridad = "MEDIA"     # ⚠️ Posible caso

]else:

```    prioridad = "BAJA"      # ⏸️ Poco probable

```

#### Cálculo de Confianza

### Ejemplo de Salida

```python

def _calculate_confidence(self, detection_results: dict) -> float:**Entrada**: "Feminicidio en Edomex deja 3 huérfanos"

    """

    Confidence = (Feminicidio × 0.4) + (NNA × 0.2) + (Orfandad × 0.3)**Salida**:

    ```json

    Bonus: +10% si tiene patrones de orfandad{

    """    "is_feminicide": true,

    confidence = (    "has_children": false,

        detection_results['feminicide_score'] * 0.4 +    "has_orphans": true,

        detection_results['children_score'] * 0.2 +    "is_target_news": true,

        detection_results['orphan_score'] * 0.3    "confidence": 0.125,

    )    "priority": "BAJA",

        "scores": {

    if detection_results['has_orphans']:        "feminicide_score": 0.010,

        confidence += 0.1  # Bonus        "children_score": 0.000,

            "orphan_score": 0.015

    return min(confidence, 1.0)    }

```}

```

#### Sistema de Prioridades

### ¿Está dando resultados esperados?

```python

def _calculate_priority(self, detection_results: dict, confidence: float) -> str:✅ **BIEN** si:

    """- Detecta 15-30% de noticias como feminicidios

    ALTA:        Feminicidio + NNA + Confianza ≥ 70%- Al menos 10% son "OBJETIVO" (tiene NNA)

    MEDIA:       Feminicidio + NNA + Confianza 40-69%- Confianza >70% para casos claros

    BAJA:        Algún indicador + Confianza 20-39%

    IRRELEVANTE: Confianza < 20% o excluido⚠️ **AJUSTAR** si:

    """- <5% son objetivo → Patrones muy estrictos, reducir umbral de confianza

    if confidence >= 0.7 and detection_results['is_target_news']:- >50% son objetivo → Sobre-detectando, aumentar umbral

        return 'ALTA'- Falsos positivos → Agregar patrones de exclusión

    elif confidence >= 0.4:

        return 'MEDIA'---

    elif confidence >= 0.2:

        return 'BAJA'## <a name="paso-3-vectorización"></a>🔢 PASO 3: Vectorización TF-IDF

    else:

        return 'IRRELEVANTE'### ¿Qué hace?

```Convierte **texto en números** que los algoritmos de Machine Learning pueden procesar.



---### ¿Por qué es necesario?

**Los algoritmos ML NO entienden palabras, solo números.**

### 3. `simplified_analyzer.py` - Pipeline ML

**Ejemplo**:

**Función:** Análisis completo con Machine Learning```

Texto: "Feminicidio en Edomex deja huérfanos"

#### Paso 1: Vectorización TF-IDFVector: [0.8, 0.0, 0.6, 0.0, 0.4, ..., 0.0]

         ↑         ↑         ↑

```python    feminicidio  mujer   huérfanos

from sklearn.feature_extraction.text import TfidfVectorizer```



tfidf = TfidfVectorizer(### Parámetros que usa

    max_features=3000,      # 3000 características

    min_df=1,               # Mínimo 1 documento```python

    max_df=0.8,             # Máximo 80% documentosTFIDF_CONFIG = {

    ngram_range=(1, 2),     # Unigramas y bigramas    'max_features': 1000,      # Solo las 1000 palabras más importantes

    encoding='utf-8-sig'    'min_df': 1,               # Palabra debe aparecer mínimo 1 vez

)    'max_df': 0.95,            # Ignora si aparece en >95% de documentos

    'ngram_range': (1, 2),     # Palabras individuales (1) y pares (2)

tfidf_matrix = tfidf.fit_transform(textos_limpios)    'strip_accents': None,     # Preserva acentos (feminicidio ≠ feminicido)

# Resultado: Matriz (N noticias, 3000 features)    'lowercase': True,         # Todo a minúsculas

```    'stop_words': None         # NO elimina palabras comunes (español)

}

**¿Qué hace?**```

- Convierte texto a números

- Palabras más raras tienen mayor peso### ¿Qué significan estos parámetros?

- Palabras muy comunes se ignoran

#### 🔹 max_features = 1000

#### Paso 2: Topic Modeling (LDA)**¿Qué hace?**: Solo guarda las 1000 palabras más relevantes



```python**¿Por qué?**: 

from sklearn.decomposition import LatentDirichletAllocation- Reduce dimensionalidad (memoria, velocidad)

- Elimina palabras raras que no aportan

lda = LatentDirichletAllocation(

    n_components=8,         # 8 tópicos**Ejemplo**:

    random_state=42,```

    max_iter=10ANTES: 50,000 palabras únicas (incluye typos, nombres raros)

)DESPUÉS: 1,000 palabras más frecuentes/relevantes

```

topic_distribution = lda.fit_transform(tfidf_matrix)

```#### 🔹 min_df = 1

**¿Qué hace?**: Palabra debe aparecer en al menos 1 documento

**Ejemplo de Tópicos Descubiertos:**

```**¿Por qué?**: Con min_df=1 acepta todas las palabras (sin filtro mínimo)

Tópico 0: feminicidio, país, animal político, violencia

Tópico 1: feminicidio, marcha, hijos, mujer**Si cambias a min_df=2**:

Tópico 2: ciudad, méxico, generación, crimen```

Tópico 3: méxico, feminicidio, huérfanos, víctimas"feminicidio" aparece en 50 docs → ✅ Se incluye

Tópico 4: feminicidio, infantil, niños, méxico"Edomex" aparece en 30 docs → ✅ Se incluye

```"Zacatepec" aparece en 1 doc → ❌ Se elimina

```

#### Paso 3: Clustering (DBSCAN)

#### 🔹 max_df = 0.95

```python**¿Qué hace?**: Ignora palabras que aparecen en >95% de documentos

from sklearn.cluster import DBSCAN

**¿Por qué?**: Palabras muy comunes no discriminan (ej: "de", "la", "que")

dbscan = DBSCAN(

    eps=0.8,                # Distancia máxima**Ejemplo**:

    min_samples=2,          # Mínimo por cluster```

    metric='cosine'         # Similitud coseno"mujer" aparece en 98% docs → ❌ Eliminada (demasiado común)

)"feminicidio" aparece en 60% docs → ✅ Incluida

```

clusters = dbscan.fit_predict(tfidf_matrix)

```#### 🔹 ngram_range = (1, 2)

**¿Qué hace?**: Considera palabras solas (1) y pares (2)

**¿Qué hace?**

- Agrupa noticias similares**¿Por qué?**: Captura contexto

- eps=0.8 → similitud > 20%

- No necesita definir # clusters previamente**Ejemplo**:

```

**Ejemplo de Resultado:**Texto: "violencia de género"

```

Cluster 0 (6 noticias): feminicidio, datos, polítican=1 (unigrams): ["violencia", "de", "género"]

Cluster 1 (5 noticias): cimacnoticias, sem méxicon=2 (bigrams):  ["violencia de", "de género"]

Outliers (214 noticias): Casos únicos

```AMBOS se incluyen → "violencia de género" vale más que solo "violencia"

```

#### Paso 4: Detección de Duplicados

### ¿Cómo calcula TF-IDF?

```python

from sklearn.metrics.pairwise import cosine_similarity**TF-IDF = Term Frequency × Inverse Document Frequency**



# Calcular similitud entre todas las noticias#### Ejemplo con la palabra "feminicidio":

similarity_matrix = cosine_similarity(tfidf_matrix)

```

# Encontrar duplicados (similitud > 75%)Documento 1: "Feminicidio en Edomex deja 3 huérfanos"

for i in range(len(noticias)):             └─ "feminicidio" aparece 1 vez en 7 palabras

    for j in range(i+1, len(noticias)):

        if similarity_matrix[i][j] >= 0.75:TF (Term Frequency) = 1 / 7 = 0.143

            # Marcar como duplicado

            noticias.at[j, 'es_duplicado'] = TrueTenemos 100 documentos, "feminicidio" aparece en 60

            noticias.at[j, 'titulo_original'] = noticias.at[i, 'titulo']IDF (Inverse Document Frequency) = log(100 / 60) = 0.511

            noticias.at[j, 'fuente_original'] = noticias.at[i, 'fuente']

```TF-IDF = 0.143 × 0.511 = 0.073

```

---

**¿Qué significa?**

### 4. `synonym_dictionary.py` - Búsqueda Inteligente- **TF-IDF alto** (>0.5): Palabra importante y específica de este documento

- **TF-IDF medio** (0.1-0.5): Palabra relevante pero común

**Función:** Expandir términos de búsqueda con sinónimos- **TF-IDF bajo** (<0.1): Palabra poco relevante



#### Diccionario (147 términos)### Ejemplo de Salida



```python**Entrada**: 100 noticias de texto

SYNONYM_DICT = {

    "feminicidio": [**Salida**: Matriz de 100 × 1000

        "femicidio",

        "asesinato de mujer",```

        "homicidio de mujer",         feminicidio  mujer  hijos  edomex  ...  (1000 palabras)

        "crimen de género",Noticia1    0.80      0.30   0.60   0.50   ...

        "violencia feminicida",Noticia2    0.85      0.40   0.00   0.00   ...

        "muerte violenta de mujer"Noticia3    0.00      0.70   0.00   0.20   ...

    ],...

    Noticia100  0.75      0.35   0.55   0.45   ...

    "niños": [```

        "niñas",

        "menores",### ¿Qué palabras REALMENTE toma en cuenta?

        "NNA",

        "infantes",**Top 20 palabras con mayor peso** (ejemplo real):

        "adolescentes",1. **feminicidio** (peso: 45.2)

        "pequeños",2. **mujer** (peso: 38.7)

        "críos"3. **hijos** (peso: 22.5)

    ],4. **edomex** (peso: 18.3)

    5. **asesinato** (peso: 16.9)

    "huérfanos": [6. **madre** (peso: 15.8)

        "orfandad",7. **huérfanos** (peso: 14.2)

        "sin madre",8. **violencia género** (peso: 12.3) ← bigram

        "sin padres",9. **niños** (peso: 11.5)

        "víctimas indirectas",10. **menores** (peso: 10.8)

        "hijos quedan"...

    ],

    ### ¿Está dando resultados esperados?

    # ... 144 términos más

}✅ **BIEN** si:

```- Matriz tiene dimensiones ~100 × 1000

- Top palabras incluyen: feminicidio, mujer, hijos, huérfanos

#### Ejemplo de Uso- >500 features (palabras únicas)



```python⚠️ **AJUSTAR** si:

# Búsqueda: "feminicidio"- <500 features → Reducir max_df o aumentar max_features

query = "feminicidio"- Top palabras son genéricas ("de", "la", "que") → Agregar stopwords español

expanded_query = synonym_dict.expand_query(query)- Faltan acentos → Verificar strip_accents=None



# Resultado:---

# feminicidio|femicidio|asesinato de mujer|homicidio de mujer|...

```## <a name="paso-4-tópicos"></a>📊 PASO 4: Modelado de Tópicos (LDA)



---### ¿Qué hace?

Encuentra **temas comunes** en las noticias usando **Latent Dirichlet Allocation (LDA)**.

## 📊 API y Dashboard

### ¿Por qué es necesario?

### Flask App (`app_docker.py`)**Agrupa noticias por tema**, no solo por palabras exactas.



#### Endpoints Principales**Ejemplo de tópicos descubiertos**:

- **Tópico 1**: feminicidio + edomex + asesinato + investigación

**1. GET `/api/stats`**- **Tópico 2**: apoyo + huérfanos + gobierno + custodia + albergue

- **Tópico 3**: violencia + género + manifestación + justicia

```python

@app.route('/api/stats')### Parámetros que usa

def get_stats():

    df = pd.read_csv('data/noticias.csv', encoding='utf-8-sig')```python

    LDA_CONFIG = {

    return {    'n_components': 6,        # Buscar 6 temas diferentes

        'total_noticias': len(df),    'random_state': 42,       # Semilla para reproducibilidad

        'noticias_nna': len(df[df['menores_identificados'] == 'Si']),    'max_iter': 20,           # Iteraciones del algoritmo

        'clusters': df['cluster'].nunique(),    'learning_method': 'online'  # Más rápido para datos grandes

        'topics': df['topic_id'].nunique(),}

        'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M:%S')```

    }

```### ¿Qué significa n_components = 6?



**2. GET `/api/noticias`****Le dice al algoritmo: "Encuentra 6 temas principales"**



```python**¿Cómo decide qué temas?**

@app.route('/api/noticias')El algoritmo LDA busca palabras que **co-ocurren frecuentemente**:

def get_noticias():

    page = int(request.args.get('page', 1))```

    per_page = int(request.args.get('per_page', 10))Si "feminicidio", "edomex", "asesinato" aparecen juntas → Tópico 1

    only_nna = request.args.get('only_nna', 'false') == 'true'Si "apoyo", "huérfanos", "gobierno" aparecen juntas → Tópico 2

    ```

    df = pd.read_csv('data/noticias.csv', encoding='utf-8-sig')

    ### Ejemplo de Salida

    # Filtrar por NNA si se solicita

    if only_nna:**Entrada**: Matriz TF-IDF (100 × 1000)

        df = df[

            (df['menores_identificados'] == 'Si') & **Salida**: 6 tópicos con palabras clave

            (df['es_objetivo'] == True)

        ]```

    Tópico 0: feminicidio, edomex, mujer, asesinato, investigación, fiscalía

    # Ordenar por prioridadTópico 1: apoyo, huérfanos, gobierno, custodia, dif, albergue

    priority_order = {'ALTA': 0, 'MEDIA': 1, 'BAJA': 2, 'IRRELEVANTE': 3}Tópico 2: violencia, género, manifestación, justicia, marcha, protesta

    df['priority_num'] = df['prioridad'].map(priority_order)Tópico 3: madre, hijos, menores, niños, familia, abuela

    df = df.sort_values('priority_num')Tópico 4: cuerpo, hallaron, localizado, abandonado, carretera

    Tópico 5: pareja, ex, esposo, relación, celos, discusión

    # Paginar```

    start = (page - 1) * per_page

    end = start + per_page**Asignación de noticias**:

    noticias_page = df.iloc[start:end]```

    Noticia 1: "Feminicidio en Edomex..." → Tópico 0 (70% prob)

    return {Noticia 2: "DIF apoya a huérfanos..." → Tópico 1 (85% prob)

        'noticias': noticias_page.to_dict('records'),Noticia 3: "Marcha por justicia..." → Tópico 2 (60% prob)

        'page': page,```

        'total_pages': math.ceil(len(df) / per_page),

        'total': len(df)### ¿Cómo se calculan los valores?

    }

```**LDA usa probabilidades**:



**3. GET `/api/search`**Cada noticia es una **mezcla de tópicos**:

```

```pythonNoticia X:

@app.route('/api/search')  30% Tópico 0 (feminicidio)

def search_news():  50% Tópico 1 (apoyo huérfanos)  ← Tópico dominante

    query = request.args.get('q', '')  10% Tópico 3 (familia)

      10% Otros

    # Expandir con sinónimos```

    expanded_query = synonym_dict.expand_query(query)

    **El sistema asigna la noticia al tópico con mayor probabilidad.**

    df = pd.read_csv('data/noticias.csv', encoding='utf-8-sig')

    ### ¿Está dando resultados esperados?

    # Buscar en título, contenido y fuente

    mask = (✅ **BIEN** si:

        df['titulo'].str.contains(expanded_query, case=False, regex=True, na=False) |- Los 6 tópicos son **interpretables** (tienen sentido temático)

        df['contenido'].str.contains(expanded_query, case=False, regex=True, na=False) |- Distribución balanceada (cada tópico tiene ~15-20% de noticias)

        df['fuente'].str.contains(expanded_query, case=False, regex=True, na=False)- Perplexity <100 (métrica de calidad del modelo)

    )

    ⚠️ **AJUSTAR** si:

    results = df[mask].head(50)- Tópicos no tienen sentido → Reducir n_components a 4-5

    - Un tópico tiene >50% noticias → Aumentar n_components a 8-10

    # Ordenar por prioridad- Perplexity >150 → Aumentar max_iter o cambiar learning_method

    priority_order = {'ALTA': 0, 'MEDIA': 1, 'BAJA': 2, 'IRRELEVANTE': 3}

    results['priority_num'] = results['prioridad'].map(priority_order)---

    results = results.sort_values('priority_num')

    ## <a name="paso-5-clustering"></a>🔗 PASO 5: Clustering (DBSCAN)

    return {

        'noticias': results.to_dict('records'),### ¿Qué hace?

        'resultados': len(results)Agrupa noticias **MUY similares** usando **DBSCAN** (Density-Based Spatial Clustering).

    }

```### ¿Por qué es necesario?

**Identifica casos duplicados o relacionados** al mismo evento.

**4. POST `/api/analyze`**

**Diferencia con LDA (Paso 4)**:

```python- **LDA**: Agrupa por TEMA general (ej: "apoyo huérfanos")

@app.route('/api/analyze', methods=['POST'])- **DBSCAN**: Agrupa por SIMILITUD exacta (ej: "mismo feminicidio reportado 3 veces")

def run_analysis():

    try:### Parámetros que usa

        # 1. Recolectar noticias

        df_noticias = collect_all_news()```python

        DBSCAN_CONFIG = {

        # 2. Guardar datos crudos    'eps': 0.6,                # Distancia máxima para agrupar

        df_noticias.to_csv('data/noticias.csv',     'min_samples': 2,          # Mínimo 2 noticias para cluster

                          index=False,     'metric': 'cosine'         # Similitud coseno

                          encoding='utf-8-sig')}

        ```

        # 3. Ejecutar análisis ML

        analyzer = SimplifiedNewsAnalyzer()### ¿Qué significa eps = 0.6?

        df_analyzed = analyzer.analyze_full_pipeline(df_noticias)

        **eps** = **epsilon** = radio de vecindad

        # 4. Guardar resultados

        df_analyzed.to_csv('data/noticias_analyzed.csv', **En similitud coseno**:

                          index=False, - eps=0.6 → Distancia ≤ 0.6 → **Similitud ≥ 40%**

                          encoding='utf-8-sig')- eps=0.4 → Distancia ≤ 0.4 → **Similitud ≥ 60%** (más estricto)

        - eps=0.8 → Distancia ≤ 0.8 → **Similitud ≥ 20%** (más permisivo)

        return {

            'success': True,**Ejemplo**:

            'noticias_recolectadas': len(df_noticias),```

            'noticias_nna': len(df_analyzed[df_analyzed['menores_identificados'] == 'Si']),Noticia A: "Feminicidio en Edomex deja 3 huérfanos"

            'clusters': df_analyzed['cluster'].nunique(),Noticia B: "Asesinan mujer en Edomex, 3 niños quedan solos"

            'topics': df_analyzed['topic_id'].nunique()

        }Similitud = 75% → Distancia = 0.25 < 0.6 → ✅ MISMO CLUSTER

        ```

    except Exception as e:

        return {'error': str(e)}, 500### ¿Qué significa min_samples = 2?

```

**Para formar un cluster, necesita al menos 2 noticias.**

---

**Ejemplo**:

## 🐳 Deployment con Docker```

Cluster 1:

### docker-compose.yml  • Noticia A (CNN)

  • Noticia B (La Jornada)    } Mismo feminicidio, fuentes distintas

```yaml  • Noticia C (Excélsior)

version: '3.8'

Outlier (cluster -1):

services:  • Noticia D (caso único, sin similares)

  nna-analyzer:```

    build: .

    container_name: nna-analyzer### Ejemplo de Salida

    volumes:

      - ./data:/app/data**Entrada**: Matriz TF-IDF (100 × 1000)

      - ./logs:/app/logs

    environment:**Salida**: Clusters + Outliers

      - ANALYSIS_MODE=scheduled

      - INTERVAL_HOURS=24```

    restart: alwaysCluster 0 (5 noticias):

      Palabras clave: feminicidio, edomex, ecatepec, 35 años

  nna-webapp:  • "Feminicidio en Ecatepec deja 3 huérfanos" (CIMAC)

    build: .  • "Asesinan mujer en Edomex, niños quedan solos" (La Jornada)

    container_name: nna-webapp  • "Matan a madre de familia en Ecatepec" (Excélsior)

    ports:  

      - "5000:5000"Cluster 1 (3 noticias):

    volumes:  Palabras clave: dif, apoyo, custodia, abuelos

      - ./data:/app/data  • "DIF otorga custodia a abuelos de huérfanos" (Milenio)

      - ./logs:/app/logs  • "Abuelos reciben apoyo para niños" (SEM México)

    depends_on:  

      - nna-analyzerOutliers (-1): 92 noticias

    restart: always  • Casos únicos sin similitud suficiente

    command: python app_docker.py```

```

### ¿Cómo calcula la calidad del clustering?

### Dockerfile

**Silhouette Score** (entre -1 y 1):

```dockerfile- **>0.5**: Excelente separación de clusters

FROM python:3.11-slim- **0.3-0.5**: Buena separación

- **<0.3**: Clusters mal definidos

# Usuario no privilegiado

RUN groupadd -r appuser && useradd -r -g appuser appuser```python

silhouette_score = 0.42  # BUENO

# Instalar dependencias del sistema```

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

### ¿Está dando resultados esperados?

WORKDIR /app

✅ **BIEN** si:

# Copiar requirements- Silhouette >0.3

COPY requirements.txt .- 10-40% de outliers (casos únicos)

RUN pip install --no-cache-dir -r requirements.txt- Clusters tienen sentido temático



# Copiar código⚠️ **AJUSTAR** si:

COPY . .- >90% outliers → **eps demasiado pequeño**, aumentar a 0.7-0.8

- <10% outliers → **eps muy grande**, reducir a 0.4-0.5

# Permisos- Silhouette <0.3 → Ajustar eps o probar K-Means

RUN mkdir -p data logs && chown -R appuser:appuser /app

**NOTA IMPORTANTE**: En noticias es **NORMAL** tener muchos outliers (70-85%) porque cada caso es único.

USER appuser

---

# Healthcheck

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \## <a name="paso-6-similitud"></a>🔄 PASO 6: Análisis de Similitud

  CMD curl -f http://localhost:5000/ || exit 1

### ¿Qué hace?

EXPOSE 5000Calcula **similitud coseno** entre cada par de noticias.

```

### ¿Por qué es necesario?

---**Permite recomendar noticias relacionadas** y detectar duplicados.



## 🔄 Flujo Completo del Sistema### ¿Cómo calcula la similitud?



### Ciclo de Análisis (Cada 24 horas)**Similitud Coseno** = Coseno del ángulo entre dos vectores



``````

1. INICIO (00:00 AM)Vector A = [0.8, 0.3, 0.6]  (feminicidio, mujer, hijos)

   │Vector B = [0.9, 0.4, 0.5]  (similar)

   ├─> Recolectar RSS (10 feeds)           → ~60-70 noticias

   ├─> Recolectar Google News               → ~150 noticiasSimilitud = cos(θ) = (A · B) / (|A| × |B|)

   └─> Buscar Histórico (6 meses)          → ~250 noticias          = 0.92  (92% similares)

   ```

2. UNIFICACIÓN

   │### Ejemplo de Salida

   └─> Deduplicar por URL                   → ~280-300 noticias únicas

   **Entrada**: Matriz TF-IDF (100 × 1000)

3. DETECCIÓN

   │**Salida**: Para cada noticia, su noticia más similar

   ├─> Aplicar patrones de feminicidio

   ├─> Aplicar patrones de NNA```

   ├─> Aplicar patrones de exclusiónNoticia 1: "Feminicidio en Edomex..."

   └─> Calcular confianza y prioridad       → ~126 casos NNA  → Más similar: Noticia 47 (similitud: 0.85)

     

4. ANÁLISIS MLNoticia 2: "DIF apoya huérfanos..."

   │  → Más similar: Noticia 12 (similitud: 0.62)

   ├─> TF-IDF Vectorization```

   ├─> LDA Topic Modeling                   → 8 tópicos

   ├─> DBSCAN Clustering                    → 6-7 clusters### ¿Está dando resultados esperados?

   └─> Detección de duplicados (75%)        → ~6 duplicados

   ✅ **BIEN** si:

5. ALMACENAMIENTO- Similitud promedio: 0.15-0.35

   │- Pares con similitud >0.7: 5-15% (posibles duplicados)

   ├─> Guardar noticias.csv

   ├─> Guardar clusters_info.csv⚠️ **REVISAR** si:

   └─> Guardar synonym_dictionary.json- Similitud promedio <0.10 → Noticias muy diversas (normal)

   - Similitud promedio >0.50 → Muchos duplicados, filtrar en recolección

6. DISPONIBILIDAD

   │---

   └─> Dashboard actualizado en tiempo real

```## <a name="flujo-completo"></a>🔄 Flujo Completo con Ejemplo



---### Entrada: 1 Noticia Real



## 📈 Ejemplo de Resultados```

Título: "Feminicidio en Ecatepec deja tres menores huérfanos"

### Caso Real: Análisis CompletoContenido: "Una mujer de 35 años fue asesinada en su domicilio de 

Ecatepec, Estado de México. La víctima deja tres hijos menores de 

```edad en situación de orfandad. La fiscalía inició investigación por 

═══════════════════════════════════════════════════════feminicidio."

 ANÁLISIS COMPLETADO EXITOSAMENTE```

═══════════════════════════════════════════════════════

### PASO 1: Recolección ✅

📊 ESTADÍSTICAS GENERALES:```

   • Total noticias recolectadas: 281Fuente: CIMAC

   • Casos con menciones NNA: 126 (44.8%)Fecha: 2025-11-18

   • Noticias objetivo (ALTA): 8 (2.8%)Status: ✓ Recolectada exitosamente

   • Noticias duplicadas: 6```



🏷️  TÓPICOS DESCUBIERTOS (LDA):### PASO 2: Detector ✅

   Tópico 0: feminicidios, país, animal, político```python

   Tópico 1: feminicidio, marcha, hijos, mujerAnálisis del detector:

   Tópico 2: mundial, drogas, ataques, senado  feminicidio: ✓ (encontrado 1 vez)

   Tópico 3: ciudad, méxico, feminicidio, generación  asesinato: ✓ (encontrado 1 vez)

   Tópico 4: méxico, feminicidio, huérfanos, víctimas  mujer: ✓ (encontrado 2 veces)

   Tópico 5: hernández, michoacán, plan, entidad  menores: ✓ (encontrado 1 vez)

   Tópico 6: feminicidio, infantil, niños, méxico  hijos: ✓ (encontrado 1 vez)

   Tópico 7: feminicidio, hijos, noticias, madre  huérfanos: ✓ (encontrado 1 vez)

  orfandad: ✓ (encontrado 1 vez)

📦 CLUSTERS FORMADOS (DBSCAN):

   • Cluster 0 (6 noticias): datos, política, blogPuntuación:

   • Cluster 1 (5 noticias): cimacnoticias, sem méxico  feminicide_score: 2/40 * 0.40 = 0.020

   • Cluster 2 (3 noticias): madre, hijos, oaxaca  children_score: 2/15 * 0.20 = 0.027

   • Cluster 3 (3 noticias): huérfanos, animal político  orphan_score: 2/20 * 0.30 = 0.030

   • Cluster 4 (3 noticias): madres, víctimas  orphan_bonus: 0.10

   • Cluster 5 (4 noticias): sol méxico, edomex  

   • Outliers (214): Casos únicos  TOTAL: 0.177 (17.7%)



🔄 DUPLICADOS DETECTADOS:Resultado:

   Grupo 1: "Feminicidio de niñas y adolescentes en México"  es_feminicidio: ✓

            → 6 versiones en diferentes fechas  tiene_nna: ✓

     es_objetivo: ✓

   Grupo 2: "Huérfanos por feminicidio en México"  prioridad: BAJA (confianza 17.7%)

            → 2 versiones en diferentes medios```



📊 MÉTRICAS ML:### PASO 3: Vectorización ✅

   • Silhouette Score: 0.48 (Bueno)```python

   • Perplexity LDA: 870,405Vector TF-IDF (top 10 palabras):

   • Similitud promedio: 0.281

   • Pares alta similitud (>50%): 27feminicidio: 0.352

ecatepec: 0.298

⏱️  TIEMPO DE EJECUCIÓN:huérfanos: 0.275

   • Recolección: 22 minutosmenores: 0.261

   • Análisis ML: 6 segundosasesinada: 0.248

   • Total: 22 min 6 segedomex: 0.234

```hijos: 0.221

mujer: 0.198

---fiscalía: 0.187

investigación: 0.165

## 🛠️ Troubleshooting... (990 palabras más con valores <0.15)

```

### Problema: No se recolectan noticias

### PASO 4: Tópicos ✅

**Solución:**```python

```bashDistribución por tópico:

# Verificar logs

docker-compose logs nna-analyzerTópico 0 (feminicidio edomex): 15%

Tópico 1 (apoyo huérfanos): 70%  ← ASIGNADO

# Revisar conectividadTópico 2 (violencia género): 5%

docker exec nna-analyzer ping -c 3 cimacnoticias.com.mxTópico 3 (familia niños): 8%

```Tópico 4 (hallazgo cuerpo): 1%

Tópico 5 (pareja ex): 1%

### Problema: Error UTF-8 en CSV

→ Asignada al Tópico 1 (apoyo huérfanos) con 70% probabilidad

**Solución:**```

```python

# Siempre usar encoding='utf-8-sig'### PASO 5: Clustering ✅

df.to_csv('archivo.csv', encoding='utf-8-sig')```python

pd.read_csv('archivo.csv', encoding='utf-8-sig')Análisis DBSCAN:

```

Buscando vecinos con similitud >40% (eps=0.6)...

### Problema: Dashboard no carga datos

Encontradas 2 noticias similares:

**Solución:**  • Noticia 47: "Asesinan mujer en Ecatepec, 3 niños solos" (sim: 0.78)

```bash  • Noticia 89: "Matan a madre en Edomex" (sim: 0.52)

# Verificar archivos

ls -lh data/→ Asignada al Cluster 3 (3 noticias del mismo caso)

```

# Debe existir:

# - noticias.csv### PASO 6: Similitud ✅

# - clusters_info.csv```python

# - synonym_dictionary.jsonNoticia más similar:

```  ID: 47

  Título: "Asesinan mujer en Ecatepec, 3 niños quedan solos"

---  Similitud: 0.78 (78%)

  

## 📚 Referencias→ Probable duplicado o caso relacionado

```

- **scikit-learn**: https://scikit-learn.org/

- **Flask**: https://flask.palletsprojects.com/### Salida Final

- **Docker**: https://docs.docker.com/```json

- **TF-IDF**: https://en.wikipedia.org/wiki/Tf%E2%80%93idf{

- **LDA**: https://en.wikipedia.org/wiki/Latent_Dirichlet_allocation  "titulo": "Feminicidio en Ecatepec deja tres menores huérfanos",

- **DBSCAN**: https://en.wikipedia.org/wiki/DBSCAN  "es_objetivo": true,

  "prioridad": "BAJA",

---  "confianza": 0.177,

  "topic_id": 1,

**Versión:** 3.0.0    "cluster": 3,

**Última Actualización:** 19 de noviembre de 2025  "max_similarity": 0.78,

  "most_similar_doc_idx": 47
}
```

---

## <a name="palabras-clave"></a>📝 ¿Qué palabras toma en cuenta?

### Palabras con MÁXIMO peso (Top 30)

| Palabra/Frase | Peso Total | Paso que la usa | ¿Por qué es importante? |
|---------------|------------|-----------------|-------------------------|
| **feminicidio** | 45.2 | Detector (40%), TF-IDF, LDA, Clustering | Palabra clave principal |
| **mujer** | 38.7 | Detector (40%), TF-IDF, LDA | Identifica víctima |
| **hijos** | 22.5 | Detector (20%), TF-IDF, LDA | Confirma presencia NNA |
| **huérfanos** | 18.3 | Detector (30%+10%), TF-IDF, LDA | Confirma objetivo |
| **edomex** | 16.9 | TF-IDF, LDA, Clustering | Ubicación frecuente |
| **asesinato** | 15.8 | Detector (40%), TF-IDF | Sinónimo feminicidio |
| **madre** | 14.2 | Detector (20%), TF-IDF, LDA | Relación con NNA |
| **menores** | 12.5 | Detector (20%), TF-IDF | Alternativa a "niños" |
| **violencia género** | 12.3 | Detector (40%), TF-IDF, LDA | Bigram importante |
| **niños** | 11.8 | Detector (20%), TF-IDF | Alternativa a "hijos" |
| **orfandad** | 10.9 | Detector (30%), TF-IDF | Confirma situación |
| **apoyo** | 10.2 | TF-IDF, LDA | Tópico de respuesta |
| **fiscalía** | 9.8 | TF-IDF, LDA | Contexto legal |
| **investigación** | 9.5 | TF-IDF, LDA | Proceso judicial |
| **cuerpo** | 8.7 | Detector (40%), TF-IDF | Hallazgo víctima |
| **dif** | 8.3 | TF-IDF, LDA | Institución apoyo |
| **custodia** | 7.9 | Detector (30%), TF-IDF | Situación legal NNA |
| **abuelos** | 7.5 | TF-IDF, LDA | Custodios frecuentes |
| **menores edad** | 7.2 | Detector (20%), TF-IDF | Bigram específico |
| **ecatepec** | 6.8 | TF-IDF, LDA | Ubicación frecuente |

### Palabras IGNORADAS (filtradas)

| Palabra | ¿Por qué se ignora? |
|---------|---------------------|
| de, la, el, un, una | **max_df=0.95**: Aparecen en >95% documentos |
| que, con, por, para | **max_df=0.95**: Muy comunes |
| Typos únicos | **min_df=1 + max_features=1000**: No entran en top 1000 |

---

## <a name="cálculo-valores"></a>🧮 ¿Cómo se calculan los valores?

### 1. Confianza del Detector (0-1)

```python
def calcular_confianza(texto):
    # Paso 1: Contar coincidencias
    fem_matches = contar_regex(texto, feminicide_patterns)  # ej: 2
    nna_matches = contar_regex(texto, children_patterns)    # ej: 1
    orf_matches = contar_regex(texto, orphan_patterns)      # ej: 1
    
    # Paso 2: Normalizar por número de patrones
    fem_score = (fem_matches / 40) * 0.40  # 2/40 * 0.40 = 0.020
    nna_score = (nna_matches / 15) * 0.20  # 1/15 * 0.20 = 0.013
    orf_score = (orf_matches / 20) * 0.30  # 1/20 * 0.30 = 0.015
    
    # Paso 3: Bonus si menciona huérfanos
    bonus = 0.10 if orf_matches > 0 else 0  # 0.10
    
    # Paso 4: Sumar
    confianza = fem_score + nna_score + orf_score + bonus
    # = 0.020 + 0.013 + 0.015 + 0.10 = 0.148 (14.8%)
    
    return confianza
```

### 2. Peso TF-IDF (0-1)

```python
def calcular_tfidf(palabra, documento, corpus):
    # Paso 1: Term Frequency (TF)
    tf = veces_aparece(palabra, documento) / total_palabras(documento)
    # "feminicidio" aparece 2 veces en 50 palabras
    # tf = 2 / 50 = 0.04
    
    # Paso 2: Inverse Document Frequency (IDF)
    idf = log(total_documentos / docs_con_palabra(palabra))
    # 100 docs totales, "feminicidio" aparece en 60
    # idf = log(100 / 60) = 0.511
    
    # Paso 3: Multiplicar
    tfidf = tf * idf
    # = 0.04 * 0.511 = 0.020
    
    return tfidf
```

### 3. Probabilidad Tópico (0-1)

```python
# LDA calcula distribución multinomial
# Ejemplo de noticia:

topic_distribution = [
    0.05,  # Tópico 0: 5%
    0.70,  # Tópico 1: 70% ← MÁXIMO
    0.10,  # Tópico 2: 10%
    0.08,  # Tópico 3: 8%
    0.05,  # Tópico 4: 5%
    0.02   # Tópico 5: 2%
]

# Asigna al tópico con mayor probabilidad
topic_id = argmax(topic_distribution) = 1
```

### 4. Similitud Coseno (0-1)

```python
def similitud_coseno(vector_a, vector_b):
    # Paso 1: Producto punto
    dot_product = sum(a[i] * b[i] for i in range(len(a)))
    # [0.8, 0.3, 0.6] · [0.9, 0.4, 0.5]
    # = 0.8*0.9 + 0.3*0.4 + 0.6*0.5 = 0.72 + 0.12 + 0.30 = 1.14
    
    # Paso 2: Magnitudes
    mag_a = sqrt(sum(a[i]**2 for i in range(len(a))))
    mag_b = sqrt(sum(b[i]**2 for i in range(len(b))))
    # mag_a = sqrt(0.64 + 0.09 + 0.36) = sqrt(1.09) = 1.044
    # mag_b = sqrt(0.81 + 0.16 + 0.25) = sqrt(1.22) = 1.105
    
    # Paso 3: Dividir
    similitud = dot_product / (mag_a * mag_b)
    # = 1.14 / (1.044 * 1.105) = 1.14 / 1.154 = 0.988
    
    return similitud  # 0.988 (98.8% similares)
```

### 5. Silhouette Score (-1 a 1)

```python
def silhouette_score(noticia, cluster):
    # a = distancia promedio a noticias del MISMO cluster
    a = promedio_distancia_intra_cluster(noticia, cluster)
    # ej: a = 0.3
    
    # b = distancia promedio a noticias del cluster MÁS CERCANO
    b = promedio_distancia_cluster_mas_cercano(noticia)
    # ej: b = 0.7
    
    # Silhouette = (b - a) / max(a, b)
    s = (b - a) / max(a, b)
    # = (0.7 - 0.3) / 0.7 = 0.4 / 0.7 = 0.571
    
    return s  # 0.571 (buen clustering)
```

---

## <a name="necesidad-pasos"></a>❓ ¿Es necesario cada paso?

### PASO 1: Recolección
**¿Es necesario?** ✅ **SÍ, ABSOLUTAMENTE**
- Sin datos NO hay sistema
- Alternativa: API de noticias (costosa)

### PASO 2: Detector
**¿Es necesario?** ✅ **SÍ**
- Filtra 80-90% de ruido
- Sin detector, pasos ML procesarían noticias irrelevantes
- Alternativa: Clasificador ML (más complejo, requiere datos etiquetados)

### PASO 3: Vectorización (TF-IDF)
**¿Es necesario?** ✅ **SÍ**
- Algoritmos ML solo entienden números
- TF-IDF es estándar en procesamiento de texto
- Alternativas:
  - **Word2Vec/BERT**: Más complejos, requieren modelos pre-entrenados
  - **Bag of Words**: Más simple pero ignora importancia de palabras

### PASO 4: Tópicos (LDA)
**¿Es necesario?** ⚠️ **OPCIONAL**
- **Ventajas**:
  - Ayuda a entender temáticas
  - Útil para dashboard (filtrar por tema)
  - Mejora interpretabilidad
- **Desventajas**:
  - No mejora detección directamente
  - Puede omitirse si solo importa feminicidios con NNA
- **Recomendación**: **MANTENER** para análisis exploratorio

### PASO 5: Clustering (DBSCAN)
**¿Es necesario?** ⚠️ **OPCIONAL**
- **Ventajas**:
  - Detecta duplicados
  - Agrupa casos relacionados
  - Útil si se procesan miles de noticias diarias
- **Desventajas**:
  - En datasets pequeños (<100) da muchos outliers (normal)
  - No mejora detección de feminicidios
- **Recomendación**: **MANTENER** si se escala a producción

### PASO 6: Similitud
**¿Es necesario?** ⚠️ **OPCIONAL**
- **Ventajas**:
  - Permite "noticias relacionadas" en dashboard
  - Detecta duplicados mejor que clustering
- **Desventajas**:
  - No afecta detección principal
- **Recomendación**: **MANTENER** para UX del dashboard

### Pipeline Mínimo Funcional

Si quieres **solo detectar feminicidios con NNA**:

```
Internet → RECOLECCIÓN → DETECTOR → ✅ LISTO
```

Si quieres **análisis ML + dashboard**:

```
Internet → RECOLECCIÓN → DETECTOR → VECTORIZACIÓN → SIMILITUD → Dashboard
```

---

## <a name="resultados-esperados"></a>📈 ¿Está dando resultados esperados?

### Métricas de Calidad

#### 1. Recolección
| Métrica | Valor Esperado | ¿Qué significa? |
|---------|----------------|-----------------|
| Total noticias | 50-150 | Suficiente para análisis |
| % Feminicidios | 20-40% | Buena precisión de fuentes |
| % Objetivo (con NNA) | 10-25% | Filtro efectivo |

#### 2. Detector
| Métrica | Valor Esperado | ¿Qué significa? |
|---------|----------------|-----------------|
| Precisión | >80% | Pocos falsos positivos |
| Recall | >70% | No pierde casos reales |
| F1-Score | >75% | Balance |

**¿Cómo medir precisión?**
```
Revisa manualmente 20 noticias clasificadas como "OBJETIVO"
Precisión = Correctas / 20
```

#### 3. Vectorización
| Métrica | Valor Esperado | ¿Qué significa? |
|---------|----------------|-----------------|
| Features | 500-1000 | Suficiente diversidad léxica |
| Top palabras incluyen | feminicidio, mujer, hijos | Captura conceptos clave |
| Densidad matriz | 5-15% | Normal en texto |

#### 4. Tópicos (LDA)
| Métrica | Valor Esperado | ¿Qué significa? |
|---------|----------------|-----------------|
| Perplexity | <150 | Modelo ajusta bien |
| Distribución | 10-30% por tópico | Balance |
| Interpretabilidad | Alta | Tópicos tienen sentido |

#### 5. Clustering
| Métrica | Valor Esperado | ¿Qué significa? |
|---------|----------------|-----------------|
| Silhouette | >0.3 | Buena separación |
| % Outliers | 30-85% | Normal en noticias |
| Clusters | 3-10 | Suficientes grupos |

#### 6. Similitud
| Métrica | Valor Esperado | ¿Qué significa? |
|---------|----------------|-----------------|
| Similitud promedio | 0.15-0.35 | Diversidad sana |
| Pares >0.7 | <20% | Pocos duplicados |

---

## <a name="recomendaciones"></a>💡 Recomendaciones de Ajuste

### Si tienes POCAS noticias (<50)

```python
# config.py
GOOGLE_NEWS_CONFIG = {
    'max_results': 50,  # Aumentar de 30 a 50
}

# Agregar más RSS feeds
RSS_FEEDS = [
    # ... feeds actuales
    'https://nuevofeed1.com/rss',
    'https://nuevofeed2.com/rss',
]
```

### Si el detector es muy ESTRICTO (<10% objetivo)

```python
# src/collection/feminicide_detector.py

def _classify_priority(self, confidence: float) -> str:
    if confidence >= 0.50:  # Reducir de 0.70 a 0.50
        return "ALTA"
    elif confidence >= 0.25:  # Reducir de 0.40 a 0.25
        return "MEDIA"
    else:
        return "BAJA"
```

### Si TF-IDF pierde palabras clave

```python
# config.py
TFIDF_CONFIG = {
    'max_features': 1500,  # Aumentar de 1000
    'max_df': 0.98,        # Aumentar de 0.95 (más permisivo)
}
```

### Si hay MUCHOS outliers en clustering (>90%)

```python
# config.py
DBSCAN_CONFIG = {
    'eps': 0.75,  # Aumentar de 0.6 (más permisivo)
    'min_samples': 2,
}
```

### Si LDA da tópicos sin sentido

```python
# config.py
LDA_CONFIG = {
    'n_components': 4,  # Reducir de 6 a 4 tópicos
    'max_iter': 30,     # Aumentar iteraciones
}
```

---

## 🎬 Conclusión

### ¿Cómo ejecutar el análisis completo?

```bash
# Desde PowerShell
python analisis_pipeline_detallado.py
```

Este script te mostrará:
1. ✅ Qué hace cada paso
2. ✅ Por qué es necesario
3. ✅ Qué parámetros usa
4. ✅ Qué palabras considera
5. ✅ Qué valores calcula
6. ✅ Si está dando resultados esperados
7. ✅ Recomendaciones de ajuste

### ¿Necesitas ayuda para decidir?

**Pregúntate**:
1. ¿El sistema detecta las noticias correctas? → Ajustar **Detector**
2. ¿Quiero entender de qué hablan las noticias? → Usar **LDA**
3. ¿Necesito agrupar casos relacionados? → Usar **DBSCAN**
4. ¿Solo quiero filtrar feminicidios con NNA? → **Recolección + Detector**

---

**📧 Contacto**: Héctor Morales - ESIME Zacatenco IPN  
**📅 Última actualización**: 18 de noviembre de 2025
