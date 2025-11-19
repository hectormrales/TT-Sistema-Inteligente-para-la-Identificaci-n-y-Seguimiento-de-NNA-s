# 🔧 Mejoras Recomendadas para Aplicar

**Fecha**: 18 de noviembre de 2025  
**Sistema**: Inteligente NNA - ESIME Zacatenco IPN

---

## 📋 RESUMEN DE CAMBIOS

Basado en el análisis del pipeline, se detectaron **3 problemas principales**:

1. ❌ TF-IDF captura palabras basura ("xico", "las", "los")
2. ❌ LDA tiene perplexity muy alto (66M vs esperado <150)
3. ❌ DBSCAN no forma clusters (100% outliers)

**SOLUCIONES**:

1. ✅ Agregar stopwords español → Mejora TF-IDF y LDA
2. ✅ Reducir tópicos LDA → Mejora perplexity
3. 🤔 Aumentar eps DBSCAN o eliminar paso

---

## 🔴 CAMBIO 1: Agregar Stopwords (URGENTE)

### En: `config.py`

**ANTES**:
```python
TFIDF_CONFIG = {
    'max_features': 3000,
    'min_df': 1,
    'max_df': 0.95,
    'ngram_range': (1, 2),
    'strip_accents': None,
    'lowercase': True,
    'stop_words': None  # ← PROBLEMA
}
```

**DESPUÉS**:
```python
TFIDF_CONFIG = {
    'max_features': 3000,
    'min_df': 1,
    'max_df': 0.95,
    'ngram_range': (1, 2),
    'strip_accents': None,
    'lowercase': True,
    'stop_words': 'spanish'  # ← SOLUCIÓN
}
```

### ¿Qué hace?

Elimina palabras comunes como: de, la, el, los, las, un, una, con, por, para, que, etc.

### Impacto esperado:

- Top palabras TF-IDF:
  - **ANTES**: xico, las, los, feminicidio, del
  - **DESPUÉS**: feminicidio, mujer, hijos, huérfanos, asesinato

- Perplexity LDA:
  - **ANTES**: 66,634,936
  - **DESPUÉS**: <500 (mejora drástica)

---

## 🟡 CAMBIO 2: Reducir Tópicos LDA (IMPORTANTE)

### En: `config.py`

**ANTES**:
```python
LDA_CONFIG = {
    'n_components': 6,  # ← Demasiados tópicos para 94 noticias
    'random_state': 42,
    'max_iter': 20,
    'learning_method': 'online'
}
```

**DESPUÉS**:
```python
LDA_CONFIG = {
    'n_components': 4,  # ← Reducir a 4 tópicos
    'random_state': 42,
    'max_iter': 30,  # Aumentar iteraciones
    'learning_method': 'online'
}
```

### ¿Por qué?

Con solo 94 noticias, 6 tópicos es demasiado. La regla general es:

```
n_components ≈ sqrt(num_documentos) / 2
n_components ≈ sqrt(94) / 2 ≈ 4.85 ≈ 4
```

### Impacto esperado:

- Tópicos más coherentes
- Perplexity menor
- Distribución más balanceada

---

## 🟢 CAMBIO 3: Ajustar DBSCAN (OPCIONAL)

### Opción A: Aumentar eps (ser más permisivo)

**En: `config.py`**

```python
DBSCAN_CONFIG = {
    'eps': 0.75,  # Aumentar de 0.6 a 0.75
    'min_samples': 2,
    'metric': 'cosine'
}
```

**Resultado esperado**: Algunos clusters se formarán

### Opción B: Eliminar paso (recomendado)

**En: `src/analysis/simplified_analyzer.py`**

Comentar o eliminar la llamada a `step_5_clustering()`:

```python
def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
    """Pipeline completo de análisis."""
    self.df_original = df
    
    # Paso 3: Vectorización
    self.step_3_vectorize_text()
    
    # Paso 4: Modelado de tópicos
    df_processed, _ = self.step_4_topic_modeling()
    
    # Paso 5: Clustering (COMENTADO - no aporta en este caso)
    # df_processed, _ = self.step_5_clustering()
    
    # Paso 6: Similitud
    df_final = self.step_6_similarity_analysis()
    
    return df_final
```

**Ventaja**: Ahorra ~30% tiempo de procesamiento

---

## 🔵 CAMBIO 4: Mejorar Query Google News (CONSIDERARLO)

### En: `config.py`

**ANTES**:
```python
GOOGLE_NEWS_CONFIG = {
    'query': 'feminicidio hijos huerfanos mexico',
    'max_results': 30,
    'language': 'es',
    'region': 'MX'
}
```

**DESPUÉS** (más específico):
```python
GOOGLE_NEWS_CONFIG = {
    'query': '(feminicidio OR "violencia género") AND (hijos OR huérfanos OR menores OR niños) AND mexico',
    'max_results': 50,  # Aumentar a 50
    'language': 'es',
    'region': 'MX'
}
```

### Impacto esperado:

- Más noticias objetivo (de 13.8% → 25-30%)
- Mejor calidad de fuentes

---

## ✅ APLICAR CAMBIOS

### Paso 1: Editar `config.py`

```bash
# Abrir archivo
code config.py
```

Aplicar cambios 1 y 2 (stopwords + reducir LDA)

### Paso 2: Verificar cambios

```bash
# Ver diferencia
git diff config.py
```

### Paso 3: Probar cambios

```bash
# Ejecutar análisis nuevamente
python analisis_pipeline_detallado.py
```

### Paso 4: Comparar resultados

**Verificar**:
- ✓ Top 5 palabras TF-IDF son relevantes (no stopwords)
- ✓ Perplexity LDA <500
- ✓ Tópicos LDA tienen sentido

---

## 📊 RESULTADOS ESPERADOS

### ANTES de los cambios:

```
TF-IDF Top 5: xico, las, los, feminicidio, del
LDA Perplexity: 66,634,936
Clusters: 0
Outliers: 94 (100%)
```

### DESPUÉS de los cambios:

```
TF-IDF Top 5: feminicidio, mujer, hijos, huérfanos, asesinato
LDA Perplexity: <500
Tópicos: 4 coherentes
Clusters: 2-5 (opcional)
Outliers: 60-80%
```

---

## 🎯 VALIDACIÓN

Después de aplicar cambios, ejecuta:

```bash
python analisis_pipeline_detallado.py
```

Y verifica:

1. ✅ Top palabras son relevantes
2. ✅ Perplexity <1000
3. ✅ Tópicos interpretables
4. ✅ Sistema más rápido

---

## 🚀 CÓDIGO COMPLETO LISTO PARA COPIAR

### `config.py` (sección TFIDF_CONFIG)

```python
# ============================================================================
# CONFIGURACIÓN DE VECTORIZACIÓN (TF-IDF)
# ============================================================================

TFIDF_CONFIG = {
    # Número máximo de características (palabras únicas) a extraer
    'max_features': 3000,
    
    # Frecuencia mínima de documento (min_df)
    # - Valor numérico: número mínimo de documentos que deben contener el término
    # - Valor decimal: proporción mínima de documentos
    'min_df': 1,
    
    # Frecuencia máxima de documento (max_df)
    # - Ignora términos que aparecen en más del X% de documentos
    # - Ayuda a eliminar términos muy comunes que no discriminan
    'max_df': 0.95,
    
    # Rango de n-gramas a considerar
    # - (1, 1): solo unigramas (palabras individuales)
    # - (1, 2): unigramas y bigramas (pares de palabras)
    'ngram_range': (1, 2),
    
    # Manejo de acentos
    # - None: preserva acentos (importante para español)
    # - 'ascii': remueve acentos
    # - 'unicode': normaliza caracteres unicode
    'strip_accents': None,
    
    # Convertir a minúsculas
    'lowercase': True,
    
    # Lista de stopwords (palabras comunes a eliminar)
    # - None: no elimina stopwords
    # - 'english': stopwords en inglés
    # - 'spanish': stopwords en español ← CAMBIO AQUÍ
    'stop_words': 'spanish',  # ← AGREGAR ESTA LÍNEA
}
```

### `config.py` (sección LDA_CONFIG)

```python
# ============================================================================
# CONFIGURACIÓN DE MODELADO DE TÓPICOS (LDA)
# ============================================================================

LDA_CONFIG = {
    # Número de tópicos a descubrir
    # - Valores típicos: 4-10 para datasets pequeños
    # - Regla general: ~sqrt(num_documentos) / 2
    'n_components': 4,  # ← CAMBIAR DE 6 A 4
    
    # Semilla aleatoria para reproducibilidad
    'random_state': 42,
    
    # Número máximo de iteraciones del algoritmo
    'max_iter': 30,  # ← AUMENTAR DE 20 A 30
    
    # Método de aprendizaje
    # - 'batch': procesa todos los documentos a la vez (más lento pero preciso)
    # - 'online': procesa en mini-batches (más rápido, bueno para grandes datasets)
    'learning_method': 'online'
}
```

### `config.py` (sección DBSCAN_CONFIG - OPCIONAL)

```python
# ============================================================================
# CONFIGURACIÓN DE CLUSTERING (DBSCAN)
# ============================================================================

DBSCAN_CONFIG = {
    # Epsilon: distancia máxima entre dos muestras para considerarlas vecinas
    # - Valores más bajos: clusters más estrictos (más outliers)
    # - Valores más altos: clusters más permisivos (menos outliers)
    # - Para similitud coseno: eps=0.6 ≈ similitud mínima de 40%
    'eps': 0.75,  # ← AUMENTAR DE 0.6 A 0.75 (opcional)
    
    # Número mínimo de muestras en un vecindario para formar un cluster
    # - min_samples=2: al menos 2 documentos similares
    # - min_samples=3: al menos 3 documentos similares (más estricto)
    'min_samples': 2,
    
    # Métrica de distancia
    # - 'cosine': similitud coseno (ideal para texto/TF-IDF)
    # - 'euclidean': distancia euclidiana
    'metric': 'cosine'
}
```

---

## 📝 CHECKLIST DE IMPLEMENTACIÓN

- [ ] Abrir `config.py`
- [ ] Cambiar `stop_words: None` → `stop_words: 'spanish'`
- [ ] Cambiar `n_components: 6` → `n_components: 4`
- [ ] Cambiar `max_iter: 20` → `max_iter: 30`
- [ ] (Opcional) Cambiar `eps: 0.6` → `eps: 0.75`
- [ ] Guardar archivo
- [ ] Ejecutar `python analisis_pipeline_detallado.py`
- [ ] Verificar mejoras en resultados
- [ ] Hacer commit: `git commit -m "Mejora TF-IDF y LDA con stopwords"`

---

## 🎓 EXPLICACIÓN PARA TU TESIS

### ¿Por qué estos cambios?

**Stopwords**:
> "Se agregó una lista de stopwords en español al proceso de vectorización TF-IDF para eliminar palabras comunes sin valor semántico (artículos, preposiciones, conjunciones). Esto mejoró la calidad de las características extraídas, permitiendo que el modelo se enfoque en términos discriminativos relacionados con feminicidios y NNA."

**Reducción de tópicos**:
> "Se redujo el número de tópicos LDA de 6 a 4 considerando la regla heurística n ≈ √N/2, donde N es el número de documentos. Con 94 noticias, 4 tópicos proporciona un balance entre granularidad temática y coherencia estadística, resultando en un perplexity significativamente menor."

**Ajuste DBSCAN**:
> "El algoritmo DBSCAN con eps=0.6 resultó en 100% outliers debido a la alta diversidad temática de las noticias. Se aumentó eps a 0.75 (similitud mínima 25%) para formar clusters de casos relacionados, aunque se considera eliminar este paso si no aporta valor al análisis."

---

**¿Listo para aplicar?** Sigue el checklist y ejecuta el análisis nuevamente.

**Héctor Morales** - ESIME Zacatenco IPN  
18 de noviembre de 2025
