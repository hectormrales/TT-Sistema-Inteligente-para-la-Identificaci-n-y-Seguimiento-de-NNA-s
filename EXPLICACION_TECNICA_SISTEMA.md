# EXPLICACION TECNICA DEL SISTEMA

**Sistema Inteligente para la Identificacion y Seguimiento de NNA (Ninos, Ninas y Adolescentes) Huerfanos por Feminicidios**

**Fecha:** 12 de noviembre de 2025  
**Version:** 2.0  
**Autores:** Hector Morales

---

## TABLA DE CONTENIDOS

1. [Introduccion](#introduccion)
2. [Arquitectura General](#arquitectura-general)
3. [Recoleccion de Noticias (Web Scraping)](#recoleccion-de-noticias-web-scraping)
4. [Deteccion de Feminicidios con NNA](#deteccion-de-feminicidios-con-nna)
5. [Vectorizacion (TF-IDF)](#vectorizacion-tf-idf)
6. [Modelado de Topicos (LDA)](#modelado-de-topicos-lda)
7. [Clustering (DBSCAN)](#clustering-dbscan)
8. [Analisis de Similitud](#analisis-de-similitud)
9. [Diccionario de Sinonimos](#diccionario-de-sinonimos)
10. [Flujo Completo del Sistema](#flujo-completo-del-sistema)
11. [Ejemplo Practico Paso a Paso](#ejemplo-practico-paso-a-paso)

---

## INTRODUCCION

### Objetivo del Proyecto

Detectar y dar seguimiento a noticias sobre **feminicidios que dejan NNA en situacion de orfandad** en Mexico, utilizando tecnicas de:
- Web Scraping
- Procesamiento de Lenguaje Natural (NLP)
- Machine Learning (ML)
- Clustering automatico

### Problema que Resuelve

Los medios publican cientos de noticias diarias. Este sistema:
1. Recolecta noticias automaticamente de multiples fuentes
2. Filtra SOLO feminicidios que mencionan NNA (hijos, huerfanos)
3. Agrupa noticias similares
4. Prioriza casos criticos (ALTA, MEDIA, BAJA)
5. Visualiza resultados en dashboard web

---

## ARQUITECTURA GENERAL

```
┌─────────────────────────────────────────────────────────────────┐
│                      CAPA DE RECOLECCION                        │
├─────────────────────────────────────────────────────────────────┤
│  RSS Feeds (8 fuentes)  +  Google News Search                   │
│  ↓                                                               │
│  BeautifulSoup (Parse XML/HTML)                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                   CAPA DE DETECCION INTELIGENTE                 │
├─────────────────────────────────────────────────────────────────┤
│  FeminicideDetector (Regex + Sistema de Confianza)             │
│  ↓                                                               │
│  Patrones: Feminicidio + NNA + Huerfanos                        │
│  ↓                                                               │
│  Confianza: 0-100% | Prioridad: ALTA/MEDIA/BAJA                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                  CAPA DE PROCESAMIENTO (NLP/ML)                 │
├─────────────────────────────────────────────────────────────────┤
│  1. TF-IDF → Vectorizacion de texto                             │
│  2. LDA → Descubrimiento de topicos                             │
│  3. DBSCAN → Clustering automatico                              │
│  4. Cosine Similarity → Similitud entre noticias                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                     CAPA DE PRESENTACION                        │
├─────────────────────────────────────────────────────────────────┤
│  Dashboard Web (Flask) | API REST | Exportacion CSV            │
└─────────────────────────────────────────────────────────────────┘
```

---

## RECOLECCION DE NOTICIAS (WEB SCRAPING)

### 1.1 Metodo Principal: RSS Feeds

**Archivo:** `src/collection/data_collector.py`  
**Funcion:** `collect_news_from_rss(rss_url)`

#### ¿Que es RSS?

**RSS** (Really Simple Syndication) es un formato XML que los sitios web usan para publicar sus articulos mas recientes.

#### Proceso Paso a Paso

**1. Conexion al Feed:**

```python
import requests
from bs4 import BeautifulSoup

# Conectar al feed RSS
response = requests.get(rss_url, headers=headers, timeout=10)
soup = BeautifulSoup(response.content, 'xml')
```

**Ejemplo de XML RSS:**

```xml
<rss>
  <channel>
    <item>
      <title>Feminicidio en Edomex deja 3 hijos huerfanos</title>
      <description><![CDATA[<p>Contenido de la noticia...</p>]]></description>
      <link>https://ejemplo.com/noticia/123</link>
      <pubDate>Mon, 11 Nov 2025 10:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
```

**2. Extraccion de Datos:**

```python
for item in soup.find_all('item'):
    # Extraer campos
    titulo = item.find('title').text.strip()
    descripcion = item.find('description').text
    enlace = item.find('link').text.strip()
    fecha = item.find('pubDate').text.strip()
    
    # Limpiar HTML de la descripcion
    desc_html = BeautifulSoup(descripcion, 'html.parser')
    contenido_limpio = desc_html.get_text(" ", strip=True)
```

**3. Normalizacion de Fecha:**

```python
from email.utils import parsedate_to_datetime

# Convertir fecha RSS a ISO 8601
fecha_obj = parsedate_to_datetime(fecha)
# Resultado: datetime(2025, 11, 11, 10, 30, 0)
fecha_iso = fecha_obj.isoformat()
# Resultado: "2025-11-11T10:30:00+00:00"
```

#### Fuentes RSS Configuradas

```python
# config.py
RSS_FEEDS = [
    # Especializadas en genero y feminicidios
    'https://cimacnoticias.com.mx/feed/',
    'https://www.semmexico.mx/feed/',
    
    # Secciones de seguridad/estados
    'https://www.jornada.com.mx/rss/estados.xml',
    'https://www.animalpolitico.com/category/seguridad/feed/',
    'https://www.proceso.com.mx/seccion/nacional/feed',
    
    # Medios generales con cobertura
    'https://aristeguinoticias.com/feed/',
    'https://www.sinembargo.mx/feed/',
    'https://www.jornada.com.mx/rss/politica.xml',
]
```

### 1.2 Metodo Complementario: Google News Search

**Archivo:** `src/collection/data_collector.py`  
**Funcion:** `collect_from_google_news(query, max_results)`

#### ¿Por que Google News?

Los RSS feeds solo muestran las ultimas 10-20 noticias publicadas. Si no hay feminicidios HOY → 0% resultados.

**Google News permite buscar especificamente:**

```python
query = "feminicidio hijos huerfanos mexico"
url = f"https://news.google.com/rss/search?q={query}&hl=es-MX&gl=MX"
```

#### Ventajas

1. **Busqueda dirigida:** Solo noticias relevantes
2. **Mayor cobertura:** Ultimos 7-30 dias
3. **Multiples fuentes:** Agrega noticias de cientos de sitios

#### Proceso

```python
# 1. Construir URL de busqueda
search_url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}"

# 2. Descargar RSS de resultados
response = requests.get(search_url, headers=headers, timeout=15)
soup = BeautifulSoup(response.content, 'xml')

# 3. Extraer items (igual que RSS normal)
for item in soup.find_all('item')[:max_results]:
    # ... mismo proceso de extraccion
```

### 1.3 Resultado de Recoleccion

**Salida:** Lista de diccionarios con estructura:

```python
{
    'titulo': 'Feminicidio en Edomex deja 3 hijos huerfanos',
    'contenido': 'Tres menores quedaron en situacion de...',
    'enlace': 'https://ejemplo.com/noticia/123',
    'fuente': 'https://cimacnoticias.com.mx/feed/',
    'fecha': '2025-11-11T10:30:00+00:00',
    'cluster': 0,  # Se asignara despues
    # Campos de deteccion (siguiente seccion)
}
```

---

## DETECCION DE FEMINICIDIOS CON NNA

### 2.1 FeminicideDetector - El Corazon del Sistema

**Archivo:** `src/collection/feminicide_detector.py`  
**Clase:** `FeminicideDetector`

#### Objetivo

Determinar si una noticia cumple con el objetivo del proyecto:
1. ¿Es sobre feminicidio?
2. ¿Menciona NNA (hijos, menores)?
3. ¿Menciona huerfanos/victimas indirectas?

### 2.2 Sistema de Patrones (Expresiones Regulares)

#### Tipo 1: Patrones de Feminicidio (40% peso)

```python
patterns_feminicide = [
    # Terminos directos
    r'\bfeminicidio\b',
    r'\bfemicidio\b',
    
    # Contextos de asesinato
    r'mujer.*(?:asesinada|hallada\s+muerta|encontrada\s+sin\s+vida)',
    r'madre.*(?:asesinada|hallada\s+muerta)',
    r'homicidio.*mujer',
    r'hallar.*muerta',
    
    # Investigacion
    r'fiscalia.*feminicidio',
    r'alerta.*g[eé]nero',
    r'caso.*feminicidio',
    r'investigar.*feminicidio',
    
    # Contextos especificos
    r'violencia.*feminicida',
    r'crimen.*g[eé]nero',
]
```

**Ejemplo de coincidencia:**

```python
texto = "Fiscalia investiga feminicidio en Edomex"

if re.search(r'\bfeminicidio\b', texto):
    # ✅ COINCIDE
    confianza += 0.40
```

#### Tipo 2: Patrones de NNA (20% peso)

```python
patterns_children = [
    # Terminos generales
    r'\bhij[oa]s?\b',              # hijo, hija, hijos, hijas
    r'\bmenor(?:es)?\b',           # menor, menores
    r'\bni[ñn][oa]s?\b',           # nino, nina, ninos, ninas
    r'\badolescentes?\b',
    r'\binfant(?:e|es|il)\b',
    r'\bbeb[eé]s?\b',
    r'\breci[eé]n\s+nacid[oa]s?\b',
    r'\bpeque[ñn][oa]s?\b',
    r'\bcr[ií][oa]s?\b',
    
    # Siglas
    r'\bNNA\b',
]
```

**Ejemplo:**

```python
texto = "Feminicidio deja 3 hijos menores de edad"

if re.search(r'\bhij[oa]s?\b', texto):  # ✅ "hijos"
    confianza += 0.20
```

#### Tipo 3: Patrones de Huerfanos (30% peso + BONUS)

```python
patterns_orphans = [
    # Orfandad directa
    r'\bhu[eé]rfan[oa]s?\b',
    r'\borfandad\b',
    
    # Contextos de abandono
    r'hijos?\s+quedan?(?:\s+(?:solos?|desamparados?|abandonados?))?',
    r'sin\s+madre',
    r'sin\s+sus?\s+madres?',
    r'madre.*fall(?:eci[oó]|ecida)',
    r'perder.*madre',
    
    # Victimas indirectas
    r'v[ií]ctimas?\s+indirectas?',
    r'v[ií]ctimas?\s+colaterales?',
    
    # Custodia/proteccion
    r'DIF.*(?:cargo|custodia)',
    r'custodia.*(?:menores?|ni[ñn]os?)',
    r'albergue.*(?:menores?|ni[ñn]os?)',
    r'adopci[oó]n',
    
    # Impacto emocional
    r'ni[ñn]os?.*presenciar',
    r'hijos?.*traumatizad[oa]s?',
    r'testigos?.*(?:menores?|ni[ñn]os?)',
]
```

### 2.3 Sistema de Confianza (Scoring)

```python
def detect(self, text):
    confidence = 0.0
    matched_patterns = {
        'feminicide': [],
        'children': [],
        'orphans': []
    }
    
    # 1. Detectar feminicidio (40%)
    is_feminicide = False
    for pattern in self.patterns_feminicide:
        if re.search(pattern, text, re.IGNORECASE):
            is_feminicide = True
            confidence += 0.40
            matched_patterns['feminicide'].append(pattern)
            break  # Solo contar una vez
    
    # 2. Detectar NNA (20%)
    has_children = False
    for pattern in self.patterns_children:
        if re.search(pattern, text, re.IGNORECASE):
            has_children = True
            confidence += 0.20
            matched_patterns['children'].append(pattern)
            break
    
    # 3. Detectar huerfanos (30%)
    has_orphans = False
    for pattern in self.patterns_orphans:
        if re.search(pattern, text, re.IGNORECASE):
            has_orphans = True
            confidence += 0.30
            matched_patterns['orphans'].append(pattern)
            break
    
    # 4. BONUS: Combinacion perfecta (+10%)
    if is_feminicide and has_children and has_orphans:
        confidence += 0.10
    
    # 5. Limitar confianza maxima a 100%
    confidence = min(confidence, 1.0)
    
    return {
        'is_feminicide': is_feminicide,
        'has_children': has_children,
        'has_orphans': has_orphans,
        'is_target_news': is_feminicide and (has_children or has_orphans),
        'confidence': confidence,
        'matched_patterns': matched_patterns,
        'priority': self._calculate_priority(...)
    }
```

### 2.4 Sistema de Priorizacion

```python
def _calculate_priority(self, is_feminicide, has_children, has_orphans, confidence):
    """
    ALTA: Feminicidio + huerfanos + confianza >= 70%
    MEDIA: Feminicidio + huerfanos (cualquier confianza)
           O feminicidio + NNA + confianza >= 50%
    BAJA: Feminicidio sin NNA claro
    IRRELEVANTE: No es feminicidio
    """
    
    if not is_feminicide:
        return 'IRRELEVANTE'
    
    if has_orphans and confidence >= 0.7:
        return 'ALTA'  # ⭐⭐⭐ CASO CRITICO
    
    if has_orphans:
        return 'MEDIA'  # ⭐⭐ Feminicidio con huerfanos
    
    if has_children and confidence >= 0.5:
        return 'MEDIA'  # ⭐⭐ Feminicidio con NNA
    
    if confidence >= 0.5:
        return 'MEDIA'  # ⭐⭐ Feminicidio con alta confianza
    
    return 'BAJA'  # ⭐ Feminicidio sin mencion clara de NNA
```

### 2.5 Ejemplo de Deteccion

**Entrada:**

```python
texto = "Edomex otorga apoyo economico a ninos y adolescentes en orfandad por feminicidio"
```

**Proceso:**

```python
# Paso 1: Buscar feminicidio
"feminicidio" encontrado → is_feminicide = True
confidence += 0.40

# Paso 2: Buscar NNA
"ninos y adolescentes" encontrado → has_children = True
confidence += 0.20

# Paso 3: Buscar huerfanos
"orfandad" encontrado → has_orphans = True
confidence += 0.30

# Paso 4: BONUS (todos presentes)
confidence += 0.10

# Paso 5: Total
confidence = 1.00 (limitar a 80% maximo)
confidence = 0.80
```

**Salida:**

```python
{
    'is_feminicide': True,
    'has_children': True,
    'has_orphans': True,
    'is_target_news': True,  # ✅ CUMPLE OBJETIVO
    'confidence': 0.80,      # 80% confianza
    'priority': 'ALTA',      # ⭐⭐⭐ PRIORIDAD MAXIMA
    'matched_patterns': {
        'feminicide': ['feminicidio'],
        'children': ['ninos', 'adolescentes'],
        'orphans': ['orfandad']
    }
}
```

---

## VECTORIZACION (TF-IDF)

### 3.1 ¿Que es TF-IDF?

**TF-IDF** = Term Frequency - Inverse Document Frequency

Tecnica que **convierte texto en numeros** para que los algoritmos de Machine Learning puedan:
- Comparar noticias
- Agrupar noticias similares
- Buscar noticias relevantes

### 3.2 Componentes

#### TF (Term Frequency) - Frecuencia del Termino

Mide: **¿Que tan importante es una palabra en UN documento?**

```
TF = (veces que aparece la palabra) / (total de palabras en el documento)
```

**Ejemplo:**

```
Documento: "Feminicidio en Edomex. Caso de feminicidio deja huerfanos."
Palabras: 9 palabras

TF(feminicidio) = 2 / 9 = 0.22  # Aparece 2 veces
TF(Edomex) = 1 / 9 = 0.11       # Aparece 1 vez
TF(en) = 1 / 9 = 0.11           # Aparece 1 vez
```

#### IDF (Inverse Document Frequency) - Frecuencia Inversa del Documento

Mide: **¿Que tan unica es una palabra en TODOS los documentos?**

```
IDF = log(total de documentos / documentos que contienen la palabra)
```

**Razonamiento:**
- Palabras comunes ("el", "en", "de") aparecen en casi todos → IDF bajo
- Palabras especificas ("feminicidio") aparecen en pocos → IDF alto

**Ejemplo:**

```
Total documentos: 100

IDF(feminicidio) = log(100 / 25) = 1.39
# "feminicidio" aparece en 25 documentos → palabra IMPORTANTE

IDF(en) = log(100 / 95) = 0.05
# "en" aparece en 95 documentos → palabra COMUN → bajo peso
```

#### TF-IDF Final

```
TF-IDF(palabra) = TF × IDF
```

**Ejemplo:**

```
TF-IDF(feminicidio) = 0.22 × 1.39 = 0.31  # ALTO (palabra importante)
TF-IDF(en) = 0.11 × 0.05 = 0.006          # BAJO (palabra comun)
```

### 3.3 Implementacion en el Sistema

**Archivo:** `src/analysis/simplified_analyzer.py`

```python
from sklearn.feature_extraction.text import TfidfVectorizer

# Configuracion del vectorizador
vectorizer = TfidfVectorizer(
    max_features=3000,      # Usar las 3000 palabras mas importantes
    ngram_range=(1, 2),     # Palabras individuales y pares
    min_df=1,               # Minimo 1 documento debe contener la palabra
    max_df=0.8,             # Maximo 80% de documentos (evita muy comunes)
    stop_words=stopwords    # Palabras a ignorar ("el", "la", "de"...)
)

# Entrenar y transformar
tfidf_matrix = vectorizer.fit_transform(textos_limpios)
# Resultado: matriz (n_noticias, 3000)
```

### 3.4 Proceso Completo

#### Paso 1: Limpieza de Texto

```python
def limpiar_texto(texto):
    # 1. Minusculas
    texto = texto.lower()
    # "Feminicidio en Edomex" → "feminicidio en edomex"
    
    # 2. Quitar acentos
    texto = unidecode(texto)
    # "México" → "Mexico"
    
    # 3. Quitar puntuacion
    texto = re.sub(r'[^\w\s]', ' ', texto)
    # "¿Feminicidio?" → "Feminicidio"
    
    # 4. Quitar numeros
    texto = re.sub(r'\d+', '', texto)
    
    # 5. Quitar espacios multiples
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto
```

**Antes:**

```
"¿Feminicidio en México deja 3 hijos huérfanos?"
```

**Despues:**

```
"feminicidio en mexico deja hijos huerfanos"
```

#### Paso 2: Tokenizacion

```python
tokens = ["feminicidio", "en", "mexico", "deja", "hijos", "huerfanos"]
```

#### Paso 3: Generacion de N-grams

```python
# ngram_range=(1, 2) significa:
# - Unigrams: palabras individuales
# - Bigrams: pares de palabras

Unigrams: ["feminicidio", "mexico", "hijos", "huerfanos"]
Bigrams: ["feminicidio mexico", "mexico deja", "deja hijos", "hijos huerfanos"]
```

#### Paso 4: Calculo TF-IDF

Para cada noticia, calcular TF-IDF de cada palabra:

```python
# Noticia 1:
[
    0.31,  # feminicidio
    0.00,  # en (stopword, removida)
    0.12,  # mexico
    0.00,  # deja (muy comun)
    0.18,  # hijos
    0.25,  # huerfanos
    ...    # hasta 3000 valores
]
```

### 3.5 Matriz TF-IDF Resultante

```
        feminicidio  mexico  hijos  huerfanos  ... (3000 palabras)
Noticia1    0.31      0.12   0.18     0.25     ...
Noticia2    0.29      0.00   0.22     0.30     ...
Noticia3    0.00      0.15   0.00     0.00     ...
...
Noticia94   0.15      0.10   0.08     0.12     ...
```

**Dimension:** (94 noticias, 3000 palabras)

### 3.6 Ventajas de TF-IDF

1. **Captura importancia contextual:** Palabras clave tienen mayor peso
2. **Reduce ruido:** Palabras comunes tienen bajo peso
3. **Permite comparacion numerica:** Noticias similares tienen vectores similares
4. **Base para clustering:** DBSCAN necesita vectores numericos

---

## MODELADO DE TOPICOS (LDA)

### 4.1 ¿Que es LDA?

**LDA** = Latent Dirichlet Allocation

Algoritmo de Machine Learning que **descubre temas ocultos** en un conjunto de documentos automaticamente.

### 4.2 Concepto

LDA asume:
1. Cada noticia es una **mezcla de varios topicos**
2. Cada topico es una **distribucion de palabras**

**Ejemplo:**

```
Topico 1 (Feminicidios): feminicidio (30%), mujer (25%), victima (20%)...
Topico 2 (Huerfanos): huerfanos (35%), hijos (30%), ninos (20%)...

Noticia X = 70% Topico 1 + 30% Topico 2
```

### 4.3 Implementacion

**Archivo:** `src/analysis/simplified_analyzer.py`

```python
from sklearn.decomposition import LatentDirichletAllocation

# Configuracion
lda = LatentDirichletAllocation(
    n_components=6,        # Crear 6 topicos
    random_state=42,       # Reproducibilidad
    max_iter=10,          # Iteraciones de entrenamiento
    learning_method='batch'
)

# Entrenar modelo
lda.fit(tfidf_matrix)

# Transformar documentos (asignar topicos)
topic_distributions = lda.transform(tfidf_matrix)
```

### 4.4 Extraccion de Topicos

```python
# Obtener palabras mas importantes de cada topico
feature_names = vectorizer.get_feature_names_out()

for topic_idx, topic in enumerate(lda.components_):
    # Obtener indices de las 5 palabras mas importantes
    top_indices = topic.argsort()[-5:][::-1]
    
    # Obtener palabras
    top_words = [feature_names[i] for i in top_indices]
    
    print(f"Topico {topic_idx}: {' '.join(top_words)}")
```

### 4.5 Topicos Descubiertos (Ejemplo Real)

```
Topico 0: del sus defensoras derechos oaxaca
→ Tema: Defensoras de derechos humanos

Topico 1: las xico 2025 contra 10
→ Tema: Noticias generales de Mexico 2025

Topico 2: las xico esta del congreso
→ Tema: Politica y legislacion

Topico 3: xico hue hue rfanos rfanos del
→ Tema: HUERFANOS POR FEMINICIDIO ⭐

Topico 4: una cuidar del agua atencio
→ Tema: Cuidados y atencion

Topico 5: feminicidio hue rfanos hue nin vi ctimas
→ Tema: FEMINICIDIOS CON VICTIMAS NNA ⭐⭐⭐
```

### 4.6 Asignacion de Topicos a Noticias

```python
# Para cada noticia:
topic_distributions = lda.transform(tfidf_matrix)
# Resultado: matriz (94 noticias, 6 topicos)

# Ejemplo para Noticia 1:
[0.05, 0.10, 0.08, 0.15, 0.12, 0.50]
  ↑     ↑     ↑     ↑     ↑     ↑
 Top0  Top1  Top2  Top3  Top4  Top5

# Interpretacion: Noticia 1 es 50% Topico 5 (feminicidios+NNA)
```

### 4.7 Seleccion de Topico Principal

```python
for idx, distribution in enumerate(topic_distributions):
    # Topico con mayor probabilidad
    topic_id = distribution.argmax()
    topic_probability = distribution[topic_id]
    
    # Descripcion del topico (palabras principales)
    topic_description = ' '.join(top_words[topic_id])
    
    # Asignar a la noticia
    df.loc[idx, 'topic_id'] = topic_id
    df.loc[idx, 'topic_probability'] = topic_probability
    df.loc[idx, 'topic_description'] = topic_description
```

### 4.8 Utilidad de LDA

1. **Descubrimiento automatico:** No necesitas etiquetar manualmente
2. **Categorizacion:** Agrupa noticias por tema
3. **Navegacion:** Dashboard puede filtrar por topico
4. **Analisis:** Identificar que temas se discuten mas

---

## CLUSTERING (DBSCAN)

### 5.1 ¿Que es DBSCAN?

**DBSCAN** = Density-Based Spatial Clustering of Applications with Noise

Algoritmo de clustering que:
- **NO necesitas decir cuantos clusters crear** (a diferencia de K-Means)
- **Detecta automaticamente** grupos densos de puntos
- **Identifica outliers** (puntos aislados)

### 5.2 Concepto

DBSCAN agrupa puntos que estan **"cerca"** entre si y tienen suficientes **"vecinos"**.

```
Puntos cercanos = MISMO CLUSTER
Puntos lejanos = DIFERENTES CLUSTERS
Puntos sin vecinos = OUTLIERS (cluster -1)
```

### 5.3 Parametros

#### eps (Epsilon) - Radio de busqueda

```
eps = 0.6

Significa: "Dos noticias son vecinas si su distancia <= 0.6"

En terminos de similitud del coseno:
similitud = 1 - distancia
similitud >= 1 - 0.6 = 0.4 (40% similares)
```

**Visualizacion:**

```
        Noticia A
           ●
          / \
         /   \  eps = 0.6
        /     \
       ●-------● Noticia B
   
   Si distancia(A,B) <= 0.6 → SON VECINAS
```

#### min_samples - Minimo de vecinos

```
min_samples = 2

Significa: "Para formar un cluster, necesito al menos 2 noticias cercanas"
```

### 5.4 Implementacion

**Archivo:** `src/analysis/simplified_analyzer.py`

```python
from sklearn.cluster import DBSCAN

# Configuracion
dbscan = DBSCAN(
    eps=0.6,              # Distancia maxima para vecinos
    min_samples=2,        # Minimo 2 noticias por cluster
    metric='cosine'       # Usar similitud del coseno
)

# Aplicar clustering
clusters = dbscan.fit_predict(tfidf_matrix)
# Resultado: array con cluster de cada noticia
# Ejemplo: [-1, 0, 0, -1, 1, 1, -1, ...]
#           ↑   ↑   ↑   ↑   ↑   ↑   ↑
#        Out C0  C0  Out C1  C1  Out
```

### 5.5 Algoritmo Paso a Paso

**Para cada noticia:**

1. **Calcular distancia** a todas las demas noticias
   ```python
   distancia(A, B) = 1 - cosine_similarity(A, B)
   ```

2. **Encontrar vecinos** (noticias con distancia <= eps)
   ```python
   vecinos_A = [B, C, D]  # Noticias con distancia <= 0.6
   ```

3. **Clasificar el punto:**
   ```python
   if len(vecinos_A) >= min_samples:
       # Punto CORE (nucleo de cluster)
       A pertenece a un cluster
   else:
       # Punto OUTLIER (aislado)
       A es cluster -1
   ```

4. **Expandir cluster:**
   ```python
   Si A es CORE:
       - Agregar A al cluster
       - Agregar todos sus vecinos al cluster
       - Para cada vecino, repetir proceso
   ```

### 5.6 Tipos de Puntos

```
CORE POINT (Nucleo):
    ● → Tiene >= min_samples vecinos
    → Forma parte de un cluster denso

BORDER POINT (Frontera):
    ○ → Tiene < min_samples vecinos
    → Pero esta cerca de un CORE POINT
    → Se agrega al cluster del CORE

NOISE POINT (Ruido/Outlier):
    × → No tiene suficientes vecinos
    → No esta cerca de ningun CORE
    → Cluster = -1
```

### 5.7 Ejemplo Visual

```
Caso 1: Cluster denso
    ●───●
    │\ /│
    │ ● │  ← 4 noticias muy similares
    │/ \│
    ●───●
Resultado: Cluster 0 (4 noticias)

Caso 2: Noticias aisladas
    ●
                ●
                            ●
Resultado: 3 outliers (cluster -1)
```

### 5.8 Resultados del Sistema

```python
# Ejemplo real del sistema:
Clusters detectados: 1
Noticias en clusters: 2
Outliers: 92

Distribucion:
- Cluster 0: 2 noticias
  * "Congreso trabaja en iniciativa contra orfandad por feminicidio CDMX"
  * "Infobae: Casos de feminicidio en CDMX"
  → Palabras clave: cdmx, infobae, casos, feminicidio, iniciativa

- Cluster -1: 92 noticias
  → Noticias unicas sin suficiente similitud
```

### 5.9 ¿Por que tantos outliers?

1. **Noticias diversas:** 68% son irrelevantes (no feminicidios)
2. **Casos unicos:** Cada feminicidio ocurre en lugar/contexto diferente
3. **Vocabulario variado:** Medios usan palabras distintas
4. **Parametros estrictos:** eps=0.6 requiere 40% similitud

### 5.10 Ventajas de DBSCAN

1. **No necesitas K:** Descubre automaticamente cuantos clusters hay
2. **Detecta outliers:** Identifica noticias atipicas
3. **Formas arbitrarias:** No asume clusters esfericos (como K-Means)
4. **Robusto:** No se afecta por outliers

---

## ANALISIS DE SIMILITUD

### 6.1 Similitud del Coseno

**Metrica matematica** que mide cuan similares son dos noticias.

### 6.2 Concepto Geometrico

Cada noticia es un **vector en espacio de 3000 dimensiones**.

```
Noticia A = [0.31, 0.12, 0.18, 0.25, ...]  ← 3000 numeros
Noticia B = [0.29, 0.10, 0.22, 0.30, ...]  ← 3000 numeros
```

**Similitud del coseno** mide el **angulo** entre estos vectores:

```
similitud = cos(θ)

θ = 0°   → similitud = 1.0  (vectores identicos, 100% similares)
θ = 45°  → similitud = 0.7  (vectores parecidos, 70% similares)
θ = 90°  → similitud = 0.0  (vectores ortogonales, 0% similares)
```

### 6.3 Formula Matematica

```
similitud(A, B) = (A · B) / (||A|| × ||B||)

Donde:
A · B = producto punto (suma de productos elemento por elemento)
||A|| = magnitud del vector A
```

### 6.4 Implementacion

```python
from sklearn.metrics.pairwise import cosine_similarity

# Calcular similitud entre TODAS las noticias
similarity_matrix = cosine_similarity(tfidf_matrix)

# Resultado: matriz (94, 94)
# similarity_matrix[i][j] = similitud entre noticia i y j
```

**Ejemplo de matriz:**

```
         Not1  Not2  Not3  Not4
Noticia1  1.0   0.65  0.12  0.03
Noticia2  0.65  1.0   0.08  0.05
Noticia3  0.12  0.08  1.0   0.70
Noticia4  0.03  0.05  0.70  1.0
```

### 6.5 Encontrar Noticia Mas Similar

```python
for i in range(len(similarity_matrix)):
    # Obtener similitudes de noticia i con todas las demas
    similarities = similarity_matrix[i].copy()
    
    # Excluir similitud consigo misma (siempre 1.0)
    similarities[i] = -1
    
    # Encontrar la mas similar
    most_similar_idx = similarities.argmax()
    max_similarity = similarities[most_similar_idx]
    
    # Guardar
    df.loc[i, 'most_similar_doc_idx'] = most_similar_idx
    df.loc[i, 'max_similarity'] = max_similarity
```

### 6.6 Interpretacion de Valores

```
Similitud >= 0.8: Noticias CASI IDENTICAS (posibles duplicados)
Similitud 0.5-0.8: Noticias MUY SIMILARES (mismo evento)
Similitud 0.3-0.5: Noticias RELACIONADAS (tema similar)
Similitud < 0.3: Noticias DIFERENTES
```

### 6.7 Utilidad

1. **Deteccion de duplicados:** Similitud > 0.8
2. **Recomendaciones:** "Noticias relacionadas"
3. **Validacion de clusters:** Clusters deben tener alta similitud interna
4. **Cobertura mediatica:** Cuantos medios cubren el mismo caso

---

## DICCIONARIO DE SINONIMOS

### 7.1 Objetivo

Mejorar la **busqueda** en el dashboard expandiendo consultas con sinonimos.

**Ejemplo:**

```
Usuario busca: "femicidio"
Sistema tambien busca: "feminicidio", "asesinato de mujer", "crimen de genero"
→ Encuentra MAS resultados
```

### 7.2 Estructura

**Archivo:** `src/analysis/synonym_dictionary.py`

```python
{
    "feminicidio": [
        "femicidio",
        "asesinato de mujer",
        "homicidio de mujer",
        "crimen de genero",
        "violencia feminicida",
        "muerte violenta de mujer"
    ],
    
    "ninos": [
        "ninas",
        "menores",
        "infantes",
        "NNA",
        "pequenos",
        "crios"
    ],
    
    "huerfanos": [
        "orfandad",
        "sin madre",
        "hijos quedan",
        "desamparados",
        "victimas indirectas"
    ]
}
```

### 7.3 Uso en Busqueda

```python
def search_with_synonyms(query):
    # 1. Buscar query original
    results = search_in_database(query)
    
    # 2. Obtener sinonimos
    synonyms = synonym_dict.get_synonyms(query)
    
    # 3. Buscar cada sinonimo
    for synonym in synonyms:
        results.extend(search_in_database(synonym))
    
    # 4. Eliminar duplicados
    results = list(set(results))
    
    return results
```

**Ejemplo:**

```python
query = "femicidio"
synonyms = ["feminicidio", "asesinato de mujer", "crimen de genero"]

# Buscar en titulos y contenidos:
mask = (
    df['titulo'].str.contains('femicidio') |
    df['titulo'].str.contains('feminicidio') |
    df['titulo'].str.contains('asesinato de mujer') |
    df['titulo'].str.contains('crimen de genero')
)

results = df[mask]
```

---

## FLUJO COMPLETO DEL SISTEMA

### 8.1 Diagrama de Flujo

```
START
  ↓
┌─────────────────────────────────────────┐
│ 1. RECOLECCION                          │
│    - RSS Feeds (8 fuentes)              │
│    - Google News Search                 │
│    Resultado: 94 noticias crudas        │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ 2. DETECCION (FeminicideDetector)      │
│    - Regex Feminicidio → +40%          │
│    - Regex NNA → +20%                   │
│    - Regex Huerfanos → +30%             │
│    - Bonus → +10%                       │
│    Resultado: 26 feminicidios (27.7%)  │
│              12 objetivo (12.8%)        │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ 3. LIMPIEZA DE TEXTO                    │
│    - Minusculas                         │
│    - Quitar acentos                     │
│    - Quitar puntuacion                  │
│    Resultado: textos normalizados       │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ 4. VECTORIZACION (TF-IDF)               │
│    - 3000 palabras mas importantes      │
│    - Bigrams (pares de palabras)        │
│    Resultado: matriz (94, 3000)         │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ 5. MODELADO DE TOPICOS (LDA)            │
│    - 6 topicos                          │
│    - Asignar topico principal           │
│    Resultado: Topico 5 (fem + NNA)      │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ 6. CLUSTERING (DBSCAN)                  │
│    - eps=0.6, min_samples=2             │
│    Resultado: 1 cluster, 92 outliers    │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ 7. SIMILITUD (Cosine)                   │
│    - Calcular similitud entre todos     │
│    - Encontrar noticia mas similar      │
│    Resultado: promedio 15.4% similar    │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ 8. GUARDADO                             │
│    - CSV con todos los campos           │
│    - JSON con metadatos                 │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│ 9. DASHBOARD WEB (Flask)                │
│    - Visualizacion de estadisticas      │
│    - Busqueda con sinonimos             │
│    - Exportacion CSV                    │
└─────────────────────────────────────────┘
  ↓
END
```

### 8.2 Tiempo de Ejecucion

```
Recoleccion: ~30 segundos
  ├─ RSS Feeds: ~10s
  └─ Google News: ~20s

Deteccion: ~1 segundo
  └─ Regex en 94 noticias

Procesamiento ML: ~5 segundos
  ├─ TF-IDF: ~1s
  ├─ LDA: ~2s
  ├─ DBSCAN: ~1s
  └─ Similitud: ~1s

TOTAL: ~36 segundos
```

---

## EJEMPLO PRACTICO PASO A PASO

### 9.1 Noticia Real

**Titulo:** "Edomex otorga apoyo economico a ninos y adolescentes en orfandad por feminicidio"  
**Fuente:** Google News → Milenio  
**Fecha:** 11 de noviembre de 2025

### 9.2 Paso 1: Recoleccion (Web Scraping)

```python
# RSS XML descargado:
<item>
  <title>Edomex otorga apoyo economico a ninos y adolescentes en orfandad por feminicidio</title>
  <link>https://milenio.com/...</link>
  <pubDate>Mon, 11 Nov 2025 10:30:00 GMT</pubDate>
  <description>El gobierno del Estado de Mexico anuncio...</description>
</item>

# Extraccion:
noticia = {
    'titulo': 'Edomex otorga apoyo economico a ninos y adolescentes...',
    'contenido': 'El gobierno del Estado de Mexico anuncio...',
    'enlace': 'https://milenio.com/...',
    'fuente': 'Google News',
    'fecha': '2025-11-11T10:30:00+00:00'
}
```

### 9.3 Paso 2: Deteccion (FeminicideDetector)

```python
texto_completo = "Edomex otorga apoyo economico a ninos y adolescentes en orfandad por feminicidio"

# Analisis de patrones:

# 1. Buscar feminicidio (40%)
if re.search(r'\bfeminicidio\b', texto_completo):
    # ✅ ENCONTRADO: "feminicidio"
    is_feminicide = True
    confidence += 0.40

# 2. Buscar NNA (20%)
if re.search(r'\bni[ñn][oa]s?\b', texto_completo):
    # ✅ ENCONTRADO: "ninos"
    has_children = True
    confidence += 0.20
if re.search(r'\badolescentes?\b', texto_completo):
    # ✅ ENCONTRADO: "adolescentes"
    # Ya se conto, no sumar de nuevo

# 3. Buscar huerfanos (30%)
if re.search(r'\borfandad\b', texto_completo):
    # ✅ ENCONTRADO: "orfandad"
    has_orphans = True
    confidence += 0.30

# 4. BONUS (10%)
if is_feminicide and has_children and has_orphans:
    # ✅ TODOS PRESENTES
    confidence += 0.10

# TOTAL:
confidence = 1.00  # Limitar a 80%
confidence = 0.80

# PRIORIZACION:
if has_orphans and confidence >= 0.7:
    priority = 'ALTA'  # ⭐⭐⭐

# RESULTADO:
{
    'is_feminicide': True,
    'has_children': True,
    'has_orphans': True,
    'is_target_news': True,
    'confidence': 0.80,
    'priority': 'ALTA'
}
```

### 9.4 Paso 3: Limpieza de Texto

```python
# Original:
"Edomex otorga apoyo económico a niños y adolescentes en orfandad por feminicidio"

# 1. Minusculas:
"edomex otorga apoyo económico a niños y adolescentes en orfandad por feminicidio"

# 2. Quitar acentos:
"edomex otorga apoyo economico a ninos y adolescentes en orfandad por feminicidio"

# 3. Quitar stopwords ("a", "en", "por"):
"edomex otorga apoyo economico ninos adolescentes orfandad feminicidio"

# RESULTADO FINAL:
texto_limpio = "edomex otorga apoyo economico ninos adolescentes orfandad feminicidio"
```

### 9.5 Paso 4: Vectorizacion (TF-IDF)

```python
# Calculo TF (frecuencia en el documento):
palabras_totales = 8
TF(feminicidio) = 1/8 = 0.125
TF(orfandad) = 1/8 = 0.125
TF(ninos) = 1/8 = 0.125
...

# Calculo IDF (rareza en todos los documentos):
total_docs = 94
docs_con_feminicidio = 26
IDF(feminicidio) = log(94/26) = 1.28

docs_con_orfandad = 6
IDF(orfandad) = log(94/6) = 2.75  # Palabra MUY rara → ALTO peso

# TF-IDF final:
TF-IDF(feminicidio) = 0.125 × 1.28 = 0.16
TF-IDF(orfandad) = 0.125 × 2.75 = 0.34  # MAYOR peso (palabra mas rara)
TF-IDF(ninos) = 0.125 × 1.15 = 0.14
...

# VECTOR RESULTANTE (simplificado):
noticia_vector = [
    0.00,  # palabra1
    0.16,  # feminicidio
    0.00,  # palabra3
    0.34,  # orfandad
    0.14,  # ninos
    ...    # 2995 valores mas
]
```

### 9.6 Paso 5: Modelado de Topicos (LDA)

```python
# LDA analiza el vector y dice:
topic_distribution = lda.transform([noticia_vector])
# Resultado: [0.05, 0.02, 0.03, 0.10, 0.05, 0.75]
#             Top0  Top1  Top2  Top3  Top4  Top5

# Topico principal:
topic_id = 5  # Mayor probabilidad (75%)
topic_probability = 0.75

# Palabras del Topico 5:
topic_description = "feminicidio huerfanos ninos victimas"

# RESULTADO:
{
    'topic_id': 5,
    'topic_probability': 0.75,
    'topic_description': 'feminicidio huerfanos ninos victimas'
}
```

### 9.7 Paso 6: Clustering (DBSCAN)

```python
# DBSCAN busca vecinos cercanos:

# 1. Calcular distancia a todas las demas noticias:
distancia(noticia, otras[0]) = 0.75  # Muy lejos
distancia(noticia, otras[1]) = 0.68  # Muy lejos
distancia(noticia, otras[2]) = 0.55  # Cerca! (< eps=0.6)
distancia(noticia, otras[3]) = 0.82  # Muy lejos
...

# 2. Contar vecinos (distancia < 0.6):
vecinos = [otras[2]]  # Solo 1 vecino
num_vecinos = 1

# 3. Clasificar:
if num_vecinos >= min_samples (2):
    cluster = algun_cluster
else:
    cluster = -1  # OUTLIER

# RESULTADO:
{
    'cluster': -1  # Outlier (noticia unica)
}
```

### 9.8 Paso 7: Similitud

```python
# Calcular similitud con todas las noticias:
similarities = cosine_similarity(noticia_vector, todas_las_noticias)
# Resultado: [0.12, 0.08, 0.32, 0.05, 0.15, ...]

# Encontrar la mas similar:
most_similar_idx = 35  # Indice de noticia mas parecida
max_similarity = 0.32  # 32% similar

# RESULTADO:
{
    'most_similar_doc_idx': 35,
    'max_similarity': 0.32
}
```

### 9.9 Paso 8: Resultado Final en CSV

```csv
titulo,contenido,fuente,fecha,cluster,es_feminicidio,tiene_nna,tiene_huerfanos,es_objetivo,confianza,prioridad,topic_id,topic_probability,topic_description,most_similar_doc_idx,max_similarity
"Edomex otorga apoyo economico...","El gobierno del Estado...","Google News","2025-11-11T10:30:00+00:00",-1,True,True,True,True,0.80,ALTA,5,0.75,"feminicidio huerfanos ninos victimas",35,0.32
```

### 9.10 Visualizacion en Dashboard

```
┌─────────────────────────────────────────────────────────┐
│ NOTICIA #83                                    ALTA     │
├─────────────────────────────────────────────────────────┤
│ Titulo: Edomex otorga apoyo economico a ninos y        │
│         adolescentes en orfandad por feminicidio       │
│                                                          │
│ Fuente: Google News                                     │
│ Fecha: 11 de noviembre de 2025                         │
│                                                          │
│ ✅ Feminicidio: Si                                      │
│ ✅ NNA: Si                                              │
│ ✅ Huerfanos: Si                                        │
│                                                          │
│ Confianza: 80%                                          │
│ Prioridad: ALTA ⭐⭐⭐                                   │
│ Topico: feminicidio huerfanos ninos victimas           │
│ Cluster: -1 (outlier)                                   │
└─────────────────────────────────────────────────────────┘
```

---

## CONCLUSION

Este sistema combina:

1. **Web Scraping** → Recoleccion automatica
2. **Regex + Scoring** → Deteccion inteligente
3. **TF-IDF** → Representacion numerica
4. **LDA** → Descubrimiento de temas
5. **DBSCAN** → Agrupacion automatica
6. **Similitud** → Recomendaciones

Todo integrado en un **dashboard web** para visualizar y analizar noticias sobre feminicidios con NNA huerfanos en Mexico.

---

**Documentacion completa del proyecto:** https://github.com/hectormrales/TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s

**Contacto:** hector.morales@ejemplo.com
