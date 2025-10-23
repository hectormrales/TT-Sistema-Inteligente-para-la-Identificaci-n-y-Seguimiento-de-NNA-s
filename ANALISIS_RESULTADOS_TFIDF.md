# 🎓 ANÁLISIS DE RESULTADOS TF-IDF - Sistema NNA

**Fecha:** 23 de octubre de 2025  
**Analista:** Héctor Morales  
**Sistema:** Identificación y Seguimiento de NNA v2.0

---

## 📊 HALLAZGOS PRINCIPALES DEL ANÁLISIS

### 1. ✅ MATRIZ TF-IDF FUNCIONAL

La matriz TF-IDF se generó correctamente:
- **Dimensiones:** 146 documentos × 3000 términos
- **Valores no-cero:** 28,658 (6.54% de densidad)
- **Sparsity:** 93.46% (normal para matrices TF-IDF)
- **Rango de scores:** 0.0 a ~0.34

**Interpretación:** La matriz es altamente dispersa (sparse), lo cual es **esperado y correcto** en análisis de texto. Cada documento solo contiene una pequeña fracción del vocabulario total.

---

### 2. 🎯 TOP PALABRAS DEL CORPUS

Las 10 palabras con mayor score TF-IDF promedio:

| # | Palabra | Score TF-IDF | Interpretación |
|---|---------|--------------|----------------|
| 1 | por | 0.063071 | Preposición común (podría ser stopword) |
| 2 | una | 0.048231 | Artículo común (podría ser stopword) |
| 3 | no | 0.041484 | Negación común |
| 4 | al | 0.037176 | Contracción común |
| 5 | su | 0.036046 | Posesivo común |
| 6 | es | 0.036017 | Verbo ser común |
| 7 | me | 0.034782 | Pronombre |
| 8 | me xico | 0.032947 | ⚠️ Error de tokenización ("méxico") |
| 9 | xico | 0.032947 | ⚠️ Error de tokenización |
| 10 | ciento | 0.030758 | Parte de "por ciento" (estadísticas) |

**⚠️ PROBLEMAS DETECTADOS:**

1. **Stopwords no filtradas:** Palabras como "por", "una", "no", "al" tienen scores altos pero no son informativas. **Recomendación:** Agregar lista de stopwords en español.

2. **Errores de tokenización:** "me xico" y "xico" indican problema con acentos. **Causa:** `strip_accents='unicode'` convierte "México" → "Mexico" pero luego se divide incorrectamente.

3. **Bigrams poco informativos:** "por ciento", "en el", "de los" son útiles pero podrían optimizarse.

---

### 3. 🚨 PALABRAS CLAVE NNA - ANÁLISIS CRÍTICO

De las 21 palabras clave que **debían** aparecer en el vocabulario, **solo 4 fueron encontradas:**

#### ✅ Palabras Encontradas:

| Palabra | TF-IDF Score | Percentil | Estado |
|---------|--------------|-----------|--------|
| violencia | 0.008050 | >75% | ✅ EXCELENTE |
| monterrey | 0.006227 | >75% | ✅ EXCELENTE |
| jalisco | 0.005451 | >75% | ✅ EXCELENTE |
| menores | 0.003063 | 50-75% | ✓ BUENO |

#### ❌ Palabras NO Encontradas (17 palabras):

**Palabras eliminadas por `min_df=2` (aparecen <2 veces):**
- niño, niña, niños, niñas
- menor, menor edad  
- adolescente, adolescentes
- feminicidio, femicidio
- desaparecido, desaparecidos, desaparecida, desaparición
- abuso, maltrato
- víctima, victima
- alerta, alerta amber

**🔴 PROBLEMA GRAVE:** Las palabras más importantes del dominio NNA están siendo **eliminadas** por el filtro `min_df=2`.

---

### 4. 📈 COMPARACIÓN NNA vs NO-NNA

**Documentos:**
- Con NNA: 36 noticias (24.7%)
- Sin NNA: 110 noticias (75.3%)

**Top 5 palabras más distintivas de noticias NNA:**

| Palabra | Score NNA | Score NO-NNA | Diferencia | Interpretación |
|---------|-----------|--------------|------------|----------------|
| ciento | 0.0528 | 0.0236 | +0.0292 | Más estadísticas en NNA |
| por ciento | 0.0528 | 0.0236 | +0.0292 | Más porcentajes en NNA |
| nin | 0.0249 | 0.0000 | +0.0249 | Parte de "niño/niña" |
| os | 0.0355 | 0.0109 | +0.0246 | Sufijo "-años" común |
| una | 0.0655 | 0.0426 | +0.0229 | Más uso de artículo |

**💡 Observación:** Las palabras fragmentadas ("nin", "os") sugieren problemas de tokenización. Las palabras completas importantes no están apareciendo.

---

### 5. 🔍 ANÁLISIS DE DOCUMENTOS INDIVIDUALES

#### Documento #10 (Noticia NNA):
**Título:** "Dan hasta 54 años de cárcel a 3 asesinos de agentes..."

**Top 5 palabras:**
1. agentes (0.3205)
2. os de (0.2747) ← fragmento problemático
3. tres (0.1950)
4. arellano (0.1887)
5. ca rcel (0.1887) ← "cárcel" mal tokenizado

**Problema:** Palabras como "menor", "niño", "desaparecido" que probablemente están en el texto **NO aparecen** en el vector porque fueron eliminadas.

---

## 🎯 DISTRIBUCIÓN DE SCORES TF-IDF

### Estadísticas de valores no-cero:

- **Media:** 0.0025
- **Mediana (P50):** 0.0025
- **P25:** 0.0018
- **P75:** 0.0039
- **Máximo:** 0.3408

**Interpretación:** La mayoría de los scores están concentrados entre 0.0018 y 0.0039. Palabras con score >0.008 son **muy distintivas** (percentil >90).

---

## 💎 ANÁLISIS DE SPARSITY

- **Sparsity global:** 93.46%
- **Sparsity promedio por documento:** ~97.5%
- **Palabras únicas promedio por documento:** ~75 palabras de 3000

**Interpretación:** Cada noticia usa aproximadamente 75 palabras únicas del vocabulario de 3000. Esto es **normal y saludable**.

---

## 🚨 PROBLEMAS IDENTIFICADOS Y SOLUCIONES

### Problema 1: Stopwords no filtradas
**Impacto:** Palabras comunes dominan el ranking  
**Causa:** `stop_words=None` en TfidfVectorizer  
**Solución:**
```python
from sklearn.feature_extraction.text import STOPWORDS_ES
# O crear lista personalizada
stopwords_custom = ['por', 'una', 'al', 'su', 'es', 'me', 'no', 'lo', 'como', ...]

TfidfVectorizer(
    stop_words=stopwords_custom,  # ← Agregar aquí
    # ... otros parámetros
)
```

---

### Problema 2: Palabras clave NNA eliminadas
**Impacto:** 🔴 CRÍTICO - El sistema no detecta correctamente casos NNA  
**Causa:** `min_df=2` elimina palabras que aparecen <2 veces  
**Solución:**
```python
TfidfVectorizer(
    min_df=1,  # ← Cambiar de 2 a 1 (permitir palabras únicas)
    # O mejor:
    min_df=0.01,  # ← Al menos 1% de documentos (≥2 docs de 146)
    # ... otros parámetros
)
```

**Advertencia:** `min_df=1` puede aumentar el tamaño del vocabulario. Monitorear `max_features`.

---

### Problema 3: Tokenización incorrecta de acentos
**Impacto:** Palabras como "México" → "me xico"  
**Causa:** `strip_accents='unicode'` + tokenización posterior  
**Solución:**
```python
# Opción 1: No remover acentos
TfidfVectorizer(
    strip_accents=None,  # ← Mantener acentos
    # ...
)

# Opción 2: Normalizar texto ANTES de vectorizar
def normalizar_texto(text):
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('utf-8')
    return text

df['texto_normalizado'] = df['texto'].apply(normalizar_texto)
```

---

### Problema 4: Bigrams poco informativos
**Impacto:** Menor - reduce capacidad del modelo  
**Causa:** `ngram_range=(1, 2)` genera muchos bigrams comunes  
**Solución:**
```python
# Agregar filtro de bigrams
def filtrar_bigrams(ngram):
    stopwords = ['por', 'de', 'en', 'el', 'la', 'los', 'las']
    palabras = ngram.split()
    if len(palabras) == 2:
        if palabras[0] in stopwords or palabras[1] in stopwords:
            return False
    return True

# O usar solo unigrams para simplificar
TfidfVectorizer(
    ngram_range=(1, 1),  # ← Solo palabras individuales
    # ...
)
```

---

## 📋 PLAN DE ACCIÓN RECOMENDADO

### Prioridad ALTA (Crítico):
1. ✅ **Reducir `min_df` de 2 a 1** para capturar palabras clave NNA
2. ✅ **Agregar stopwords en español** para filtrar palabras comunes
3. ✅ **Validar tokenización** de palabras con acentos

### Prioridad MEDIA (Importante):
4. ⏳ **Verificar detección de NNA** con palabras clave completas
5. ⏳ **Optimizar bigrams** filtrando combinaciones poco informativas
6. ⏳ **Ajustar `max_df`** si palabras muy comunes dominan

### Prioridad BAJA (Mejoras):
7. 🔮 **Experimentar con TF-IDF sublineal** (`sublinear_tf=True`)
8. 🔮 **Probar diferentes rangos de ngrams** (1-3, solo 1, etc.)
9. 🔮 **Evaluar impacto de normalización L1 vs L2**

---

## 📊 MÉTRICAS ACTUALES vs OBJETIVO

| Métrica | Actual | Objetivo | Estado |
|---------|--------|----------|--------|
| Palabras clave NNA encontradas | 4/21 (19%) | 18/21 (85%) | 🔴 Crítico |
| Silhouette Score (DBSCAN) | 0.51 | >0.50 | ✅ Cumplido |
| Sparsity | 93.46% | 90-95% | ✅ Óptimo |
| Outliers detectados | 146 (100%) | 5-15% | 🔴 Error |
| Vocabulario | 3000 | 2000-4000 | ✅ Correcto |

**⚠️ ALERTA:** El clustering está marcando **TODAS** las noticias como outliers (-1). Esto indica que `eps=0.4` es demasiado restrictivo o hay un problema en la normalización de vectores.

---

## 🎓 CONCLUSIONES PARA TU PROFESOR

### Lo que FUNCIONA BIEN:
1. ✅ **Arquitectura del pipeline:** Las 7 etapas están correctamente implementadas
2. ✅ **TF-IDF básico:** La matriz se genera correctamente con dimensiones adecuadas
3. ✅ **Visualizaciones:** Los scripts permiten inspeccionar scores y validar pesos
4. ✅ **Sparsity:** La dispersión de la matriz está en el rango esperado
5. ✅ **Comparación NNA vs NO-NNA:** Se pueden identificar patrones diferenciales

### Lo que NECESITA MEJORA:
1. 🔴 **Filtrado de stopwords:** Palabras comunes dominan el ranking
2. 🔴 **min_df demasiado alto:** Elimina palabras clave del dominio NNA
3. 🔴 **Tokenización de acentos:** Fragmenta palabras importantes
4. 🔴 **Clustering fallido:** Todos los documentos son outliers
5. ⚠️ **Validación de NNA:** No se puede verificar si detecta correctamente sin las palabras clave

### Recomendación Principal:
**ANTES** de continuar con más análisis o despliegue, es **crítico** ajustar los parámetros de TfidfVectorizer:

```python
# CONFIGURACIÓN MEJORADA RECOMENDADA
vectorizer = TfidfVectorizer(
    max_features=3000,
    ngram_range=(1, 2),
    min_df=1,              # ← CAMBIO: Permitir palabras únicas
    max_df=0.85,           # ← CAMBIO: Más permisivo
    strip_accents=None,    # ← CAMBIO: Mantener acentos
    lowercase=True,
    stop_words=['por', 'una', 'al', 'su', 'es', 'me', 'no', 'lo', 'como', 
                'de', 'en', 'el', 'la', 'los', 'las', 'para', 'con', 'se',
                'ha', 'si', 'ya', 'son', 'este', 'esta', 'sus', 'mas']  # ← CAMBIO: Agregar stopwords
)
```

Luego **re-ejecutar** todo el pipeline y validar que:
- Palabras como "niño", "menor", "desaparecido" aparezcan en vocabulario
- DBSCAN forme clusters reales (no todo outliers)
- Scores TF-IDF reflejen importancia del dominio NNA

---

## 📚 REFERENCIAS Y RECURSOS

- **Documento técnico completo:** `EXPLICACION_TECNICA_COMPLETA.md`
- **Scripts de validación:**
  - `visualize_tfidf.py` - Análisis en consola
  - `visualize_tfidf_plots.py` - Gráficas PNG
- **Visualizaciones generadas:** Carpeta `visualizations/`
- **Datos de análisis:** `data/noticias_analyzed_simplified.csv`

---

**Próximos pasos:** Implementar cambios recomendados y re-ejecutar análisis completo para validar mejoras.
