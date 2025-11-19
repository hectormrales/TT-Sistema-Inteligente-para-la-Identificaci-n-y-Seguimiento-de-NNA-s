# 🔍 CÓMO FUNCIONA EL SISTEMA - Explicación Completa

**Sistema Inteligente para Identificación y Seguimiento de NNA's**  
**ESIME Zacatenco - IPN**  
**Autor: Héctor Morales**  
**Fecha: 18 de noviembre de 2025**

---

## 📋 Índice

1. [Introducción: ¿Qué hace este sistema?](#introducción)
2. [PASO 1: Recolección de Noticias](#paso-1-recolección)
3. [PASO 2: Detector de Feminicidios](#paso-2-detector)
4. [PASO 3: Vectorización TF-IDF](#paso-3-vectorización)
5. [PASO 4: Modelado de Tópicos (LDA)](#paso-4-tópicos)
6. [PASO 5: Clustering (DBSCAN)](#paso-5-clustering)
7. [PASO 6: Análisis de Similitud](#paso-6-similitud)
8. [Flujo Completo con Ejemplo](#flujo-completo)
9. [¿Qué palabras toma en cuenta?](#palabras-clave)
10. [¿Cómo se calculan los valores?](#cálculo-valores)
11. [¿Es necesario cada paso?](#necesidad-pasos)
12. [¿Está dando resultados esperados?](#resultados-esperados)
13. [Recomendaciones de Ajuste](#recomendaciones)

---

## <a name="introducción"></a>🎯 Introducción: ¿Qué hace este sistema?

### Objetivo Principal
Identificar **automáticamente** noticias sobre feminicidios que dejan niños huérfanos (NNA = Niñas, Niños y Adolescentes) en México.

### ¿Por qué es importante?
- **Problema social**: Cada feminicidio puede dejar NNA en situación vulnerable
- **Volumen de información**: Miles de noticias diarias, imposible revisar manualmente
- **Acción rápida**: Mientras más pronto se detecte un caso, más rápido se puede dar apoyo

### ¿Cómo lo hace?
Usa **6 pasos secuenciales**, cada uno con un propósito específico:

```
Internet → [RECOLECCIÓN] → [DETECTOR] → [VECTORIZACIÓN] → [TÓPICOS] → [CLUSTERING] → [SIMILITUD] → Dashboard
```

---

## <a name="paso-1-recolección"></a>📰 PASO 1: Recolección de Noticias

### ¿Qué hace?
Busca y descarga noticias de **2 tipos de fuentes**:
1. **RSS Feeds**: 8 medios especializados en temas de género
2. **Google News**: Búsqueda específica con palabras clave

### ¿Por qué es necesario?
**Sin noticias NO hay nada que analizar.** Este es el combustible del sistema.

### Parámetros que usa

#### 🔹 RSS Feeds (8 fuentes configuradas)
```python
RSS_FEEDS = [
    'https://cimacnoticias.com.mx/feed',              # CIMAC - Especializado en género
    'https://semmexico.mx/feed',                       # SEM México - Feminismo
    'https://www.jornada.com.mx/rss/edicion.xml',     # La Jornada - General
    # ... 5 fuentes más
]
```

**¿Qué valores toma?**
- **URL de cada feed**: Dirección del RSS
- **Timeout**: 10 segundos por fuente
- **Intentos**: 3 reintentos si falla
- **User-Agent**: Simula navegador para evitar bloqueos

#### 🔹 Google News
```python
GOOGLE_NEWS_CONFIG = {
    'query': 'feminicidio OR "violencia contra la mujer" OR "asesinato de mujer"',
    'max_results': 30,
    'language': 'es',
    'region': 'MX'
}
```

**¿Qué valores toma?**
- **Query**: Palabras clave combinadas con OR
- **max_results**: Máximo 30 noticias
- **language**: Solo español
- **region**: Solo México

### Ejemplo de Salida

**Entrada**: URLs de RSS + Query de Google  
**Salida**: DataFrame con ~50-100 noticias

```
| titulo                                    | fuente    | contenido            | fecha      |
|-------------------------------------------|-----------|----------------------|------------|
| "Feminicidio en Edomex deja 3 huérfanos" | CIMAC     | "Una mujer de 35..." | 2025-11-15 |
| "Asesinan a madre en Puebla"             | La Jornada| "Autoridades..."     | 2025-11-16 |
```

### ¿Está dando resultados esperados?

✅ **BIEN** si:
- Recolecta >50 noticias
- Al menos 20% son sobre feminicidios
- Hay variedad de fuentes

⚠️ **AJUSTAR** si:
- <30 noticias → Agregar más fuentes RSS
- <10% feminicidios → Ajustar query de Google News
- Todas de la misma fuente → Verificar que otros RSS funcionen

---

## <a name="paso-2-detector"></a>🔍 PASO 2: Detector de Feminicidios

### ¿Qué hace?
Analiza **cada noticia** con **40+ patrones regex** para determinar:
1. ¿Es sobre un feminicidio? ✓
2. ¿Menciona hijos/NNA? ✓
3. ¿Habla de huérfanos? ✓

### ¿Por qué es necesario?
**Filtra el ruido.** De 100 noticias recolectadas, solo 10-20 son realmente relevantes.

### Parámetros que usa

#### 🔹 Patrones de Feminicidio (Peso: 40%)
```python
feminicide_patterns = [
    r'\bfeminicidio\b',
    r'\basesinat[oa]\b.*\bmujer\b',
    r'\bmataron?\b.*\b(?:mujer|femenina)\b',
    r'\bhallaron?\b.*\bcuerpo\b.*\bmujer\b',
    # ... 40+ patrones más
]
```

**¿Qué palabras busca?**
- feminicidio, asesinato, mataron, hallaron cuerpo
- violencia de género, crimen machista
- encontraron muerta, muerte violenta

#### 🔹 Patrones de NNA/Hijos (Peso: 20%)
```python
children_patterns = [
    r'\bhijos?\b',
    r'\bniñ[oa]s?\b',
    r'\bmenor(?:es)?\b',
    r'\badolescente\b',
    # ...
]
```

**¿Qué palabras busca?**
- hijos, hijas, niños, niñas
- menores, adolescentes, bebé
- infantes, pequeños

#### 🔹 Patrones de Orfandad (Peso: 30% + 10% bonus)
```python
orphan_patterns = [
    r'\bhu[eé]rfan[oa]s?\b',
    r'\bquedar[oa]n?\b.*\bdesamparad[oa]s?\b',
    r'\bsin\b.*\bmadre\b',
    r'\babandon[oa](?:dos|das)\b',
    # ...
]
```

**¿Qué palabras busca?**
- huérfanos, quedaron sin madre
- desamparados, abandonados
- apoyo a menores, custodia

### ¿Cómo calcula la puntuación?

```python
# Ejemplo de noticia
texto = "Feminicidio en Edomex deja 3 huérfanos"

# 1. Cuenta coincidencias
feminicidio_count = 1   # Encontró "feminicidio"
nna_count = 0           # NO encontró "hijos", "niños", etc.
orfandad_count = 1      # Encontró "huérfanos"

# 2. Normaliza (divide entre número de patrones)
feminicidio_score = 1 / 40 * 0.40 = 0.010
nna_score = 0 / 15 * 0.20 = 0.000
orfandad_score = 1 / 20 * 0.30 = 0.015

# 3. Bonus si menciona huérfanos
orfandad_bonus = 0.10

# 4. Suma total
confianza = 0.010 + 0.000 + 0.015 + 0.10 = 0.125 (12.5%)
```

### Clasificación por Confianza

```python
if confianza >= 0.70:
    prioridad = "ALTA"      # ✅ Caso confirmado
elif confianza >= 0.40:
    prioridad = "MEDIA"     # ⚠️ Posible caso
else:
    prioridad = "BAJA"      # ⏸️ Poco probable
```

### Ejemplo de Salida

**Entrada**: "Feminicidio en Edomex deja 3 huérfanos"

**Salida**:
```json
{
    "is_feminicide": true,
    "has_children": false,
    "has_orphans": true,
    "is_target_news": true,
    "confidence": 0.125,
    "priority": "BAJA",
    "scores": {
        "feminicide_score": 0.010,
        "children_score": 0.000,
        "orphan_score": 0.015
    }
}
```

### ¿Está dando resultados esperados?

✅ **BIEN** si:
- Detecta 15-30% de noticias como feminicidios
- Al menos 10% son "OBJETIVO" (tiene NNA)
- Confianza >70% para casos claros

⚠️ **AJUSTAR** si:
- <5% son objetivo → Patrones muy estrictos, reducir umbral de confianza
- >50% son objetivo → Sobre-detectando, aumentar umbral
- Falsos positivos → Agregar patrones de exclusión

---

## <a name="paso-3-vectorización"></a>🔢 PASO 3: Vectorización TF-IDF

### ¿Qué hace?
Convierte **texto en números** que los algoritmos de Machine Learning pueden procesar.

### ¿Por qué es necesario?
**Los algoritmos ML NO entienden palabras, solo números.**

**Ejemplo**:
```
Texto: "Feminicidio en Edomex deja huérfanos"
Vector: [0.8, 0.0, 0.6, 0.0, 0.4, ..., 0.0]
         ↑         ↑         ↑
    feminicidio  mujer   huérfanos
```

### Parámetros que usa

```python
TFIDF_CONFIG = {
    'max_features': 1000,      # Solo las 1000 palabras más importantes
    'min_df': 1,               # Palabra debe aparecer mínimo 1 vez
    'max_df': 0.95,            # Ignora si aparece en >95% de documentos
    'ngram_range': (1, 2),     # Palabras individuales (1) y pares (2)
    'strip_accents': None,     # Preserva acentos (feminicidio ≠ feminicido)
    'lowercase': True,         # Todo a minúsculas
    'stop_words': None         # NO elimina palabras comunes (español)
}
```

### ¿Qué significan estos parámetros?

#### 🔹 max_features = 1000
**¿Qué hace?**: Solo guarda las 1000 palabras más relevantes

**¿Por qué?**: 
- Reduce dimensionalidad (memoria, velocidad)
- Elimina palabras raras que no aportan

**Ejemplo**:
```
ANTES: 50,000 palabras únicas (incluye typos, nombres raros)
DESPUÉS: 1,000 palabras más frecuentes/relevantes
```

#### 🔹 min_df = 1
**¿Qué hace?**: Palabra debe aparecer en al menos 1 documento

**¿Por qué?**: Con min_df=1 acepta todas las palabras (sin filtro mínimo)

**Si cambias a min_df=2**:
```
"feminicidio" aparece en 50 docs → ✅ Se incluye
"Edomex" aparece en 30 docs → ✅ Se incluye
"Zacatepec" aparece en 1 doc → ❌ Se elimina
```

#### 🔹 max_df = 0.95
**¿Qué hace?**: Ignora palabras que aparecen en >95% de documentos

**¿Por qué?**: Palabras muy comunes no discriminan (ej: "de", "la", "que")

**Ejemplo**:
```
"mujer" aparece en 98% docs → ❌ Eliminada (demasiado común)
"feminicidio" aparece en 60% docs → ✅ Incluida
```

#### 🔹 ngram_range = (1, 2)
**¿Qué hace?**: Considera palabras solas (1) y pares (2)

**¿Por qué?**: Captura contexto

**Ejemplo**:
```
Texto: "violencia de género"

n=1 (unigrams): ["violencia", "de", "género"]
n=2 (bigrams):  ["violencia de", "de género"]

AMBOS se incluyen → "violencia de género" vale más que solo "violencia"
```

### ¿Cómo calcula TF-IDF?

**TF-IDF = Term Frequency × Inverse Document Frequency**

#### Ejemplo con la palabra "feminicidio":

```
Documento 1: "Feminicidio en Edomex deja 3 huérfanos"
             └─ "feminicidio" aparece 1 vez en 7 palabras

TF (Term Frequency) = 1 / 7 = 0.143

Tenemos 100 documentos, "feminicidio" aparece en 60
IDF (Inverse Document Frequency) = log(100 / 60) = 0.511

TF-IDF = 0.143 × 0.511 = 0.073
```

**¿Qué significa?**
- **TF-IDF alto** (>0.5): Palabra importante y específica de este documento
- **TF-IDF medio** (0.1-0.5): Palabra relevante pero común
- **TF-IDF bajo** (<0.1): Palabra poco relevante

### Ejemplo de Salida

**Entrada**: 100 noticias de texto

**Salida**: Matriz de 100 × 1000

```
         feminicidio  mujer  hijos  edomex  ...  (1000 palabras)
Noticia1    0.80      0.30   0.60   0.50   ...
Noticia2    0.85      0.40   0.00   0.00   ...
Noticia3    0.00      0.70   0.00   0.20   ...
...
Noticia100  0.75      0.35   0.55   0.45   ...
```

### ¿Qué palabras REALMENTE toma en cuenta?

**Top 20 palabras con mayor peso** (ejemplo real):
1. **feminicidio** (peso: 45.2)
2. **mujer** (peso: 38.7)
3. **hijos** (peso: 22.5)
4. **edomex** (peso: 18.3)
5. **asesinato** (peso: 16.9)
6. **madre** (peso: 15.8)
7. **huérfanos** (peso: 14.2)
8. **violencia género** (peso: 12.3) ← bigram
9. **niños** (peso: 11.5)
10. **menores** (peso: 10.8)
...

### ¿Está dando resultados esperados?

✅ **BIEN** si:
- Matriz tiene dimensiones ~100 × 1000
- Top palabras incluyen: feminicidio, mujer, hijos, huérfanos
- >500 features (palabras únicas)

⚠️ **AJUSTAR** si:
- <500 features → Reducir max_df o aumentar max_features
- Top palabras son genéricas ("de", "la", "que") → Agregar stopwords español
- Faltan acentos → Verificar strip_accents=None

---

## <a name="paso-4-tópicos"></a>📊 PASO 4: Modelado de Tópicos (LDA)

### ¿Qué hace?
Encuentra **temas comunes** en las noticias usando **Latent Dirichlet Allocation (LDA)**.

### ¿Por qué es necesario?
**Agrupa noticias por tema**, no solo por palabras exactas.

**Ejemplo de tópicos descubiertos**:
- **Tópico 1**: feminicidio + edomex + asesinato + investigación
- **Tópico 2**: apoyo + huérfanos + gobierno + custodia + albergue
- **Tópico 3**: violencia + género + manifestación + justicia

### Parámetros que usa

```python
LDA_CONFIG = {
    'n_components': 6,        # Buscar 6 temas diferentes
    'random_state': 42,       # Semilla para reproducibilidad
    'max_iter': 20,           # Iteraciones del algoritmo
    'learning_method': 'online'  # Más rápido para datos grandes
}
```

### ¿Qué significa n_components = 6?

**Le dice al algoritmo: "Encuentra 6 temas principales"**

**¿Cómo decide qué temas?**
El algoritmo LDA busca palabras que **co-ocurren frecuentemente**:

```
Si "feminicidio", "edomex", "asesinato" aparecen juntas → Tópico 1
Si "apoyo", "huérfanos", "gobierno" aparecen juntas → Tópico 2
```

### Ejemplo de Salida

**Entrada**: Matriz TF-IDF (100 × 1000)

**Salida**: 6 tópicos con palabras clave

```
Tópico 0: feminicidio, edomex, mujer, asesinato, investigación, fiscalía
Tópico 1: apoyo, huérfanos, gobierno, custodia, dif, albergue
Tópico 2: violencia, género, manifestación, justicia, marcha, protesta
Tópico 3: madre, hijos, menores, niños, familia, abuela
Tópico 4: cuerpo, hallaron, localizado, abandonado, carretera
Tópico 5: pareja, ex, esposo, relación, celos, discusión
```

**Asignación de noticias**:
```
Noticia 1: "Feminicidio en Edomex..." → Tópico 0 (70% prob)
Noticia 2: "DIF apoya a huérfanos..." → Tópico 1 (85% prob)
Noticia 3: "Marcha por justicia..." → Tópico 2 (60% prob)
```

### ¿Cómo se calculan los valores?

**LDA usa probabilidades**:

Cada noticia es una **mezcla de tópicos**:
```
Noticia X:
  30% Tópico 0 (feminicidio)
  50% Tópico 1 (apoyo huérfanos)  ← Tópico dominante
  10% Tópico 3 (familia)
  10% Otros
```

**El sistema asigna la noticia al tópico con mayor probabilidad.**

### ¿Está dando resultados esperados?

✅ **BIEN** si:
- Los 6 tópicos son **interpretables** (tienen sentido temático)
- Distribución balanceada (cada tópico tiene ~15-20% de noticias)
- Perplexity <100 (métrica de calidad del modelo)

⚠️ **AJUSTAR** si:
- Tópicos no tienen sentido → Reducir n_components a 4-5
- Un tópico tiene >50% noticias → Aumentar n_components a 8-10
- Perplexity >150 → Aumentar max_iter o cambiar learning_method

---

## <a name="paso-5-clustering"></a>🔗 PASO 5: Clustering (DBSCAN)

### ¿Qué hace?
Agrupa noticias **MUY similares** usando **DBSCAN** (Density-Based Spatial Clustering).

### ¿Por qué es necesario?
**Identifica casos duplicados o relacionados** al mismo evento.

**Diferencia con LDA (Paso 4)**:
- **LDA**: Agrupa por TEMA general (ej: "apoyo huérfanos")
- **DBSCAN**: Agrupa por SIMILITUD exacta (ej: "mismo feminicidio reportado 3 veces")

### Parámetros que usa

```python
DBSCAN_CONFIG = {
    'eps': 0.6,                # Distancia máxima para agrupar
    'min_samples': 2,          # Mínimo 2 noticias para cluster
    'metric': 'cosine'         # Similitud coseno
}
```

### ¿Qué significa eps = 0.6?

**eps** = **epsilon** = radio de vecindad

**En similitud coseno**:
- eps=0.6 → Distancia ≤ 0.6 → **Similitud ≥ 40%**
- eps=0.4 → Distancia ≤ 0.4 → **Similitud ≥ 60%** (más estricto)
- eps=0.8 → Distancia ≤ 0.8 → **Similitud ≥ 20%** (más permisivo)

**Ejemplo**:
```
Noticia A: "Feminicidio en Edomex deja 3 huérfanos"
Noticia B: "Asesinan mujer en Edomex, 3 niños quedan solos"

Similitud = 75% → Distancia = 0.25 < 0.6 → ✅ MISMO CLUSTER
```

### ¿Qué significa min_samples = 2?

**Para formar un cluster, necesita al menos 2 noticias.**

**Ejemplo**:
```
Cluster 1:
  • Noticia A (CNN)
  • Noticia B (La Jornada)    } Mismo feminicidio, fuentes distintas
  • Noticia C (Excélsior)

Outlier (cluster -1):
  • Noticia D (caso único, sin similares)
```

### Ejemplo de Salida

**Entrada**: Matriz TF-IDF (100 × 1000)

**Salida**: Clusters + Outliers

```
Cluster 0 (5 noticias):
  Palabras clave: feminicidio, edomex, ecatepec, 35 años
  • "Feminicidio en Ecatepec deja 3 huérfanos" (CIMAC)
  • "Asesinan mujer en Edomex, niños quedan solos" (La Jornada)
  • "Matan a madre de familia en Ecatepec" (Excélsior)
  
Cluster 1 (3 noticias):
  Palabras clave: dif, apoyo, custodia, abuelos
  • "DIF otorga custodia a abuelos de huérfanos" (Milenio)
  • "Abuelos reciben apoyo para niños" (SEM México)
  
Outliers (-1): 92 noticias
  • Casos únicos sin similitud suficiente
```

### ¿Cómo calcula la calidad del clustering?

**Silhouette Score** (entre -1 y 1):
- **>0.5**: Excelente separación de clusters
- **0.3-0.5**: Buena separación
- **<0.3**: Clusters mal definidos

```python
silhouette_score = 0.42  # BUENO
```

### ¿Está dando resultados esperados?

✅ **BIEN** si:
- Silhouette >0.3
- 10-40% de outliers (casos únicos)
- Clusters tienen sentido temático

⚠️ **AJUSTAR** si:
- >90% outliers → **eps demasiado pequeño**, aumentar a 0.7-0.8
- <10% outliers → **eps muy grande**, reducir a 0.4-0.5
- Silhouette <0.3 → Ajustar eps o probar K-Means

**NOTA IMPORTANTE**: En noticias es **NORMAL** tener muchos outliers (70-85%) porque cada caso es único.

---

## <a name="paso-6-similitud"></a>🔄 PASO 6: Análisis de Similitud

### ¿Qué hace?
Calcula **similitud coseno** entre cada par de noticias.

### ¿Por qué es necesario?
**Permite recomendar noticias relacionadas** y detectar duplicados.

### ¿Cómo calcula la similitud?

**Similitud Coseno** = Coseno del ángulo entre dos vectores

```
Vector A = [0.8, 0.3, 0.6]  (feminicidio, mujer, hijos)
Vector B = [0.9, 0.4, 0.5]  (similar)

Similitud = cos(θ) = (A · B) / (|A| × |B|)
          = 0.92  (92% similares)
```

### Ejemplo de Salida

**Entrada**: Matriz TF-IDF (100 × 1000)

**Salida**: Para cada noticia, su noticia más similar

```
Noticia 1: "Feminicidio en Edomex..."
  → Más similar: Noticia 47 (similitud: 0.85)
  
Noticia 2: "DIF apoya huérfanos..."
  → Más similar: Noticia 12 (similitud: 0.62)
```

### ¿Está dando resultados esperados?

✅ **BIEN** si:
- Similitud promedio: 0.15-0.35
- Pares con similitud >0.7: 5-15% (posibles duplicados)

⚠️ **REVISAR** si:
- Similitud promedio <0.10 → Noticias muy diversas (normal)
- Similitud promedio >0.50 → Muchos duplicados, filtrar en recolección

---

## <a name="flujo-completo"></a>🔄 Flujo Completo con Ejemplo

### Entrada: 1 Noticia Real

```
Título: "Feminicidio en Ecatepec deja tres menores huérfanos"
Contenido: "Una mujer de 35 años fue asesinada en su domicilio de 
Ecatepec, Estado de México. La víctima deja tres hijos menores de 
edad en situación de orfandad. La fiscalía inició investigación por 
feminicidio."
```

### PASO 1: Recolección ✅
```
Fuente: CIMAC
Fecha: 2025-11-18
Status: ✓ Recolectada exitosamente
```

### PASO 2: Detector ✅
```python
Análisis del detector:
  feminicidio: ✓ (encontrado 1 vez)
  asesinato: ✓ (encontrado 1 vez)
  mujer: ✓ (encontrado 2 veces)
  menores: ✓ (encontrado 1 vez)
  hijos: ✓ (encontrado 1 vez)
  huérfanos: ✓ (encontrado 1 vez)
  orfandad: ✓ (encontrado 1 vez)

Puntuación:
  feminicide_score: 2/40 * 0.40 = 0.020
  children_score: 2/15 * 0.20 = 0.027
  orphan_score: 2/20 * 0.30 = 0.030
  orphan_bonus: 0.10
  
  TOTAL: 0.177 (17.7%)

Resultado:
  es_feminicidio: ✓
  tiene_nna: ✓
  es_objetivo: ✓
  prioridad: BAJA (confianza 17.7%)
```

### PASO 3: Vectorización ✅
```python
Vector TF-IDF (top 10 palabras):

feminicidio: 0.352
ecatepec: 0.298
huérfanos: 0.275
menores: 0.261
asesinada: 0.248
edomex: 0.234
hijos: 0.221
mujer: 0.198
fiscalía: 0.187
investigación: 0.165
... (990 palabras más con valores <0.15)
```

### PASO 4: Tópicos ✅
```python
Distribución por tópico:

Tópico 0 (feminicidio edomex): 15%
Tópico 1 (apoyo huérfanos): 70%  ← ASIGNADO
Tópico 2 (violencia género): 5%
Tópico 3 (familia niños): 8%
Tópico 4 (hallazgo cuerpo): 1%
Tópico 5 (pareja ex): 1%

→ Asignada al Tópico 1 (apoyo huérfanos) con 70% probabilidad
```

### PASO 5: Clustering ✅
```python
Análisis DBSCAN:

Buscando vecinos con similitud >40% (eps=0.6)...

Encontradas 2 noticias similares:
  • Noticia 47: "Asesinan mujer en Ecatepec, 3 niños solos" (sim: 0.78)
  • Noticia 89: "Matan a madre en Edomex" (sim: 0.52)

→ Asignada al Cluster 3 (3 noticias del mismo caso)
```

### PASO 6: Similitud ✅
```python
Noticia más similar:
  ID: 47
  Título: "Asesinan mujer en Ecatepec, 3 niños quedan solos"
  Similitud: 0.78 (78%)
  
→ Probable duplicado o caso relacionado
```

### Salida Final
```json
{
  "titulo": "Feminicidio en Ecatepec deja tres menores huérfanos",
  "es_objetivo": true,
  "prioridad": "BAJA",
  "confianza": 0.177,
  "topic_id": 1,
  "cluster": 3,
  "max_similarity": 0.78,
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
