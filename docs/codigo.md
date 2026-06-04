# Banco de Preguntas Técnicas — Código del TT2
## Sistema Inteligente para la Identificación y Seguimiento de NNA por Feminicidios

> **Cómo usarlo:** Cada pregunta incluye la ruta exacta del archivo donde está la respuesta y el número de línea relevante. Lee la respuesta en voz alta como si se la dijeras a tu sinodal.

---

## 🗂️ Estructura del proyecto

```
/
├── src/
│   ├── analysis/
│   │   ├── semantic_detector.py   ← Clasificador BETO + 4 capas escalonadas
│   │   ├── analyzer.py            ← Pipeline completo (pasos 1-11)
│   │   ├── dedup.py               ← Deduplicación en cascada (4 algoritmos)
│   │   ├── bertopic_clustering.py ← BERTopic: UMAP + HDBSCAN + c-TF-IDF
│   │   ├── investigator.py        ← DeepInvestigator (Gemini Flash)
│   │   └── synonyms.py            ← Diccionario de sinónimos para FTS
│   ├── collection/
│   │   ├── collector.py           ← RSS + Google News + StealthSession
│   │   └── scraper.py             ← StealthSession v7.0 (anti-WAF)
│   └── database/
│       ├── models_noticias.py     ← ORM SQLAlchemy (4 tablas)
│       └── repository.py         ← Patrón Repository + FTS PostgreSQL
├── app/                           ← Dashboard Flask
├── scheduler.py                   ← Ejecución programada
├── docker-compose.yml             ← 3 contenedores orquestados
└── config.py                      ← Variables de entorno centralizadas
```

---

## 🔴 MÓDULO 1 — Clasificador Escalonado (`src/analysis/semantic_detector.py`)

---

**P1. ¿Cuántas capas tiene el clasificador y qué hace cada una?**

Son 4 capas en orden de costo computacional creciente:

- **Capa 0 — Escudo Léxico** (línea 482–542): `frozenset` con ~120 keywords de dominios ajenos (economía, deportes, clima, política). Si el texto contiene alguna, `score = 0.0` y se termina ahí. Costo: O(n_keywords) sobre texto plano, sin ML.
- **Capa 0b — Escudo Suave** (línea 552–593): Keywords de contenido no-fáctico (estadísticas, leyes, países extranjeros). No bloquea, registra `penalizacion_suave = -0.35` para aplicar después.
- **Capa 2 — BETO fine-tuned** (línea 1076–1108): El texto tokenizado pasa por los 12 bloques Transformer, la cabeza de clasificación produce logits, `softmax` → `probs[1]` = P(clase "relevante") ∈ [0,1].
- **Capa 2b — Aplicación penalización** (línea 942–958): `score_ajustado = max(0.0, score_beto - 0.35)`. Se reclasifica con el score ajustado.
- **Capa 3 — Post-filtro regex** (línea 607–744): Se aplica solo a "Alta" y "Media". Busca patrones VP (verdadero positivo: "quedaron en orfandad", "resguardo del DIF") y patrones FP (hijo mata madre, menor como víctima directa). Puede degradar Alta→Media o cualquiera→No relevante.

---

**P2. ¿Cuáles son los umbrales de clasificación exactos y por qué cambiaron de los originales?**

Los umbrales actuales están en `_classify_score` (línea 1283–1301):

```python
score >= 0.60 → "Alta"
score >= 0.35 → "Media"
score <  0.35 → "No relevante"
```

Los umbrales originales eran ≥0.80 y ≥0.50. Se bajaron porque en modo **Linear Probing** (solo entrenamos la cabeza, 2,307 parámetros, el encoder BETO está congelado), el modelo produce distribuciones de probabilidad más conservadoras — raramente supera 0.75 incluso para casos genuinos. Con los umbrales altos, el sistema no generaba ninguna "Alta". La v7.1 los calibró empíricamente sobre el corpus de producción.

---

**P3. Si aplicas -0.35 de penalización, ¿una noticia Alta puede quedar como Alta todavía?**

Sí, solo si BETO le da ≥ 0.95. Ejemplo: `0.95 - 0.35 = 0.60` → sigue siendo Alta. Pero una noticia donde BETO da 0.87 → `0.87 - 0.35 = 0.52` → cae a Media. Eso es el comportamiento correcto: las noticias con contenido legislativo mezclado con un caso real reciben más escrutinio, no bloqueo absoluto. La función relevante es `max(0.0, score_original + penalizacion)` (línea 948) — el `max(0.0, ...)` garantiza que el score nunca sea negativo.

---

**P4. ¿Qué es el "Bypass de Oro" y cuándo se activa?**

Está en `step_9_semantic_detection` del `analyzer.py` (línea 686–699). Se activa **solo** cuando el post-filtro NO degradó la noticia a "No relevante", y además `score_victima_indirecta >= 0.60` y `score_feminicidio > 0.10`. En ese caso eleva la clasificación a "Alta" con score mínimo 0.75. El punto clave es que **nunca eleva** una noticia que el post-filtro ya rechazó — previene que keywords heurísticas revierten decisiones semánticas. Es la combinación de conocimiento de dominio (heurístico) con validación semántica (BETO).

---

**P5. ¿Cómo está construida la cabeza de clasificación de BETO?**

En `BETOClassifier` (línea 176–227 de `semantic_detector.py`):

```
[CLS] embedding (768 dims)
  → Dropout(0.3)
  → Linear(768 → 256)
  → ReLU
  → Dropout(0.2)
  → Linear(256 → 2)   ← dos logits: [no_relevante, relevante]
  → softmax (en inferencia)
```

El token `[CLS]` es el primer token de toda secuencia BERT/BETO — durante el pre-entrenamiento se optimizó para condensar el significado global del texto. La cabeza tiene `768×256 + 256 + 256×2 + 2 = 197,634` parámetros aproximadamente. Junto con los biases son ~2,307 parámetros entrenables en modo Linear Probing (el encoder de 110M está congelado con `requires_grad=False`).

---

**P6. ¿Por qué usas `local_files_only=True` en la carga del modelo?**

Línea 197 y 351. En producción el sistema corre en Docker sin acceso a internet — `local_files_only=True` fuerza a Hugging Face Transformers a leer solo desde el cache local (`models/cache/`) y falla inmediatamente si no existe, en lugar de intentar una descarga que nunca completaría. El volumen `models_cache` en `docker-compose.yml` (línea 32) persiste ese cache entre reinicios del contenedor.

---

**P7. ¿Cómo evitas que el modo del detector dependa de cómo se instancia la clase?**

El constructor de `SemanticDetector` (línea 251–303) ignora el parámetro `mode` que recibe y siempre lee `os.environ.get("DETECTOR_MODE", "fine-tuned")`. Esto garantiza que `docker-compose.yml` sea la única fuente de verdad — cualquier código que instancie `SemanticDetector("zero_shot")` en realidad usará lo que diga la variable de entorno. Así el comportamiento de producción no depende de cómo el desarrollador llame a la clase.

---

## 🟡 MÓDULO 2 — Deduplicación (`src/analysis/dedup.py`)

---

**P8. ¿Por qué usas 4 algoritmos en cascada y no solo uno?**

Cada algoritmo tiene distinta velocidad y sensibilidad. Se ejecutan en orden de costo creciente y cada uno solo procesa noticias que los anteriores no agruparon:

| Paso | Algoritmo | Detecta | Complejidad |
|---|---|---|---|
| 1 | MD5 del título normalizado | Copias exactas | O(n) |
| 2 | Jaccard de títulos (≥0.70) | Reescrituras léxicas | O(n²) pero con early-exit |
| 3 | SimHash + Hamming (≤6 bits) | Paráfrasis con vocabulario diferente | O(n²) |
| 4 | TF-IDF coseno (≥0.85) | Duplicados semánticos profundos | O(n²) vectorizado por bloques |

El SimHash (línea 62–85) es el más elegante: convierte cada token en su hash MD5, suma o resta 1 de cada bit posición según si el bit correspondiente del hash está activo, y el signo del vector final da el fingerprint. Dos textos similares tienen fingerprints con pocos bits distintos — eso es la distancia de Hamming.

---

**P9. Cuando hay duplicados, ¿cuál conservas?**

El parámetro `keep` del método `deduplicate` (línea 123–273). Con `keep='best'` conserva la noticia con mayor `score_compuesto` del grupo; con `keep='first'` conserva la primera aparición. En el pipeline real se usa `keep='best'` (línea 317 de `analyzer.py`) para quedarse con la noticia mejor cubierta periodísticamente.

---

## 🟠 MÓDULO 3 — Recolección (`src/collection/`)

---

**P10. ¿Cómo evades los WAF de Cloudflare?**

`StealthSession` en `scraper.py` usa `cloudscraper` que reemplaza la pila TLS de Python `requests` por una que genera el mismo hash JA3 que Chrome en Windows. Los WAF modernos no bloquean por User-Agent — bloquean por TLS fingerprint. Además, los delays entre requests son de distribución log-normal (μ=2.5, σ=0.7, mediana ≈12.2s) para imitar el patrón asimétrico de lectura humana. El Circuit Breaker por dominio cuenta fallos consecutivos y entra en cooldown de 300s si llega a 3 — evita el ban permanente de IP.

---

**P11. ¿Por qué RSS y no scraping HTML directo a todos los sitios?**

El RSS ya viene parseado y estructurado — fecha, título, enlace y resumen sin necesidad de analizar el DOM. El 65% de las fuentes tiene RSS activo. Para el 35% restante se usa `StealthSession`. HTML directo puro falló al 100% en el P0 porque los WAF bloquean el fingerprint TLS de `requests`. Los feeds RSS pasan por los mismos CDN pero no activan los WAF porque son endpoints de datos, no páginas renderizadas para humanos.

---

## 🔵 MÓDULO 4 — Base de datos (`src/database/`)

---

**P12. ¿Cuántas tablas tiene el esquema y cómo se relacionan?**

4 tablas en `models_noticias.py`:

- **`noticias`**: tabla central. Tiene `score_feminicidio`, `score_nna`, `score_semantico`, `clasificacion_final`, `cluster_id` (FK), `sesion_id` (FK), `investigacion_json` (JSONB).
- **`detecciones`**: relación 1:1 con noticia (FK con `ondelete=CASCADE`). Guarda scores heurístico, semántico e híbrido por separado para auditoría.
- **`clusters_semanticos`**: un cluster por tópico BERTopic. Las noticias apuntan a su cluster con FK.
- **`entidades`**: NER extraídas (PER/LOC/ORG/MISC) con FK y `CASCADE DELETE`.

La columna `enlace` tiene restricción `unique=True` (línea 59) — es el mecanismo principal anti-duplicado a nivel de base de datos. Si el scraper recoge la misma URL dos veces, el INSERT falla con `IntegrityError` y el Repository lo captura silenciosamente.

---

**P13. ¿Cómo funciona el Full-Text Search del dashboard?**

PostgreSQL tiene FTS nativo. La columna `busqueda_fts` es un `tsvector` generado automáticamente por un trigger SQL que concatena título y contenido con la configuración `'spanish'` (incluye stemming, stop words y normalización de acentos). El índice es GIN (`idx_noticias_fts`), que permite búsquedas en O(log n). Cuando el usuario busca "niños", la consulta tsquery en español también encuentra "menores", "infantes" y "NNA" porque el diccionario de sinónimos expande el query. El `ts_rank` ordena los resultados por relevancia dentro del resultado.

---

**P14. ¿Por qué no usas `CASCADE` en todas las relaciones?**

Se usa `CASCADE DELETE` en `detecciones` y `entidades` (línea 176–278) porque son datos derivados que no tienen sentido sin la noticia padre. Pero `cluster_id` en `noticias` es `nullable=True` sin CASCADE — si se borra un cluster (por reejecutar BERTopic), las noticias no se borran, solo quedan sin cluster (`cluster_id = NULL`). Esto protege el corpus principal de eliminaciones accidentales al actualizar los clusters.

---

## 🟢 MÓDULO 5 — Infraestructura (`docker-compose.yml`, `scheduler.py`)

---

**P15. ¿Cuántos contenedores hay y qué hace cada uno?**

3 servicios en `docker-compose.yml`:

| Contenedor | Imagen | Puerto | Función |
|---|---|---|---|
| `nna-postgres` | postgres:16-alpine | 5432 | Base de datos ACID |
| `nna-analyzer` | Dockerfile propio | — | Pipeline NLP programado (`scheduler.py`) |
| `nna-webapp` | Dockerfile propio | 5000 | Dashboard Flask con Gunicorn |

`nna-webapp` tiene `depends_on: nna-postgres: condition: service_healthy` — no arranca hasta que PostgreSQL pase su healthcheck (`pg_isready`). Gunicorn corre con 2 workers y timeout de 300s (línea 85). El modelo BETO se monta como volumen compartido `models_cache` para que ambos contenedores (analyzer y webapp) lean del mismo cache sin duplicar los 440MB del modelo.

---

**P16. ¿Por qué el analyzer y el webapp son contenedores separados?**

Para separar la carga de CPU. El pipeline NLP (scraping + BETO + BERTopic) es intensivo y puede tardar varios minutos — si corriera dentro del proceso Gunicorn, el timeout de 300s lo mataría. El `nna-analyzer` corre `scheduler.py` que ejecuta el pipeline en background según horario. El `nna-webapp` solo sirve los datos ya procesados desde PostgreSQL. Esta separación también permite reiniciar el dashboard sin interrumpir una ejecución del pipeline.

---

## 🟣 MÓDULO 6 — BERTopic (`src/analysis/bertopic_clustering.py`)

---

**P17. ¿Por qué BERTopic solo procesa noticias Alta y Media, no todo el corpus?**

Línea 744–745 de `analyzer.py`: `mask_relevante = df["clasificacion_final"].isin(["Alta", "Media"])`. UMAP reduce dimensionalidad preservando estructura de vecindad — si el 95% de los documentos son ruido semántico (noticias de economía, deportes, etc. que pasaron los filtros), la proyección UMAP se distorsiona hacia esos outliers y HDBSCAN no puede encontrar densidades coherentes. Al filtrar primero, UMAP trabaja con un espacio semántico cohesivo del dominio feminicidio-orfandad y los clusters resultantes son interpretables.

---

**P18. ¿Qué hace el `min_cluster_size` dinámico?**

Línea 758–765 de `analyzer.py`:

```python
corpus >= 100 → min_cluster_size = 8
corpus 50-99  → min_cluster_size = 5
corpus 20-49  → min_cluster_size = 3
corpus < 20   → min_cluster_size = 2
```

HDBSCAN necesita al menos `min_cluster_size` documentos para formar un cluster — si el valor es fijo y el corpus es pequeño, todos los documentos quedan como outliers (-1). El ajuste dinámico garantiza que siempre haya clusters significativos independientemente del tamaño del ciclo de recolección.

---

**P19. ¿Qué significa que el 81% inicial de noticias sean outliers en BERTopic?**

En HDBSCAN, outlier = documento que no alcanza la densidad mínima para pertenecer a ningún cluster. NO es un error — significa que esas noticias son casos individuales sin cobertura paralela en otros medios. El sistema los trata con mayor escepticismo (si son "Alta" pero outlier, el analista lo ve en el dashboard). Con la estrategia multi-etapa de reducción de outliers (reducción por probabilidad de pertenencia al tópico más cercano), bajamos del 81% al 55%. El 55% restante son genuinamente únicos.

---

## ⚫ PREGUNTAS DE CÓDIGO "TRAMPA"

---

**P20. ¿Por qué `step_4` (LDA) y `step_5` (K-Means) están comentados en el pipeline?**

Líneas 519–521 y 599–601 de `analyzer.py`. LDA y K-Means fueron el sistema de clustering del TT1 basado en TF-IDF. En TT2, BERTopic reemplaza ambos porque opera sobre embeddings de 768 dimensiones de BETO (comprensión semántica) en lugar de vectores TF-IDF léxicos. Mantenerlos sería redundante y aumentaría el tiempo de ejecución. Se dejaron comentados con explicación explícita para que el código sea auditable — se puede ver la evolución TT1→TT2 sin borrar historia.

---

**P21. ¿Por qué `step_7` (TF-IDF rescore) también está comentado?**

Línea 523–525 de `analyzer.py`. El comentario lo explica: `"ELIMINADO: sobrescribía clasificacion_final del collector con un blend 60/40 que destruía las 'Alta' reales"`. Este blend `0.60 × score_heurístico + 0.40 × score_tfidf` sobreescribía la clasificación que ya había hecho BETO en `step_9`. Era un bug de arquitectura — el paso 7 corría antes que el 9 pero sobreescribía su resultado. Se eliminó para que BETO tenga la última palabra.

---

**P22. ¿Qué pasa si BETO no está disponible (no existe `model.pt`)?**

`_detect_mode()` (línea 305–334) verifica si `models/finetuned/model.pt` existe con ruta absoluta (para garantizar funcionamiento en Docker independientemente del CWD). Si no existe, emite un `logger.warning` y cae automáticamente a modo `zero_shot`. En `zero_shot`, la clasificación usa similitud coseno entre el embedding [CLS] del texto y embeddings de descripciones de categorías — sin fine-tuning. La precisión baja pero el sistema no falla: hay degradación graceful en lugar de crash.

---

**P23. ¿Qué contiene `investigacion_json` en la tabla `noticias`?**

Es un campo JSONB (línea 101 de `models_noticias.py`) que almacena la ficha de caso generada por `DeepInvestigator`. Tiene 7 campos: `ubicacion`, `victimas`, `ninos_afectados`, `edades`, `situacion_actual`, `medios_contacto` (DIF y Fiscalía competente) y `resumen`. Se puebla solo cuando el analista activa el DeepInvestigator desde el dashboard — no es automático sobre todo el corpus. `NULL` significa que esa noticia aún no fue investigada en profundidad.

---

**P24. ¿Cómo se garantiza que el mismo enlace no se inserte dos veces?**

Dos niveles: `unique=True` en `enlace` (línea 59 de `models_noticias.py`) crea una restricción `UNIQUE` en PostgreSQL. Si el collector intenta insertar la misma URL, el `INSERT` lanza `IntegrityError`. El `NoticiasRepository` captura ese error y hace `session.rollback()` silenciosamente — la noticia se descarta sin romper la sesión. El segundo nivel es la deduplicación en `dedup.py` que opera antes de llegar a la base de datos, usando el `content_hash` (MD5 del contenido) para detectar el mismo artículo con diferente URL.

---

**P25. ¿Por qué el TF-IDF inyecta "documentos ficticios" con términos de dominio?**

Línea 187–202 de `analyzer.py`. `TfidfVectorizer` calcula IDF (Inverse Document Frequency) sobre el corpus completo — un término que aparece en pocos documentos tiene IDF alto. El problema: palabras como "orfandad" o "DIF" son muy específicas del dominio y aparecen en pocas noticias, pero son las más importantes para el sistema. Sin inyección, podrían quedar fuera del vocabulario si `min_df > 1`. Al agregar 2 documentos artificiales con todos los términos de dominio, se garantiza que esas palabras estén en el vocabulario y tengan peso adecuado. Los documentos artificiales se descartan de la matriz final (línea 202: `self.tfidf_matrix = full_matrix[:len(texts)]`).
