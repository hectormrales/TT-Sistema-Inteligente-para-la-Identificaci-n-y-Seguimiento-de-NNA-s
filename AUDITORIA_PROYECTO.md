# 🔍 AUDITORÍA COMPLETA DEL PROYECTO NNA

**Fecha:** 11 de noviembre de 2025  
**Proyecto:** Sistema Inteligente para Identificación y Seguimiento de NNA  
**Objetivo Principal:** Detectar noticias sobre **víctimas indirectas** (NNA huérfanos) de feminicidios

---

## ⚠️ ANÁLISIS CRÍTICO: ¿CUMPLE EL OBJETIVO?

### 🎯 Objetivo Declarado vs Implementación Real

| Aspecto | Lo Que DEBE Hacer | Lo Que REALMENTE Hace | ✅/❌ |
|---------|-------------------|----------------------|------|
| **Enfoque principal** | Víctimas indirectas (NNA huérfanos de feminicidios) | Detecta CUALQUIER mención de NNA (genérico) | ❌ |
| **Tipo de noticias** | Feminicidios con NNA afectados | Noticias generales (política, economía, todo) | ❌ |
| **Detección específica** | Palabras como "huérfanos", "madre asesinada", "feminicidio" + "hijos" | Solo busca palabras genéricas de NNA | ⚠️ |
| **Feeds RSS** | Medios especializados en seguridad/género | Medios GENERALES (política, economía, etc.) | ❌ |

### 🔴 PROBLEMA PRINCIPAL: DESALINEACIÓN DE OBJETIVOS

**Tu sistema actualmente:**
1. ✅ Recolecta noticias de medios mexicanos
2. ✅ Aplica TF-IDF correctamente
3. ✅ Hace clustering con DBSCAN
4. ✅ Identifica tópicos con LDA
5. ❌ **NO se enfoca en feminicidios**
6. ❌ **NO detecta específicamente víctimas indirectas**
7. ❌ **NO busca relación madre asesinada → NNA huérfanos**

**Lo que recolecta realmente:**
- Noticias de **política** (La Jornada, Proceso)
- Noticias de **economía** (Forbes, El Financiero)
- Noticias **generales** (Animal Político, Aristegui)
- **Muy pocas** sobre feminicidios o NNA huérfanos

---

## 📊 RESULTADOS ACTUALES (DIAGNÓSTICO)

### Ejecución más reciente (23 octubre 2025):

```
📰 Total noticias: 146
👶 Casos NNA: 36 (24.7%)
🏷️  Clusters: 0 (todo marcado como outliers)
🎯 Tópicos descubiertos:
   - Tópico 0: dong dong zhang zhi dong zhi zhang
   - Tópico 1: villalpando penal juicio de jalisco joven
   - Tópico 2: un pai puntos escuderi hacia la guardia
   - Tópico 3: por no una es al
   - Tópico 4: produccio la estrategia en otro reality
   - Tópico 5: portafolio fibra mty fibra mty venta
```

**Interpretación:**
- ❌ **Tópicos irrelevantes:** "dong zhang", "reality", "portafolio" → No relacionados con feminicidios
- ❌ **Clustering falló:** 146/146 outliers → DBSCAN no encontró similitudes
- ⚠️ **36 casos NNA:** Pero ¿cuántos son huérfanos de feminicidios? **Desconocido**

---

## 🔬 ANÁLISIS TÉCNICO DETALLADO

### ✅ LO QUE SÍ FUNCIONA BIEN

#### 1. **Arquitectura del Pipeline** ✅
- 7 etapas bien definidas
- Código modular y organizado
- Docker funcionando correctamente

#### 2. **TF-IDF Vectorización** ✅
```python
TfidfVectorizer(
    max_features=3000,      # ✅ Correcto
    ngram_range=(1, 2),     # ✅ Correcto (uni+bigrams)
    min_df=2,               # ⚠️ Ver nota abajo
    max_df=0.8,             # ✅ Correcto
    strip_accents='unicode' # ⚠️ Causa errores (me xico)
)
```

**Resultado:** Matriz 146×3000 correctamente generada

#### 3. **LDA Topic Modeling** ✅ (Técnicamente)
```python
LatentDirichletAllocation(
    n_components=6,          # ✅ 6 tópicos
    max_iter=20,             # ✅ Suficiente
    learning_method='online' # ✅ Rápido
)
```

**Problema:** Tópicos inútiles porque las noticias son **irrelevantes** al tema

#### 4. **DBSCAN Clustering** ✅ (Implementación)
```python
DBSCAN(
    eps=0.4,           # ⚠️ Muy restrictivo
    min_samples=3,     # ✅ Correcto
    metric='cosine'    # ✅ Correcto
)
```

**Problema:** eps=0.4 marca TODO como outliers → No hay clusters

#### 5. **Similitud Coseno** ✅
- Matriz 146×146 correctamente calculada
- 22 pares con similitud >0.5
- Implementación correcta

---

### ❌ LO QUE NO FUNCIONA / ESTÁ MAL ENFOCADO

#### 1. **FEEDS RSS INCORRECTOS** 🔴 CRÍTICO

**Feeds actuales:**
```python
RSS_FEEDS = [
    'https://www.jornada.com.mx/rss/politica.xml',      # POLÍTICA
    'https://www.proceso.com.mx/feed',                  # GENERAL
    'https://aristeguinoticias.com/feed/',              # GENERAL
    'https://www.animalpolitico.com/feed/',             # POLÍTICA
    'https://www.sinembargo.mx/feed/',                  # GENERAL
    'https://www.forbes.com.mx/feed/',                  # ECONOMÍA
    'https://www.elsoldemexico.com.mx/rss.xml',         # GENERAL
    'https://www.elfinanciero.com.mx/rss/',             # FINANZAS
]
```

**Problema:** Ninguno se especializa en **feminicidios** o **seguridad**

**Feeds que DEBERÍAS usar:**
```python
RSS_FEEDS_FEMINICIDIOS = [
    # Secciones específicas de seguridad/género
    'https://www.jornada.com.mx/rss/seguridad.xml',     # ✅ Seguridad
    'https://www.proceso.com.mx/seccion/seguridad',     # ✅ Seguridad
    'https://www.animalpolitico.com/genero',            # ✅ Género
    'https://aristeguinoticias.com/categoria/genero/',  # ✅ Género
    
    # Medios especializados en género
    'https://www.semmexico.mx/feed/',                   # ✅ Periodismo feminista
    'https://cimacnoticias.com.mx/feed/',               # ✅ Agencia especializada en género
    'https://www.luchadoras.mx/feed/',                  # ✅ Colectivo feminista
    
    # Secciones de estados con más feminicidios
    'https://www.elsoldetoluca.com.mx/rss/local.xml',   # ✅ Estado de México
    'https://www.milenio.com/estados/estado-de-mexico', # ✅ Edomex
    'https://www.jornada.com.mx/rss/estados.xml',       # ✅ Estados
]
```

#### 2. **DETECCIÓN DE NNA MUY GENÉRICA** 🔴 CRÍTICO

**Código actual:**
```python
def detect_children_mentions(text):
    keywords = [
        r'\bhij[oa]s?\b',           # hijo, hija, hijos, hijas
        r'\bmenor(?:es)?\b',        # menor, menores
        r'\bniñ?[oa]s?\b',          # niño, niña
        r'\badolescentes?\b',       # adolescente
        r'\bhu(erf|erf)an[oa]s?\b', # huérfano ✅ BIEN
        # ...
    ]
```

**Problema:** Detecta **CUALQUIER** mención de NNA, no específicamente **huérfanos de feminicidios**

**Ejemplos de falsos positivos actuales:**
- "Niños regresan a clases" ❌
- "Menor gana premio de matemáticas" ❌
- "Adolescentes participan en deportes" ❌
- "Hijos de político asisten a evento" ❌

**Lo que DEBE detectar:**
- "Tres hijos quedan huérfanos tras feminicidio" ✅
- "Niños en custodia tras asesinato de su madre" ✅
- "Menores víctimas indirectas de feminicidio" ✅

#### 3. **NO HAY DETECCIÓN DE FEMINICIDIOS** 🔴 CRÍTICO

**Código actual:** NO EXISTE función `detect_feminicide()`

**Lo que necesitas:**
```python
def detect_feminicide_with_orphans(text):
    """
    Detecta si la noticia menciona:
    1. Feminicidio/asesinato de mujer
    2. NNA afectados (hijos, huérfanos)
    """
    # Paso 1: ¿Menciona feminicidio?
    feminicide_patterns = [
        r'\bfeminicidio[s]?\b',
        r'\bfemicidio[s]?\b',
        r'\bmujer\s+(asesinada|asesinato|homicidio|muerte)',
        r'\basesinat[oa]\s+.*\s+mujer',
        r'\bmadre\s+(asesinada|muerta)',
    ]
    
    # Paso 2: ¿Menciona NNA huérfanos?
    orphan_patterns = [
        r'\bhu[eé]rfan[oa]s?\b',
        r'\bhij[oa]s?\s+quedan',
        r'\bhij[oa]s?\s+(desamparad|abandon|sin\s+madre)',
        r'\bmenor[es]?\s+(quedan|víctima|afectad)',
        r'\bniñ[oa]s?\s+(quedan|víctima|afectad)',
        r'\bvíctima[s]?\s+indirecta[s]?',
    ]
    
    # Debe cumplir AMBOS criterios
    has_feminicide = any(re.search(p, text, re.I) for p in feminicide_patterns)
    has_orphans = any(re.search(p, text, re.I) for p in orphan_patterns)
    
    return has_feminicide and has_orphans
```

#### 4. **DICCIONARIO DE SINÓNIMOS EXISTE PERO NO SE USA CORRECTAMENTE**

**Diccionario actual:**
```python
# ✅ BIEN: Incluye términos correctos
orphan_terms = [
    "huérfanos", "huérfanas", "orfandad",
    "víctimas indirectas", "hijos de víctimas"
]

feminicide_terms = [
    "feminicidio", "femicidio", "asesinato de mujer",
    "violencia feminicida"
]
```

**Problema:** Se carga pero **NO se integra** en la detección primaria

#### 5. **PARÁMETROS TF-IDF ELIMINAN PALABRAS CLAVE** ⚠️

**Análisis de visualización mostró:**
```
Palabras clave NO encontradas (eliminadas por min_df=2):
- feminicidio ❌
- femicidio ❌
- huérfanos ❌
- víctima ❌
- menor edad ❌
```

**Causa:** `min_df=2` elimina palabras que aparecen <2 veces

**Problema:** Si solo hay 1-2 noticias de feminicidios, las palabras clave se pierden

#### 6. **CLUSTERING DBSCAN FALLA** ⚠️

**Resultado actual:**
```
🎯 Clusters detectados: 0
🔍 Outliers: 146/146 (100%)
```

**Causa:** `eps=0.4` (40% similitud) es demasiado restrictivo

**Por qué:** Noticias de temas variados (política, economía, deportes) no son similares entre sí

---

## 📋 PLAN DE DEPURACIÓN Y CORRECCIÓN

### 🔴 PRIORIDAD CRÍTICA (Debe hacerse YA)

#### 1. **Cambiar Feeds RSS a fuentes especializadas**

**Acción:** Modificar `config.py`

```python
# ANTES (INCORRECTO)
RSS_FEEDS = [
    'https://www.jornada.com.mx/rss/politica.xml',  # ❌
    'https://www.forbes.com.mx/feed/',              # ❌
]

# DESPUÉS (CORRECTO)
RSS_FEEDS = [
    # Secciones de seguridad/género de medios nacionales
    'https://www.jornada.com.mx/rss/seguridad.xml',
    'https://www.animalpolitico.com/genero',
    
    # Medios especializados en género
    'https://cimacnoticias.com.mx/feed/',           # ✅ CIMAC (especializado género)
    'https://www.semmexico.mx/feed/',               # ✅ SEM México
    
    # Alertas de género de estados con más feminicidios
    'https://www.elsoldetoluca.com.mx/rss/local.xml',  # Edomex
    'https://aristeguinoticias.com/categoria/mexico/',  # Nacional
]
```

#### 2. **Implementar detección específica de feminicidios con NNA**

**Acción:** Crear `src/collection/feminicide_detector.py`

```python
import re
from typing import Dict

def detect_feminicide_news(text: str) -> Dict[str, bool]:
    """
    Detecta si una noticia trata sobre feminicidio con víctimas indirectas NNA.
    
    Returns:
        {
            'is_feminicide': bool,
            'has_children': bool,
            'has_orphans': bool,
            'is_target_news': bool  # feminicidio + NNA
        }
    """
    text_lower = text.lower()
    
    # Patrones de feminicidio
    feminicide_indicators = [
        r'\bfeminicidio[s]?\b',
        r'\bfemicidio[s]?\b',
        r'\bmujer\s+(asesinada|hallada\s+muerta|encontrada\s+sin\s+vida)',
        r'\basesinat[oa]\s+.*\s+(mujer|femenina)',
        r'\bmadre\s+(asesinada|muerta|fallecida)\s+(por|en)',
        r'\bhomicidio\s+de\s+mujer',
        r'\bviolencia\s+feminicida',
        r'\bcrimen\s+de\s+g[ée]nero',
    ]
    
    # Patrones de NNA/hijos
    children_indicators = [
        r'\bhij[oa]s?\b',
        r'\bmenor[es]?\b',
        r'\bniñ[oa]s?\b',
        r'\badolescente[s]?\b',
        r'\bbeb[ée][s]?\b',
        r'\binf antes?\b',
    ]
    
    # Patrones de orfandad/víctimas indirectas
    orphan_indicators = [
        r'\bhu[ée]rfan[oa]s?\b',
        r'\bhij[oa]s?\s+(quedan|quedaron)',
        r'\bmenor[es]?\s+(quedan|quedaron)',
        r'\bv[íi]ctima[s]?\s+indirecta[s]?\b',
        r'\bsin\s+(madre|mam[áa])',
        r'\bdesamparad[oa]s?\b',
        r'\babandonad[oa]s?\b',
        r'\bcustodia\s+de',
        r'\bal\s+cuidado\s+de',
    ]
    
    # Detectar cada categoría
    is_feminicide = any(re.search(p, text_lower) for p in feminicide_indicators)
    has_children = any(re.search(p, text_lower) for p in children_indicators)
    has_orphans = any(re.search(p, text_lower) for p in orphan_indicators)
    
    # Noticia objetivo: feminicidio + (hijos O huérfanos)
    is_target = is_feminicide and (has_children or has_orphans)
    
    return {
        'is_feminicide': is_feminicide,
        'has_children': has_children,
        'has_orphans': has_orphans,
        'is_target_news': is_target,
        'confidence': calculate_confidence(text_lower, is_feminicide, has_children, has_orphans)
    }

def calculate_confidence(text: str, is_fem: bool, has_child: bool, has_orph: bool) -> float:
    """Calcula nivel de confianza de la detección."""
    score = 0.0
    
    if is_fem:
        score += 0.4
        # Bonus si menciona múltiples indicadores
        if 'feminicidio' in text and 'asesinada' in text:
            score += 0.1
    
    if has_child:
        score += 0.2
    
    if has_orph:
        score += 0.3  # Mayor peso a huérfanos
        if 'víctimas indirectas' in text:
            score += 0.1
    
    return min(score, 1.0)
```

#### 3. **Integrar detección en data_collector.py**

**Acción:** Modificar `collect_news_from_rss()`

```python
from src.collection.feminicide_detector import detect_feminicide_news

def collect_news_from_rss(rss_url):
    # ... código existente ...
    
    for item in soup.find_all('item'):
        # ... extraer título, contenido ...
        
        # NUEVO: Detectar feminicidios con NNA
        full_text = f"{title.text} {desc_text}"
        detection_result = detect_feminicide_news(full_text)
        
        articles.append({
            'titulo': title.text.strip(),
            'contenido': desc_text,
            'enlace': link.text.strip(),
            'fuente': rss_url,
            'fecha': dt.isoformat(),
            
            # NUEVO: Campos específicos
            'es_feminicidio': 'Si' if detection_result['is_feminicide'] else 'No',
            'tiene_nna': 'Si' if detection_result['has_children'] else 'No',
            'tiene_huerfanos': 'Si' if detection_result['has_orphans'] else 'No',
            'es_objetivo': 'Si' if detection_result['is_target_news'] else 'No',
            'confianza': detection_result['confidence'],
            
            # Campos existentes
            'cluster': 0,
            'menores_identificados': 'Si' if detection_result['has_children'] else 'No'
        })
```

#### 4. **Ajustar parámetros TF-IDF**

**Acción:** Modificar `simplified_analyzer.py`

```python
# ANTES
TfidfVectorizer(
    max_features=3000,
    ngram_range=(1, 2),
    min_df=2,              # ❌ Elimina palabras clave
    max_df=0.8,
    strip_accents='unicode', # ❌ Causa errores
)

# DESPUÉS
TfidfVectorizer(
    max_features=3000,
    ngram_range=(1, 2),
    min_df=1,              # ✅ Permitir palabras únicas
    max_df=0.85,           # ✅ Más permisivo
    strip_accents=None,    # ✅ Mantener acentos
    lowercase=True,
    
    # NUEVO: Agregar stopwords en español
    stop_words=['de', 'la', 'el', 'en', 'y', 'a', 'los', 'las', 
                'por', 'con', 'para', 'del', 'al', 'se', 'un', 'una',
                'es', 'su', 'no', 'ha', 'son', 'me', 'lo', 'si']
)
```

#### 5. **Recalibrar DBSCAN**

**Acción:** Ajustar `eps` en `simplified_analyzer.py`

```python
# ANTES
DBSCAN(
    eps=0.4,          # ❌ Muy restrictivo
    min_samples=3,
    metric='cosine'
)

# DESPUÉS
DBSCAN(
    eps=0.6,          # ✅ Más permisivo (40% similitud)
    min_samples=2,    # ✅ Reducir mínimo
    metric='cosine'
)
```

---

### ⚠️ PRIORIDAD ALTA (Importante)

#### 6. **Agregar filtro post-recolección**

**Acción:** Crear función de filtrado

```python
def filter_target_news(df):
    """
    Filtra solo noticias objetivo: feminicidios con NNA.
    """
    # Opción 1: Solo noticias objetivo
    target_df = df[df['es_objetivo'] == 'Si'].copy()
    
    # Opción 2: Feminicidios + NNA (más permisivo)
    relevant_df = df[
        (df['es_feminicidio'] == 'Si') | 
        (df['tiene_huerfanos'] == 'Si')
    ].copy()
    
    return target_df  # O relevant_df según necesidad
```

#### 7. **Actualizar README.md con objetivo claro**

**Acción:** Reescribir descripción

```markdown
## 🎯 Objetivo del Proyecto

Sistema automatizado para detectar y analizar noticias sobre **víctimas indirectas de feminicidios**: 
Niños, Niñas y Adolescentes (NNA) que quedan huérfanos tras el asesinato de sus madres.

### Casos Objetivo

✅ "Feminicidio deja tres hijos huérfanos en Ecatepec"
✅ "Menores quedan bajo custodia tras asesinato de su madre"
✅ "Niños víctimas indirectas de violencia feminicida"
✅ "Huérfanos por feminicidio sin apoyo del Estado"

❌ "Niños regresan a clases" (NO relevante)
❌ "Menor gana premio de matemáticas" (NO relevante)
```

#### 8. **Crear dashboard específico de feminicidios**

**Acción:** Modificar `dashboard_docker.html`

Agregar métricas:
- Total feminicidios detectados
- Feminicidios con NNA afectados
- Total NNA huérfanos identificados
- Casos por estado
- Casos por mes

---

### 🔵 PRIORIDAD MEDIA (Mejoras)

#### 9. **Validación manual de detección**

Crear script:
```python
# validate_detection.py
def validate_random_sample(n=20):
    """Muestra muestra aleatoria para validación manual."""
    df = pd.read_csv('data/noticias.csv')
    sample = df.sample(n)
    
    for idx, row in sample.iterrows():
        print(f"\n{'='*80}")
        print(f"Título: {row['titulo']}")
        print(f"Contenido: {row['contenido'][:200]}...")
        print(f"\nClasificación automática:")
        print(f"  Feminicidio: {row['es_feminicidio']}")
        print(f"  Tiene NNA: {row['tiene_nna']}")
        print(f"  Huérfanos: {row['tiene_huerfanos']}")
        print(f"  Es objetivo: {row['es_objetivo']}")
        print(f"  Confianza: {row['confianza']:.2f}")
        
        manual = input("\n¿Clasificación correcta? (s/n): ")
        # Guardar para análisis
```

#### 10. **Mejorar sinónimos específicos**

Expandir `synonym_dictionary.py`:
```python
# Contextos específicos de feminicidio + NNA
contexto_feminicidio_nna = [
    "madre asesinada",
    "madre hallada muerta",
    "madre víctima de feminicidio",
    "asesinato de madre",
    "hijos de víctima",
    "menores en orfandad",
    "niños sin madre",
    "custodia de menores tras",
]
```

---

## 📊 MÉTRICAS DE ÉXITO POST-DEPURACIÓN

**Después de implementar cambios, el sistema debe:**

| Métrica | Valor Actual | Objetivo | Mejora Esperada |
|---------|--------------|----------|-----------------|
| % noticias feminicidios | ~2% (3/146) | >70% | +68% |
| % feminicidios con NNA | Desconocido | >30% | N/A |
| Palabras clave encontradas | 4/21 (19%) | 18/21 (85%) | +66% |
| Clusters válidos | 0 | 3-7 | N/A |
| Tópicos relevantes | 0/6 | 4/6 | +67% |
| Precisión detección NNA | Baja | >90% | N/A |

---

## 🚀 ORDEN DE EJECUCIÓN

### Fase 1: Recolección (2-3 días)
1. ✅ Cambiar feeds RSS → feeds especializados
2. ✅ Crear `feminicide_detector.py`
3. ✅ Integrar detección en `data_collector.py`
4. ✅ Ejecutar recolección nueva
5. ✅ Validar que >70% sean feminicidios

### Fase 2: Análisis (1-2 días)
6. ✅ Ajustar TF-IDF (min_df, stopwords)
7. ✅ Recalibrar DBSCAN (eps)
8. ✅ Ejecutar análisis completo
9. ✅ Validar visualizaciones

### Fase 3: Validación (1 día)
10. ✅ Validación manual de muestra
11. ✅ Ajustar patrones de detección
12. ✅ Documentar resultados

### Fase 4: Presentación (1 día)
13. ✅ Actualizar README
14. ✅ Crear dashboard específico
15. ✅ Preparar demo

---

## 💡 CONCLUSIÓN

**Tu proyecto tiene una base técnica sólida pero está DESENFOCADO del objetivo principal.**

### Lo Bueno ✅
- Arquitectura correcta
- Implementación técnica sólida de ML
- Docker funcional
- Código limpio y modular

### Lo Malo ❌
- Feeds RSS inadecuados (generales en vez de especializados)
- Detección genérica de NNA (no específica a huérfanos)
- NO detecta feminicidios específicamente
- Palabras clave eliminadas por parámetros

### Siguiente Paso 🚀
**Implementar Fase 1 URGENTE** para realinear el proyecto con su objetivo real.

---

**Fecha límite recomendada:** Completar Fase 1-2 en 1 semana

