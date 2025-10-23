# 📚 EXPLICACIÓN TÉCNICA COMPLETA DEL SISTEMA NNA

## 🎯 Visión General del Pipeline

Tu sistema funciona como una cadena de **7 etapas** que transforman noticias crudas en conocimiento estructurado:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   SCRAPING  │───▶│  TF-IDF     │───▶│    LDA      │───▶│   DBSCAN    │
│   (RSS)     │    │  VECTORES   │    │  TÓPICOS    │    │  CLUSTERS   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      ▼                   ▼                   ▼                   ▼
  146 noticias      Matriz 146x3000      6 tópicos         5 clusters
   (texto crudo)    (números TF-IDF)   (temas latentes)   + 12 outliers
```

---

## 📖 ETAPA 1: WEB SCRAPING (Recolección de Noticias)

### 🔍 ¿Qué hace?
Extrae noticias de **8 fuentes RSS** de medios mexicanos y detecta menciones a NNA (niños, niñas, adolescentes).

### 📂 Archivo: `src/collection/data_collector.py`

### 🔧 Fragmentos de código clave:

#### 1.1 Recolección RSS (líneas ~30-60)
```python
def collect_news(self):
    """Recolecta noticias de múltiples feeds RSS"""
    for feed_url in self.feeds:
        feed = feedparser.parse(feed_url)  # ← Parsea el XML del RSS
        for entry in feed.entries:
            news_item = {
                'title': entry.title,
                'link': entry.link,
                'published': entry.published,
                'source': feed.feed.title,
                'summary': entry.summary  # ← Texto crudo para análisis
            }
            all_news.append(news_item)
```

**¿Cómo funciona?**
- `feedparser.parse()` convierte XML en diccionario Python
- Extrae: título, URL, fecha, fuente, resumen
- Almacena en lista `all_news`

#### 1.2 Detección de NNA (líneas ~70-90)
```python
def detect_nna_mentions(self, text):
    """Detecta si el texto menciona casos de NNA"""
    patterns = [
        r'\bniñ[oa]s?\b',           # niño, niña, niños, niñas
        r'\bmenor(?:es)?\b',         # menor, menores
        r'\badolescente[s]?\b',      # adolescente, adolescentes
        r'\binfant(?:e|es|il)\b',    # infante, infantil
        r'\bjoven(?:es)?\b',         # joven, jóvenes
        # ... más patrones
    ]
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True  # ← Si encuentra coincidencia, marca como NNA
    return False
```

**¿Cómo funciona?**
- Usa **expresiones regulares (regex)** para buscar palabras clave
- `\b` = límite de palabra (evita falsos positivos)
- `re.IGNORECASE` = no distingue mayúsculas/minúsculas
- Si encuentra cualquier patrón → `nna_related = True`

### 📊 Salida de Etapa 1:
- Archivo: `data/noticias.csv`
- Estructura: `title, link, published, source, summary, nna_related`
- Ejemplo: 146 noticias, 36 marcadas con `nna_related=True`

---

## 🔢 ETAPA 2: TF-IDF VECTORIZACIÓN (Representación Numérica)

### 🔍 ¿Qué hace?
Convierte **texto en números** usando TF-IDF (Term Frequency - Inverse Document Frequency).

### 📂 Archivo: `src/analysis/simplified_analyzer.py` (líneas 120-180)

### 🧮 Matemática de TF-IDF:

#### Fórmula:
```
TF-IDF(palabra, documento) = TF × IDF

TF (Term Frequency) = frecuencia de palabra en documento / total de palabras
IDF (Inverse Doc Freq) = log(total de documentos / documentos con esa palabra)
```

#### Ejemplo real:
Supongamos 3 noticias:
- Doc 1: "menor desaparecido en Jalisco"
- Doc 2: "menor encontrado en Monterrey"  
- Doc 3: "reunión presidencial en Jalisco"

Para la palabra **"menor"**:
```
TF en Doc1 = 1/4 = 0.25
IDF = log(3/2) = 0.176  (aparece en 2 de 3 docs)
TF-IDF(menor, Doc1) = 0.25 × 0.176 = 0.044
```

Para la palabra **"Jalisco"**:
```
TF en Doc1 = 1/4 = 0.25
IDF = log(3/2) = 0.176  (aparece en 2 de 3 docs)
TF-IDF(Jalisco, Doc1) = 0.25 × 0.176 = 0.044
```

Para la palabra **"desaparecido"**:
```
TF en Doc1 = 1/4 = 0.25
IDF = log(3/1) = 0.477  (aparece solo en 1 doc) ← MÁS DISTINTIVA
TF-IDF(desaparecido, Doc1) = 0.25 × 0.477 = 0.119  ← SCORE MÁS ALTO
```

**💡 Intuición:** Palabras raras y distintivas tienen scores más altos.

### 🔧 Fragmento de código (líneas 120-180):

```python
def step_3_vectorization(self):
    """Crea representación vectorial TF-IDF"""
    
    # Limpieza de texto
    self.df_processed['text_clean'] = self.df_processed['combined_text'].apply(
        lambda x: self._clean_text(x)  # ← Remueve puntuación, números
    )
    
    # Configuración del vectorizador
    self.tfidf_vectorizer = TfidfVectorizer(
        max_features=3000,        # ← Solo las 3000 palabras más importantes
        ngram_range=(1, 2),       # ← Unigrams (1 palabra) y bigrams (2 palabras)
        min_df=2,                 # ← Palabra debe aparecer en ≥2 documentos
        max_df=0.8,               # ← Ignora si aparece en >80% de docs (muy común)
        strip_accents='unicode',  # ← Normaliza acentos
        lowercase=True,           # ← Todo a minúsculas
        stop_words=None           # ← No usa stopwords predefinidas
    )
    
    # TRANSFORMACIÓN: Texto → Matriz numérica
    self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(
        self.df_processed['text_clean']
    )
    # ↑ Resultado: matriz dispersa (sparse matrix) 146x3000
    #    Cada fila = 1 noticia
    #    Cada columna = 1 palabra
    #    Valores = scores TF-IDF (0.0 a 1.0)
```

### 🔑 Parámetros importantes:

- **`max_features=3000`**: Limita vocabulario a las 3000 palabras más frecuentes (evita explosión dimensional)
- **`ngram_range=(1,2)`**: 
  - Unigrams: "niño", "desaparecido", "Jalisco"
  - Bigrams: "niño desaparecido", "menor edad", "alerta amber"
- **`min_df=2`**: Elimina palabras que solo aparecen 1 vez (probablemente ruido)
- **`max_df=0.8`**: Elimina palabras muy comunes como "el", "de", "en" (no discriminan)

### 📊 Salida de Etapa 2:
- **Objeto:** `self.tfidf_matrix` (scipy sparse matrix)
- **Dimensiones:** 146 filas × 3000 columnas
- **Tipo de datos:** float64 (valores entre 0.0 y ~1.0)
- **Formato:** Compressed Sparse Row (CSR) - solo guarda valores no-cero
- **Vocabulario:** `self.tfidf_vectorizer.vocabulary_` (diccionario palabra→índice)

**Ejemplo de una fila (noticia vectorizada):**
```
[0.0, 0.0, 0.234, 0.0, 0.567, 0.0, ..., 0.123, 0.0]
  ↑    ↑     ↑     ↑     ↑     ↑         ↑     ↑
 palabra palabra palabra ...            palabra palabra
   0      1      2                       2998   2999
```

---

## 🏷️ ETAPA 3: LDA TOPIC MODELING (Modelado de Tópicos)

### 🔍 ¿Qué hace?
Descubre **temas latentes** (tópicos) en las noticias usando LDA (Latent Dirichlet Allocation).

### 📂 Archivo: `src/analysis/simplified_analyzer.py` (líneas 182-220)

### 🧠 Intuición de LDA:

LDA asume que:
1. Cada documento es una **mezcla de tópicos**
2. Cada tópico es una **distribución de palabras**

**Ejemplo:**
```
Tópico 1 (Violencia):     feminicidio(30%), menor(20%), desaparecido(15%), ...
Tópico 2 (Justicia):      juicio(25%), joven(20%), penal(18%), ...
Tópico 3 (Política):      gobierno(30%), presidente(25%), estrategia(15%), ...
```

Una noticia puede ser:
- 60% Tópico 1 (Violencia)
- 30% Tópico 2 (Justicia)
- 10% Tópico 3 (Política)

### 🔧 Fragmento de código (líneas 182-220):

```python
def step_4_topic_modeling(self, n_topics=6):
    """Entrena modelo LDA para descubrir tópicos"""
    
    # Configuración de LDA
    self.lda_model = LatentDirichletAllocation(
        n_components=n_topics,     # ← Número de tópicos a descubrir
        max_iter=20,               # ← Iteraciones de optimización
        learning_method='online',  # ← Aprendizaje incremental (más rápido)
        random_state=42,           # ← Reproducibilidad
        n_jobs=-1                  # ← Usa todos los CPUs
    )
    
    # ENTRENAMIENTO: Aprende distribuciones de palabras por tópico
    self.topic_distribution = self.lda_model.fit_transform(self.tfidf_matrix)
    # ↑ Resultado: matriz 146x6
    #    Cada fila = 1 noticia
    #    Cada columna = 1 tópico
    #    Valores = probabilidad de que noticia pertenezca a ese tópico
    
    # Extraer palabras clave por tópico
    feature_names = self.tfidf_vectorizer.get_feature_names_out()
    for topic_idx, topic in enumerate(self.lda_model.components_):
        top_words_idx = topic.argsort()[-10:][::-1]  # ← Top 10 palabras
        top_words = [feature_names[i] for i in top_words_idx]
        print(f"  Tópico {topic_idx}: {' '.join(top_words[:7])}")
```

### 🎲 Proceso matemático de LDA:

1. **Inicialización aleatoria:** Asigna palabras a tópicos aleatoriamente
2. **Iteración Gibbs Sampling:**
   - Para cada palabra en cada documento:
     - ¿Qué tan probable es que esta palabra pertenezca a cada tópico?
     - ¿Qué tan probable es que este documento hable de cada tópico?
     - Reasigna palabra al tópico más probable
3. **Convergencia:** Después de 20 iteraciones, las asignaciones se estabilizan

### 📊 Salida de Etapa 3:
- **Objeto:** `self.topic_distribution` (numpy array 146x6)
- **Tópicos descubiertos:** 6 temas latentes
- **Ejemplo de salida:**
  ```
  Tópico 0: dong dong zhang zhi dong zhi zhang
  Tópico 1: villalpando penal juicio de jalisco joven
  Tópico 2: un pai puntos escuderi hacia la guardia
  Tópico 3: por no una es al
  Tópico 4: produccio la estrategia en otro reality
  Tópico 5: portafolio fibra mty fibra mty venta
  ```

---

## 🎯 ETAPA 4: DBSCAN CLUSTERING (Agrupación de Noticias)

### 🔍 ¿Qué hace?
Agrupa noticias **similares** usando DBSCAN y detecta **outliers** (casos únicos).

### 📂 Archivo: `src/analysis/simplified_analyzer.py` (líneas 226-330)

### 🧩 Algoritmo DBSCAN:

DBSCAN = **D**ensity-**B**ased **S**patial **C**lustering of **A**pplications with **N**oise

**Principio:** Agrupar puntos **densos** (muchos vecinos cercanos) y marcar puntos aislados como **outliers**.

#### Parámetros:
- **`eps=0.4`**: Radio de vecindad (40% de similitud)
- **`min_samples=3`**: Mínimo de vecinos para formar cluster

#### Proceso:

```
1. Calcular distancia entre todos los pares de noticias
   Distancia = 1 - similitud_coseno
   
2. Para cada noticia:
   - Si tiene ≥3 vecinos dentro de radio 0.4 → Forma cluster (Core Point)
   - Si está cerca de un cluster pero tiene <3 vecinos → Se une al cluster (Border Point)
   - Si está lejos de todos → Outlier (Noise Point)
```

### 🔧 Fragmento de código (líneas 226-330):

```python
def _clustering_dbscan(self, eps=0.4, min_samples=3):
    """Aplica DBSCAN para clustering adaptativo"""
    
    # Normalizar vectores (importante para similitud coseno)
    tfidf_normalized = normalize(self.tfidf_matrix, norm='l2')
    # ↑ Cada vector tiene longitud 1 (norma euclidiana)
    
    # Configuración de DBSCAN
    self.dbscan_model = DBSCAN(
        eps=eps,                    # ← Radio de vecindad (0.4 = 60% similitud)
        min_samples=min_samples,    # ← Mínimo de vecinos
        metric='cosine',            # ← Usa distancia coseno
        n_jobs=-1                   # ← Paraleliza cálculo
    )
    
    # CLUSTERING: Asigna etiquetas de cluster
    labels = self.dbscan_model.fit_predict(tfidf_normalized)
    # ↑ Resultado: array de 146 enteros
    #    -1 = outlier
    #    0, 1, 2, ... = ID de cluster
    
    self.df_processed['cluster_dbscan'] = labels
    
    # Calcular métricas de calidad
    non_outliers = labels != -1
    if non_outliers.sum() > 1:
        silhouette = silhouette_score(
            tfidf_normalized[non_outliers],
            labels[non_outliers],
            metric='cosine'
        )
        # ↑ Silhouette score: -1 (malo) a 1 (perfecto)
        #   Mide qué tan compactos y separados están los clusters
```

### 📏 Similitud Coseno (métrica de distancia):

#### Fórmula:
```
similitud_coseno(A, B) = (A · B) / (||A|| × ||B||)

Donde:
- A · B = producto punto (suma de productos elemento a elemento)
- ||A|| = norma (longitud del vector)
```

#### Ejemplo visual:
```
Noticia A = [0.5, 0.3, 0.0, 0.8, ...]  (vector TF-IDF)
Noticia B = [0.6, 0.2, 0.1, 0.7, ...]

A · B = (0.5×0.6) + (0.3×0.2) + (0.0×0.1) + (0.8×0.7) + ...
      = 0.30 + 0.06 + 0.00 + 0.56 + ...
      = 0.92

||A|| = √(0.5² + 0.3² + 0.0² + 0.8² + ...) = 1.0 (normalizado)
||B|| = √(0.6² + 0.2² + 0.1² + 0.7² + ...) = 1.0 (normalizado)

similitud_coseno = 0.92 / (1.0 × 1.0) = 0.92  ← MUY SIMILARES

distancia_coseno = 1 - 0.92 = 0.08 < 0.4 (eps)  ← SON VECINOS!
```

**💡 Intuición:** 
- Similitud 1.0 = idénticos (distancia 0.0)
- Similitud 0.6 = algo similares (distancia 0.4) ← umbral `eps`
- Similitud 0.0 = ortogonales (distancia 1.0)

### 📊 Salida de Etapa 4:
- **Columna:** `cluster_dbscan` en DataFrame
- **Valores:** -1 (outlier) o 0,1,2,3,4 (IDs de cluster)
- **Resultados típicos:**
  - 5 clusters (grupos de noticias similares)
  - 12 outliers (casos únicos o raros)
- **Archivo:** `data/clusters_info.csv` (análisis detallado por cluster)

---

## 📐 ETAPA 5: ANÁLISIS DE SIMILITUD (Matriz de Similitud)

### 🔍 ¿Qué hace?
Calcula similitud coseno entre **todos los pares** de noticias para encontrar relaciones.

### 📂 Archivo: `src/analysis/simplified_analyzer.py` (líneas 332-370)

### 🔧 Fragmento de código:

```python
def step_6_similarity_analysis(self):
    """Calcula similitud coseno entre documentos"""
    
    # Calcular matriz de similitud (146x146)
    similarity_matrix = cosine_similarity(self.tfidf_matrix)
    # ↑ similarity_matrix[i][j] = similitud entre noticia i y noticia j
    
    # Encontrar pares con alta similitud
    n_docs = len(self.df_processed)
    similar_pairs = []
    
    for i in range(n_docs):
        for j in range(i+1, n_docs):  # ← Solo mitad superior (matriz simétrica)
            sim_score = similarity_matrix[i, j]
            if sim_score > 0.5:  # ← Umbral de similitud
                similar_pairs.append({
                    'doc1': i,
                    'doc2': j,
                    'similarity': sim_score,
                    'title1': self.df_processed.iloc[i]['title'],
                    'title2': self.df_processed.iloc[j]['title']
                })
    
    # Guardar en DataFrame
    self.df_processed['top_similar_docs'] = None
    for i in range(n_docs):
        # Top 5 noticias más similares a esta
        similarities = similarity_matrix[i]
        similarities[i] = 0  # ← Excluir consigo misma
        top_indices = similarities.argsort()[-5:][::-1]
        top_scores = similarities[top_indices]
        
        similar_info = [
            f"{self.df_processed.iloc[idx]['title'][:50]}... ({score:.2f})"
            for idx, score in zip(top_indices, top_scores)
        ]
        self.df_processed.at[i, 'top_similar_docs'] = '; '.join(similar_info)
```

### 📊 Salida de Etapa 5:
- **Matriz:** 146×146 de similitudes (21,316 pares)
- **Similitud promedio:** 0.324 (32.4%)
- **Pares con alta similitud (>0.5):** 22 pares
- **Columna:** `top_similar_docs` (5 noticias más similares a cada una)

---

## 🔍 ETAPA 6: BÚSQUEDA MEJORADA (Diccionario de Sinónimos)

### 🔍 ¿Qué hace?
Crea un diccionario de **sinónimos** para mejorar búsquedas (expande términos relacionados).

### 📂 Archivo: `src/analysis/synonym_dictionary.py`

### 🔧 Fragmento de código:

```python
SYNONYM_DICTIONARY = {
    'feminicidio': [
        'feminicidio', 'femicidio', 'asesinato de mujer',
        'homicidio de mujer', 'crimen de género', 
        'violencia feminicida', 'muerte violenta de mujer'
    ],
    'menor': [
        'menor', 'menor de edad', 'niño', 'niña', 
        'adolescente', 'infante', 'joven'
    ],
    'desaparecido': [
        'desaparecido', 'desaparición', 'no localizado',
        'extraviado', 'perdido', 'ausente'
    ],
    # ... 143 términos totales
}

def expand_search_term(term):
    """Expande un término de búsqueda con sus sinónimos"""
    term_lower = term.lower()
    for key, synonyms in SYNONYM_DICTIONARY.items():
        if term_lower in synonyms:
            return synonyms  # ← Retorna lista completa de sinónimos
    return [term]  # ← Si no tiene sinónimos, retorna solo el término
```

### 📊 Salida de Etapa 6:
- **Archivo:** `data/synonym_dictionary.json`
- **Total términos:** 143 palabras clave
- **Uso:** Interfaz web para búsqueda expandida

---

## 💾 ETAPA 7: GUARDADO DE RESULTADOS

### 📂 Archivos generados:

1. **`data/noticias_analyzed_simplified.csv`**
   - Todas las noticias con vectores, clusters, tópicos, similitudes
   - Columnas: title, link, published, source, summary, nna_related, 
     text_clean, cluster_dbscan, topic_distribution, top_similar_docs

2. **`data/noticias_analyzed_simplified_metadata.json`**
   - Metadatos del análisis: fecha, parámetros, métricas
   - Ejemplo:
     ```json
     {
       "version": "2.0",
       "analysis_date": "2025-10-23T17:07:48",
       "clustering_method": "dbscan",
       "parameters": {
         "eps": 0.4,
         "min_samples": 3,
         "n_topics": 6
       },
       "metrics": {
         "total_news": 146,
         "nna_cases": 36,
         "n_clusters": 5,
         "n_outliers": 12,
         "silhouette_score": 0.51
       }
     }
     ```

3. **`data/clusters_info.csv`**
   - Análisis detallado por cluster
   - Columnas: cluster_id, size, nna_count, keywords, sample_titles

---

## 🧪 RESUMEN DE TRANSFORMACIONES DE DATOS

```
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 1: WEB SCRAPING                                           │
├─────────────────────────────────────────────────────────────────┤
│ INPUT:  8 feeds RSS (XML)                                       │
│ OUTPUT: 146 noticias (texto crudo)                              │
│ FORMATO: DataFrame con columnas [title, summary, nna_related]   │
└─────────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 2: TF-IDF VECTORIZACIÓN                                   │
├─────────────────────────────────────────────────────────────────┤
│ INPUT:  146 textos (strings)                                    │
│ PROCESO: Limpieza → Tokenización → TF-IDF                       │
│ OUTPUT: Matriz 146×3000 (sparse matrix)                         │
│ FORMATO: CSR matrix con valores float64 [0.0, 1.0]              │
└─────────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 3: LDA TOPIC MODELING                                     │
├─────────────────────────────────────────────────────────────────┤
│ INPUT:  Matriz TF-IDF 146×3000                                  │
│ PROCESO: Latent Dirichlet Allocation (20 iteraciones)           │
│ OUTPUT: Matriz 146×6 (distribución de tópicos)                  │
│ FORMATO: Numpy array con probabilidades [0.0, 1.0]              │
└─────────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 4: DBSCAN CLUSTERING                                      │
├─────────────────────────────────────────────────────────────────┤
│ INPUT:  Matriz TF-IDF normalizada 146×3000                      │
│ PROCESO: DBSCAN con distancia coseno (eps=0.4)                  │
│ OUTPUT: Array de 146 etiquetas [-1, 0, 1, 2, 3, 4]              │
│ FORMATO: Numpy array int64 (-1 = outlier)                       │
└─────────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 5: SIMILITUD COSENO                                       │
├─────────────────────────────────────────────────────────────────┤
│ INPUT:  Matriz TF-IDF 146×3000                                  │
│ PROCESO: Producto matricial A × A^T                             │
│ OUTPUT: Matriz 146×146 de similitudes                           │
│ FORMATO: Numpy array float64 [0.0, 1.0] (simétrica)             │
└─────────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 6: DICCIONARIO DE SINÓNIMOS                               │
├─────────────────────────────────────────────────────────────────┤
│ INPUT:  Términos clave del dominio NNA                          │
│ OUTPUT: JSON con 143 términos y sus sinónimos                   │
│ FORMATO: Dict[str, List[str]]                                   │
└─────────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 7: GUARDADO DE RESULTADOS                                 │
├─────────────────────────────────────────────────────────────────┤
│ OUTPUT: 3 archivos CSV/JSON con análisis completo               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 MÉTRICAS DE CALIDAD DEL SISTEMA

### Silhouette Score (Clustering)
- **Fórmula:** `s = (b - a) / max(a, b)`
  - `a` = distancia promedio a puntos del mismo cluster
  - `b` = distancia promedio al cluster más cercano
- **Rango:** -1 (malo) a 1 (perfecto)
- **Tu resultado:** 0.51 ✅ (Bueno - clusters compactos y separados)

### Perplexity (LDA)
- **Definición:** Mide qué tan bien el modelo predice nuevos documentos
- **Fórmula:** `perplexity = exp(-log likelihood / n_words)`
- **Rango:** Menor es mejor (pero depende del corpus)
- **Tu resultado:** 47,903.98 (normal para 146 documentos con 3000 palabras)

### Cobertura NNA
- **Total noticias:** 146
- **Casos NNA:** 36 (24.7%)
- **Clusters con NNA:** Variable según la corrida

---

## 🎯 FLUJO DE EJECUCIÓN COMPLETO

### Archivo principal: `src/analysis/simplified_analyzer.py`

```python
def run_complete_analysis(self, clustering_method='dbscan'):
    """Ejecuta pipeline completo de 7 etapas"""
    
    print("🚀 INICIANDO ANÁLISIS COMPLETO")
    
    # ETAPA 1: Scraping
    self.step_1_data_collection()        # → data/noticias_raw.csv
    
    # ETAPA 2: Almacenamiento
    self.step_2_initial_storage()        # → Carga CSV a DataFrame
    
    # ETAPA 3: Vectorización
    self.step_3_vectorization()          # → Matriz TF-IDF 146x3000
    
    # ETAPA 4: Modelado de tópicos
    self.step_4_topic_modeling(n_topics=6)  # → 6 tópicos latentes
    
    # ETAPA 5: Clustering
    self.step_5_clustering(
        method=clustering_method,        # → 'dbscan' o 'kmeans'
        eps=0.4,                         # → Para DBSCAN
        min_samples=3                    # → Para DBSCAN
    )
    
    # ETAPA 6: Similitud
    self.step_6_similarity_analysis()    # → Matriz 146x146
    
    # ETAPA 7: Sinónimos
    self.step_7_enhanced_search()        # → Diccionario JSON
    
    # Guardar resultados
    self._save_results()
    
    print("🎉 ANÁLISIS COMPLETADO")
    return self.df_processed
```

---

## 🔑 VENTAJAS DE DBSCAN vs K-MEANS

| Aspecto | K-Means | DBSCAN |
|---------|---------|--------|
| **Número de clusters** | Manual (k=4) | Automático (detecta óptimo) |
| **Forma de clusters** | Esférica | Arbitraria |
| **Outliers** | No detecta | Identifica casos únicos (-1) |
| **Sensibilidad** | Centroides afectados por outliers | Robusto a ruido |
| **Silhouette Score** | 0.42 | 0.51 (+21%) ✅ |

---

## 🚀 PRÓXIMOS PASOS DE MEJORA

1. **✅ COMPLETADO:** Implementación de DBSCAN
2. **⏳ PENDIENTE:** Scripts de visualización de matrices TF-IDF
3. **🔮 FUTURO:** Fine-tuning de parámetros DBSCAN
4. **🔮 FUTURO:** Integración con modelos de lenguaje (BERT, RoBERTa)
5. **🔮 FUTURO:** Dashboard interactivo con visualizaciones 3D

---

**Fecha de documento:** 23 de octubre de 2025  
**Versión del sistema:** 2.0 (con DBSCAN)  
**Autor:** Sistema NNA - Héctor Morales
