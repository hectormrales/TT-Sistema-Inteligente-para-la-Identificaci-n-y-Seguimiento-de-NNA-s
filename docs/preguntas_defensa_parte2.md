# Banco de Preguntas para la Defensa — TT2
## PARTE 2: Técnico-Profundo
*BETO · Clasificación Escalonada · BERTopic · PostgreSQL · DeepInvestigator*

---

## BLOQUE 4 — BETO y el Motor NLP

---

### P17. ¿Qué es WordPiece y por qué importa para textos periodísticos mexicanos?

> WordPiece es el algoritmo de tokenización de BERT/BETO. Divide palabras desconocidas en sub-tokens con el prefijo `##`. Por ejemplo, `"feminicidio"` se tokeniza como `["femi", "##ni", "##ci", "##dio"]`. Esto permite que BETO maneje el vocabulario abierto del español periodístico — neologismos, siglas, topónimos regionales — sin necesitar una entrada en su vocabulario de 31,000 tokens. El límite máximo es **512 tokens** (configurado como `MAX_SEQ_LENGTH = 512` en `semantic_detector.py`).

### P18. ¿Qué texto exactamente se le pasa a BETO?

> En el dataset (`NNANewsDataset.__getitem__`): `título + " [SEP] " + contenido`. El separador `[SEP]` es el token especial de BERT que delimita segmentos. El tokenizador aplica `truncation=True` — si el texto supera 512 tokens, **se trunca por la derecha** (se pierde el final del contenido). El `[CLS]` al inicio y el `[SEP]` al final son insertados automáticamente por el tokenizador.

### P19. ¿Por qué se usa el token `[CLS]` y no el promedio de todos los tokens?

> BERT fue preentrenado con una tarea NSP (Next Sentence Prediction) cuya señal se acumula en `[CLS]`. Sus 12 capas de auto-atención transforman el `[CLS]` en una representación que captura el significado **global** de toda la secuencia — es el token que más información distribuida recibe por diseño. El promedio de todos los tokens diluye la información con tokens de puntuación y stop words que aportan poco al significado de la oración.

### P20. ¿Qué es la arquitectura `BETOClassifier` exactamente?

> Definida en `semantic_detector.py`:
>
> ```
> BETO Encoder (congelado en Linear Probing)
>   → [CLS] embedding 768-dim
>   → Dropout(0.3)
>   → Linear(768 → 256)
>   → ReLU
>   → Dropout(0.2)
>   → Linear(256 → 2)      ← 2 clases: relevante / no relevante
>   → CrossEntropyLoss durante entrenamiento
>   → Softmax + P(clase=1) durante inferencia
> ```
>
> La pérdida es `CrossEntropyLoss` estándar. En inferencia se extrae `P(relevante)` como score en [0,1].

### P21. ¿Qué es Linear Probing y por qué fue la solución al problema de RAM?

> Fine-Tuning completo actualiza los **110 millones** de parámetros de BETO en cada backward pass — requiere ~16 GB de VRAM en GPU. Linear Probing **congela** el encoder (`bert.parameters()` con `requires_grad=False`) y entrena únicamente la cabeza de clasificación: `Linear(768→256)` + `Linear(256→2)` = **~197,000 parámetros**. El gradiente no necesita propagarse por las 12 capas Transformer. En CPU con 8 GB de RAM, el entrenamiento completa en minutos en lugar de horas con OOM.

### P22. ¿Qué parámetros de entrenamiento se usaron?

> En `semantic_detector.py`:
> - `LEARNING_RATE = 2e-5` — estándar para fine-tuning de BERT
> - `NUM_EPOCHS = 4`
> - `BATCH_SIZE = 4` — pequeño por restricción de RAM
> - `WARMUP_RATIO = 0.1` — 10% de los pasos iniciales con LR creciente para estabilizar la convergencia
> - Optimizador: AdamW (estándar para Transformers)
> - Se implementó Gradient Accumulation para simular batch sizes mayores sin agotar memoria

### P23. ¿Cómo funciona el modo Zero-Shot como fallback?

> Si `model.pt` no existe en `FINETUNED_MODEL_DIR`, el sistema lanza un `Warning` explícito y activa el modo Zero-Shot. Se calculan los embeddings `[CLS]` del texto de entrada y de dos **descripciones de categoría en lenguaje natural** (`CATEGORY_DESCRIPTIONS`): "Caso individual de feminicidio donde sus hijos quedaron huérfanos..." vs "Noticia general que NO relata...". La similitud coseno contra cada descripción produce dos scores brutos. Dado que la diferencia es muy pequeña (0.02-0.05), se aplica **Temperature Scaling** dividiendo los logits por temperatura=5 antes del Softmax para amplificar la separación. En producción, este modo tiene ~60% de FP — por eso se documenta como "ÚLTIMO RECURSO".

### P24. ¿Por qué el modo de operación se lee de la variable de entorno y no del código?

> Porque el sistema corre en Docker. Si el modo estuviera hardcoded, habría que reconstruir la imagen para cambiarlo. `DETECTOR_MODE` en `docker-compose.yml` es la **única fuente de verdad**: garantiza que el mismo contenedor pueda correr `fine-tuned` en producción y `zero_shot` en CI/testing sin cambiar código. El parámetro `mode` del constructor se ignora explícitamente.

---

## BLOQUE 5 — Clasificación Escalonada v7.1 (el núcleo del TT2)

---

### P25. ¿Cuáles son los 4 umbrales exactos del sistema de scoring?

> Del código de `semantic_detector.py`:
>
> | Score final | Clasificación |
> |---|---|
> | ≥ 0.80 | **Alta** (pasa al post-filtro de validación) |
> | ≥ 0.50 y < 0.80 | **Media** |
> | < 0.50 | **No relevante** |
>
> El Escudo Suave aplica `δ = -0.35` al score de BETO. El post-filtro VP aplica bonificaciones de `+0.10` o `+0.25`. El Escudo Léxico descarta con `score = 0.0` absoluto.

### P26. ¿Cuántas keywords tiene el Escudo Léxico y cómo se buscan?

> El `frozenset _ESCUDO_LEXICO` contiene **más de 200 términos** organizados en 8 dominios: macroeconomía, energía, clima, espectáculos, política, deportes, salud pública y tecnología. La búsqueda es `if kw in texto.lower()` — una operación de subcadena pura, O(n_keywords × len_texto), sin ML. El `frozenset` garantiza lookup O(1) por keyword. Si hay match, el pipeline termina ahí sin invocar BETO.

### P27. ¿Por qué el Escudo Suave usa -0.35 y no -0.50?

> -0.35 fue calibrado empíricamente sobre el corpus de validación. Una noticia fáctica genuina con BETO a 0.72 (Media) que menciona "datos del REDIM" baja a 0.37 — se mantiene en el pipeline como Media para revisión humana. Con -0.50 bajaría a 0.22 — clasificaría como No relevante y se perdería. Con -0.20 el Escudo Suave sería insuficiente para degradar estadísticas puras. El valor -0.35 es el punto que minimiza falsos negativos sin aumentar falsos positivos en el corpus de prueba.

### P28. ¿Qué son los `_PATRONES_VP` y `_PATRONES_FP`?

> Son tuplas de expresiones regulares en `semantic_detector.py`:
>
> **`_PATRONES_FP`** (falso positivo — degradar a No relevante):
> - `r"hijo\w*\s+(?:la\s+)?(?:mat[óoaé]|asesin[óoaé])"` — hijo mata a madre
> - `r"(?:adolescente|menor)\s+(?:es\s+)?(?:imputad[oa]|acusad[oa])"` — menor como agresor
> - `r"feminicidio\s+de\s+una\s+menor"` — menor como víctima directa
>
> **`_PATRONES_VP`** (verdadero positivo — confirmar Alta):
> - `r"deja(?:ndo|ron|\s)\s*(?:a\s+)?(?:sus\s+)?(?:\d+\s+)?hijos?"` — deja hijos
> - `r"resguardo\s+del\s+DIF"` — bajo custodia institucional
> - `r"(?:menores?|hijos?)\s+(?:bajo|en)\s+(?:resguardo|custodia)"` — resguardo genérico
>
> La lógica: primero busca FP (si hay match → degradar). Si no hay FP y sí hay VP → confirmar Alta. Si no hay ninguno → "revisar" (baja a Media).

### P29. ¿Por qué la Capa 3 (post-filtro) nunca bloquea una noticia de "Media"?

> Por diseño deliberado. El post-filtro ejecuta `_post_filtro_validacion()` únicamente cuando el score ≥ 0.85 (Alta). Una noticia Media nunca pasa por los `_PATRONES_FP`. Esto evita que el sistema descarte casos reales redactados de forma ambigua — un periodista local puede escribir un caso genuino sin usar las frases exactas del corpus. La Media existe precisamente para que el analista la revise.

---

## BLOQUE 6 — Deduplicación (detalles del código)

---

### P30. ¿Cómo funciona el SimHash exactamente?

> `_simhash()` en `dedup.py` genera un fingerprint de 64 bits:
> 1. Tokeniza el texto normalizado.
> 2. Por cada token, calcula `MD5(token)` → entero de 128 bits.
> 3. Para cada uno de los 64 bits: si el bit `i` del MD5 está activo → `v[i] += 1`; si no → `v[i] -= 1`.
> 4. El fingerprint final: bit `i` = 1 si `v[i] > 0`, else 0.
>
> Dos textos con vocabulario similar generarán hashes con pocos bits diferentes. La distancia de Hamming (`bin(hash1 XOR hash2).count('1')`) mide esa diferencia. Umbral: **≤ 8 bits** = cuasi-duplicado.

### P31. ¿Por qué el Paso 4 (TF-IDF coseno) es el más caro y cuándo se salta?

> El TF-IDF vectoriza todos los textos combinados (título + 1,000 chars de contenido) en una matriz sparse de 3,000 features. La similitud coseno requiere multiplicación matricial O(n²) en el peor caso. Para evitar OOM, se procesa en bloques de 100. **Se omite completamente** si `len(unique_roots) ≤ 5` — es decir, si los pasos 1-3 ya redujeron el corpus a 5 o menos grupos únicos no tendría impacto.

---

## BLOQUE 7 — BERTopic y PostgreSQL

---

### P32. ¿Por qué UMAP y no PCA para reducción de dimensionalidad?

> PCA preserva solo **varianza global lineal** — asume que las relaciones entre puntos son lineales. Los embeddings de BETO viven en un espacio no-lineal de alta dimensionalidad. UMAP preserva simultáneamente estructura **topológica local y global** mediante grafos de vecindad. La configuración `metric='cosine'` en el UMAP de BERTopic es crítica: los embeddings de texto tienen magnitudes variables — la similitud semántica se mide por el ángulo (coseno), no por la distancia euclidiana.

### P33. El 81.4% inicial de outliers en BERTopic, ¿es un fracaso del modelo?

> No — es una característica esperada del corpus periodístico. BERTopic con HDBSCAN solo agrupa documentos en clústeres de **densidad suficiente**. Las noticias que cubren eventos únicos sin cobertura paralela de otros medios son genuinamente outliers. El sistema los reduce al 55% mediante tres estrategias: (1) probabilidades soft de HDBSCAN, (2) distribución c-TF-IDF, (3) umbral de distancia embedding=0.3. Un outlier en BERTopic recibe un umbral de score más alto en BETO (0.65 vs 0.50) — son los casos que requieren más evidencia para clasificar como relevantes.

### P33b. ¿Qué utilidad concreta aporta BERTopic al resultado final? ¿Qué pasaría si lo quitaran?

> Esta es una pregunta legítima que merece una respuesta honesta. BERTopic cumple **dos funciones en el sistema**, ninguna de las cuales es la clasificación principal — eso ya lo hace BETO escalonado:
>
> **Función 1 — Retroalimentación al umbral de clasificación:**
> El tópico asignado a cada noticia influye en el umbral de score que aplica el post-filtro. Una noticia marcada como outlier (sin clúster de densidad suficiente) es tratada con más escepticismo: necesita un score BETO más alto para clasificar como "Alta". Esto reduce los falsos positivos en noticias aisladas sin cobertura paralela en otros medios, que estadísticamente tienen mayor probabilidad de ser contextos genéricos o notas de relleno.
>
> **Función 2 — Agrupamiento cruzado de medios en el dashboard:**
> El analista puede ver qué noticias de distintos medios cubren el mismo caso criminal. Un feminicidio en Ecatepec cubierto por La Jornada, Milenio y un portal local aparece como un clúster coherente — el analista no necesita leer tres artículos para darse cuenta de que son el mismo caso. El tópico BERTopic asignado (visible como etiqueta en el dashboard) también permite filtrar rápidamente por categoría temática sin leer el texto.
>
> **¿Qué pasa si se elimina?**
> El clasificador BETO sigue funcionando igual — la clasificación Alta/Media/Baja no depende de BERTopic. Se pierde la retroalimentación del umbral diferenciado para outliers (lo que podría incrementar marginalmente los falsos positivos) y se pierde la vista agregada por caso en el dashboard. Es una capa de valor añadido para el analista, no el motor de detección. Por eso en el documento técnico se presenta como módulo complementario de agrupamiento, no como parte del pipeline de clasificación primaria.
>
> **Reconocimiento honesto:** En la implementación actual, el vínculo entre el tópico BERTopic y la decisión de clasificación final es débil. La contribución más concreta y medible de BERTopic es la etiqueta de tópico visible en el dashboard — que facilita la navegación del corpus al analista — más que un impacto directo en precisión o recall. La integración más profunda de BERTopic en el pipeline de clasificación es una de las líneas de trabajo futuro identificadas.

### P34. ¿Por qué PostgreSQL y no SQLite o MongoDB?

> **vs SQLite:** SQLite no soporta escrituras concurrentes seguras — el pipeline analítico y el dashboard Flask harían escrituras/lecturas simultáneas sobre `noticias`, generando condiciones de carrera.

> **vs MongoDB:** MongoDB no tiene transacciones ACID completas ni `FOREIGN KEY`. En un sistema de derechos humanos, la consistencia de datos es un requisito ético no negociable. Eliminar una noticia sin propagar el borrado a `detecciones` y `entidades` dejaría registros huérfanos indetectables.

> **vs Elasticsearch:** Ofrece FTS de calidad comparable, pero requiere una JVM y configuración de clúster incompatible con el entorno universitario de 8 GB RAM.

### P35. ¿Qué son los índices GIN y por qué reducen la latencia de búsqueda?

> GIN (Generalized Inverted Index) sobre columna `tsvector` es el equivalente de un índice de motor de búsqueda dentro de PostgreSQL. El `tsvector` almacena un vector léxico preprocesado (stemming Snowball para español, eliminación de stop words) de cada documento. Una búsqueda FTS con índice GIN tiene complejidad **O(log n)** por intersección de listas de postings invertidas. Sin índice, cualquier `LIKE '%feminicidio%'` haría escaneo lineal O(n). Con 10,000 noticias y latencia objetivo < 100ms, el índice GIN es el diferenciador.

### P36. ¿Qué hace el trigger de PostgreSQL en la tabla `noticias`?

> Se ejecuta automáticamente en `INSERT` y `UPDATE`. Concatena `titulo || ' ' || contenido`, lo procesa con `to_tsvector('spanish', texto)` y almacena el resultado en la columna `search_vector`. El diccionario `'spanish'` aplica el stemmer Snowball: reduce `"feminicidios"`, `"feminicida"`, `"feminicidio"` a la misma raíz léxica. Así, una búsqueda por `"feminicidio"` recupera documentos con cualquier variante morfológica sin lógica adicional en la aplicación.

---

## BLOQUE 8 — DeepInvestigator y Detalles Finos

---

### P37. ¿Por qué Gemini Flash y no GPT-4 en el DeepInvestigator?

> Tres razones: (1) **Costo**: Gemini Flash es significativamente más barato que GPT-4 Turbo para volúmenes bajos de uso reactivo. (2) **Integración**: `google-genai` se integra nativamente con `GoogleSearch` como herramienta — si el scraping DuckDuckGo falla, Gemini activa su propio buscador interno como último recurso (`_investigate_with_gemini_search()`). (3) El modelo actual en el código es `gemini-2.5-flash` — no Gemini 1.0, una versión actualizada durante el desarrollo.

### P38. ¿Qué pasa si DuckDuckGo bloquea la búsqueda del DeepInvestigator?

> El flujo tiene **tres niveles de fallback** en `investigate()`:
> 1. Intenta `html.duckduckgo.com/html/?q=...`
> 2. Si falla → intenta `lite.duckduckgo.com/lite/?q=...`
> 3. Si ambos fallan → llama a `_investigate_with_gemini_search()` que activa `types.Tool(google_search=types.GoogleSearch())` — Gemini hace la búsqueda internamente con su propio acceso a la web y devuelve el JSON con el campo `"metodo": "gemini_native_search"`.

### P39. ¿Por qué el campo `medios_contacto` del JSON puede inferirse aunque no esté en el texto?

> El prompt de `_generate_summary()` instruye explícitamente: *"Si no se menciona, sugiérelo según la ubicación (ej. 'Contactar al DIF de Cuautitlán Izcalli')"*. Gemini Flash usa su **conocimiento paramétrico** — sabe qué municipios tienen DIF, cuál es la Fiscalía estatal según el estado mencionado en el texto. Es la única pieza de información en el JSON que puede venir del modelo y no del texto original, y es la más accionable para los trabajadores sociales.

### P40. ¿Por qué el DeepInvestigator extrae solo 4,000 caracteres por URL?

> Límite de contexto práctico. Gemini Flash acepta hasta ~1 millón de tokens de contexto, pero el costo de tokens y la latencia crecen linealmente. El texto relevante de una noticia periodística está concentrado en los primeros 2-3 párrafos. El sistema concatena hasta 8 URLs, dando ~32,000 caracteres totales de contexto. El prompt los limita a `combined_text[:15000]` al llamar a `_generate_summary()`.

---

## BLOQUE 9 — Preguntas Trampa / Difíciles

---

### P41. ¿Sus métricas de precisión son reproducibles? ¿Cómo se midieron?

> Verificación manual sobre el corpus de producción de 634 noticias. El 20% de FP no proviene de un conjunto de test formal con división train/val/test — el corpus etiquetado es pequeño. Esta es una **limitación reconocida** documentada en Trabajo Futuro: el Active Learning propuesto precisamente construiría un conjunto de evaluación más robusto con etiquetado incremental.

### P42. ¿Por qué no usaron transfer learning con un modelo ya fine-tuned en español forense/policial?

> No existe un modelo BERT fine-tuned públicamente disponible para el dominio específico de "crónica policial mexicana + derechos de la infancia". Los modelos disponibles en HuggingFace para español legal (como `dccuchile/bert-base-spanish-wwm-cased-finetuned-ner`) están entrenados para NER general, no clasificación de relevancia en el dominio feminicidio-NNA. Construir ese corpus de dominio específico es parte de la aportación original del proyecto.

### P43. ¿El sistema funciona en tiempo real?

> No en el sentido estricto — opera en **ciclos programados**. El scheduler ejecuta el pipeline completo (scraping + deduplicación + clasificación) en intervalos configurables (6 horas en el entorno de producción documentado). El dashboard muestra el estado del último ciclo. Un ciclo completo de 847 noticias con StealthSession tarda ~90 minutos en condiciones normales — incompatible con alertas en segundos, pero suficiente para el caso de uso de organizaciones civiles que no operan 24/7.

### P44. ¿Qué impide que el sistema sea usado para vigilancia masiva de personas?

> Tres barreras técnicas y legales: (1) El sistema no tiene módulo de reconocimiento facial ni extrae datos de identidad de NNA. (2) La tabla `detecciones` no tiene campos para CURP, nombre completo de menores ni domicilio — por diseño de esquema, no solo por política. (3) El acceso al dashboard requiere autenticación y está desplegado en red interna. Las restricciones LGDNNA son parte del contrato de uso, no solo de la documentación.

### P45. ¿Qué harían diferente si empezaran el TT2 desde cero?

> Tres cosas: (1) Construir el corpus etiquetado desde el día 1, no al final de P3 cuando el Efecto Péndulo ya estaba documentado — habría acelerado el Fine-Tuning 4-6 semanas. (2) Integrar BERTopic desde P2 en lugar de P4 — los clústeres semánticos habrían mejorado el etiquetado del corpus de entrenamiento de BETO. (3) Diseñar el esquema PostgreSQL con todas las tablas desde P1 para evitar las migraciones de Flask-Migrate que consumieron tiempo en la transición CSV → BD.

---

## BLOQUE 10 — Evaluación Formal: Metodología y Kappa
*(preguntas derivadas de las observaciones del director — alta probabilidad de aparición en defensa)*

---

### P46. ¿Sus métricas de precisión y recall fueron medidas sobre un conjunto de prueba independiente del entrenamiento?

> Sí. El conjunto de prueba fue construido seleccionando noticias del corpus de producción que fueron **excluidas explícitamente del fine-tuning** del prototipo 4. El modelo nunca vio esas instancias durante el entrenamiento. Evaluar sobre los mismos datos con los que se entrenó inflaría artificialmente el desempeño — ese sería el error metodológico clásico de data leakage entre train y test. La separación se hizo **antes** de entrenar: primero se reservó el conjunto de prueba y después se procedió con el ajuste fino.

### P47. ¿Qué es el coeficiente Kappa de Cohen y por qué lo usaron?

> El Kappa de Cohen ($\kappa$) mide el **acuerdo entre dos anotadores humanos más allá del azar**. La fórmula es $\kappa = \frac{P_o - P_e}{1 - P_e}$, donde $P_o$ es el acuerdo observado y $P_e$ es el acuerdo esperado por azar. Si dos personas estuvieran anotando aleatoriamente con la distribución de clases del corpus (mayoritariamente "no relevante"), podrían coincidir el 70% de las veces por pura probabilidad. El Kappa descuenta eso. Se usa porque es el estándar en tareas de anotación de corpus en NLP, establecido por Landis y Koch (1977): κ ≥ 0.60 se considera acuerdo sustancial, suficiente para validar un conjunto de evaluación en investigación académica.

### P48. ¿Quiénes fueron los dos anotadores y cuál fue el protocolo?

> Los dos anotadores fueron miembros del equipo del proyecto que no participaron en la construcción del conjunto de entrenamiento de BETO. Se les proporcionó una guía de codificación con la definición operacional de "relevante": noticia que describe un caso fáctico individual donde una mujer adulta fue víctima de feminicidio y sus hijos menores de edad quedaron en situación de orfandad o desamparo. Las anotaciones se hicieron de forma **independiente** — cada anotador trabajó con su propia copia del CSV sin ver las respuestas del otro. Después de anotar, se calculó el Kappa y se resolvieron los casos en disputa por consenso antes de usarlos en la evaluación.

### P49. ¿Por qué reportan el 20% de falsos positivos si ahora dicen que no tenían conjunto de prueba formal?

> El 20% de FP es una **observación operativa** obtenida durante la validación manual del prototipo 4 sobre el corpus de producción completo. No es una métrica calculada con ground truth etiquetado — es la estimación del equipo tras revisar manualmente las noticias clasificadas como "Alta". Es un dato honesto pero metodológicamente distinto de una métrica con conjunto de test separado. En el documento técnico se distinguen claramente ambos: el 20% como observación operativa en la tabla comparativa TT1/TT2, y las métricas formales (Precisión/Recall/F1/κ) como resultados del conjunto de prueba etiquetado.

### P50. ¿El tamaño de su conjunto de prueba es suficiente para sacar conclusiones estadísticas?

> Es una limitación reconocida. Con un corpus de ~634 noticias y la baja prevalencia del fenómeno (~4% de casos Alta), el conjunto de prueba etiquetado es modesto. Eso significa que los intervalos de confianza alrededor de las métricas son amplios — hay incertidumbre en las estimaciones puntuales. Lo que el conjunto de prueba sí permite, con confianza razonable, es: (1) comparar cualitativamente el desempeño del clasificador contra el modo zero-shot baseline, (2) confirmar que el sistema supera el umbral del 30% de FP establecido como meta del TT2, y (3) establecer una línea base reproducible para iteraciones futuras con aprendizaje activo. Esto es lo que se reclama en el documento — no precisión clínica.

### P51. ¿Cómo miden el recall si no conocen todos los casos reales que existen en el corpus?

> Esta es la pregunta más técnicamente correcta sobre la evaluación. El recall formal ($VP / VP + FN$) requiere conocer los falsos negativos — las noticias relevantes que el sistema clasificó como "no relevante". En el conjunto de prueba etiquetado, los FN son las noticias que los anotadores marcaron como relevantes (gold=1) pero el sistema clasificó como "no Alta" (pred=0). Eso sí es medible. Lo que **no** es medible sin revisar manualmente las ~480 noticias clasificadas como "Baja" o "Media" es el recall sobre el corpus completo. Por eso el recall formal se reporta solo sobre el conjunto de prueba, no sobre los 634 artículos totales.

### P52. ¿Cuánto tiempo tomó el proceso de etiquetado y por qué no lo hicieron desde el principio?

> El etiquetado del conjunto de prueba tomó aproximadamente dos horas de trabajo por anotador sobre ~70 noticias. La razón por la que no se hizo desde el inicio del TT2 es que en el prototipo 3, cuando el sistema operaba en modo Zero-Shot con alta tasa de FP, el corpus aún no era lo suficientemente limpio para construir un conjunto de prueba representativo — la mayoría de las noticias candidatas eran falsos positivos obvios, lo que habría sesgado el conjunto de evaluación. Una vez que la arquitectura escalonada del prototipo 4 estabilizó la distribución de clasificaciones, fue posible muestrear aleatoriamente con representación equilibrada de positivos y negativos para construir un conjunto de prueba útil.

---

*— FIN PARTE 2 + BLOQUE 10 — Banco completo: 52 preguntas.*
