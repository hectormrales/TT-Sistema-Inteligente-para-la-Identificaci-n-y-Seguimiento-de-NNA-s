# Plan de Exposición — Defensa TT2
## Sistema Inteligente para la Identificación y Seguimiento de NNA por Feminicidios
**Duración objetivo: 18–20 minutos | 14 diapositivas**

---

> [!IMPORTANT]
> **Regla de ritmo:** Las diapositivas 1–4 son contexto rápido (4 min total). El peso técnico vive en las diapositivas 5–11 (12 min). El cierre es compacto (4 min). Si el sinodal interrumpe con preguntas, sacrifica las notas de los puntos opcionales marcados con *(opcional)*.

---

## Mapa de tiempo

| # | Título | Tiempo |
|---|--------|--------|
| 01 | Portada | 0:30 |
| 02 | El problema: NNA invisibles | 1:00 |
| 03 | Lecciones del TT1 — la línea base | 1:30 |
| 04 | Arquitectura general del TT2 | 1:00 |
| 05 | Reto 1: Scraping contra WAF | 2:00 |
| 06 | Reto 2: Deduplicación en cascada | 1:30 |
| 07 | Reto 3: Por qué NLP profundo (BETO) | 2:00 |
| 08 | La solución: Clasificación Escalonada v7.1 | 2:00 |
| 09 | BERTopic: agrupamiento semántico | 1:00 |
| 10 | DeepInvestigator: IA generativa bajo demanda | 1:30 |
| 11 | Resultados cuantitativos | 1:30 |
| 12 | El producto: Dashboard operativo | 1:00 |
| 13 | Conclusiones y trabajo futuro | 1:00 |
| 14 | Cierre | 0:30 |
| **Total** | | **~18:30** |

---

## Diapositiva 01 — Portada
**Tiempo: 0:30**

### Contenido visual
- Título del TT: *"Sistema Inteligente para la Identificación y Seguimiento de NNA en situación de orfandad por feminicidio"*
- Protocolo: TT 2026-A135
- Nombre del alumno, directores
- Logos IPN / ESCOM
- Fecha: Junio 2026

### Speech
> *"Buenos días. Mi nombre es Hector Morales Martínez y les presento el Trabajo Terminal número 2026-A135: un sistema inteligente diseñado para hacer visible lo que hoy es invisible — los niños y niñas que quedaron solos tras el feminicidio de su madre."*

---

## Diapositiva 02 — El problema: NNA invisibles
**Tiempo: 1:00**

### Contenido visual
- **Dato impacto (grande, centrado):** `+8,000 feminicidios en México (2010–2023)`
- **Dato impacto secundario:** `~3,500 NNA en orfandad — sin padrón oficial`
- Ícono de noticia fragmentada → dispersión en medios locales
- Frase ancla: *"La información existe, pero no es accesible a escala computacional."*

### Speech
> *"El problema no es falta de información — es que esa información está fragmentada en miles de notas de medios locales, comunicados de fiscalías y archivos de ONGs que jamás se conectan entre sí. Organizaciones como Futuro con Derechos dedican decenas de horas semanales a revisar portales manualmente, y aún así muchos casos pasan desapercibidos. México tiene más de 1,200 medios digitales activos. Es imposible auditarlos todos con un equipo humano."*

---

## Diapositiva 03 — Lecciones del TT1 — la línea base
**Tiempo: 1:30**

### Contenido visual
Tabla compacta de 3 filas (prototipos P0, P1, P2):

| Prototipo | Enfoque | Resultado | Problema fatal |
|-----------|---------|-----------|----------------|
| P0 | Scraping HTML directo | 0% éxito | WAF bloqueó todo |
| P1 | 8 RSS + palabras clave | 96 noticias | **80% falsos positivos** |
| P2 | 10 RSS + 72 patrones RegEx | 250 noticias | **60% falsos positivos** |

- Flecha al final: *"El paradigma léxico alcanzó su techo. Necesitamos comprensión semántica."*

### Speech
> *"El TT1 fue un ciclo de diagnóstico deliberado. En tres prototipos aprendimos tres cosas fundamentales: primero, que el scraping HTML directo está muerto — los firewalls lo bloquean al instante. Segundo, que 8 fuentes RSS son insuficientes para cobertura nacional. Y tercero — el hallazgo más importante — que ningún sistema basado en expresiones regulares puede superar el 60% de falsos positivos, porque la co-ocurrencia de palabras no implica la co-ocurrencia de significado. Con esa evidencia empírica, diseñamos el TT2."*

---

## Diapositiva 04 — Arquitectura general del TT2
**Tiempo: 1:00**

### Contenido visual
Diagrama de flujo horizontal en 5 bloques encadenados:

```
[Recolección] → [Deduplicación] → [Clasificación] → [Agrupamiento] → [Dashboard]
  45 RSS           Cascada 4F      BETO Escalonado     BERTopic        Flask
  Google News      MD5→Coseno      + DeepInvestigator  UMAP+HDBSCAN    PostgreSQL
  StealthSession
```

- 3 contenedores Docker en la parte inferior como base de infraestructura

### Speech
> *"El TT2 integra cinco módulos en un pipeline continuo. Cada uno resuelve un problema específico identificado en el TT1. Voy a explicar los tres más pesados técnicamente: el scraping, el procesamiento de lenguaje natural, y los modelos de IA."*

---

## Diapositiva 05 — Reto 1: Scraping contra WAF
**Tiempo: 2:00** *(diapositiva técnica principal)*

### Contenido visual
**Mitad izquierda — El problema:**
- Diagrama: `Python requests` → `JA3 hash` → `WAF detecta bot` → `HTTP 403`
- Cifra: *78% de medios detrás de Cloudflare/Akamai*

**Mitad derecha — La solución (StealthSession v7.0):**
1. `cloudscraper` — emula fingerprint TLS de Chrome/Windows
2. Delays **log-normal** (μ=2.5, σ=0.7) — mediana 12.2s, imita lectura humana
3. **Circuit Breaker** por dominio — 3 fallos → cooldown 300s → evita ban de IP

- Resultado: *"85%+ tasa de éxito en producción con 45 fuentes RSS + scraping stealth"*

### Speech
> *"El primer obstáculo técnico del TT2 fue la evasión de Web Application Firewalls. Los WAF modernos no se bloquean por User-Agent — se bloquean por TLS fingerprinting: comparan el hash criptográfico del saludo TLS del cliente contra el navegador declarado. Python con `requests` genera un hash JA3 que es inmediatamente reconocible. La solución fue `StealthSession`, que reemplaza la pila TLS completa con `cloudscraper` para generar hashes idénticos a Chrome en Windows. Complementamos eso con delays de distribución log-normal — porque los humanos reales no esperan exactamente 10 segundos entre cada click, tienen un patrón asimétrico con pausas ocasionales largas. Y un Circuit Breaker por dominio que detiene automáticamente los reintentos cuando un sitio está bloqueando activamente, evitando el ban permanente de IP."*

---

## Diapositiva 06 — Reto 2: Deduplicación en cascada
**Tiempo: 1:30**

### Contenido visual
Diagrama de embudo con 4 etapas y sus números reales:

```
900 noticias brutas
        ↓  [Hash MD5]      → -89 duplicados exactos
        ↓  [Jaccard ≥0.70] → -61 reescrituras léxicas
        ↓  [SimHash ≤6bit] → -43 paráfrasis
        ↓  [Coseno TF-IDF ≥0.85] → -20 duplicados de contenido
= 634 noticias únicas (25% eliminado)
```

- Nota al margen: *"Coste computacional ascendente — los casos obvios se resuelven con el método más barato."*

### Speech
> *"Con 45 fuentes cubriendo los mismos eventos, la redundancia periodística es inevitable. El mismo feminicidio puede aparecer en La Jornada, Milenio y El Universal con redacciones completamente diferentes. Sin deduplicación, el corpus inflado genera alertas redundantes que saturan al analista. Implementamos una cascada de cuatro algoritmos en orden de coste computacional creciente: MD5 detecta copias exactas en O(1); Jaccard detecta reescrituras léxicas simples; SimHash usa proyecciones aleatorias para detectar paráfrasis sin comparaciones par a par; y coseno TF-IDF resuelve los casos más ambiguos. Resultado: 25% del corpus era ruido. Lo que llegó al clasificador era limpio."*

---

## Diapositiva 07 — Reto 3: Por qué NLP profundo
**Tiempo: 2:00** *(la más importante para el sinodal)*

### Contenido visual
**Comparativa conceptual en 2 columnas:**

| RegEx / TF-IDF (TT1) | BETO Transformer (TT2) |
|---|---|
| Ve: co-ocurrencia de tokens | Ve: rol semántico en contexto bidireccional |
| *"menor + feminicidio"* → alerta | Distingue: menor agresor vs. menor víctima indirecta |
| Ciego a la sintaxis | Comprende: *"sus hijos menores quedaron en resguardo del DIF"* |
| 60% falsos positivos | ~20% falsos positivos |

**Abajo:** Arquitectura simplificada de BETO
- 12 capas Transformer → 110M parámetros → 768 dimensiones por token
- **Linear Probing:** solo se entrena la cabeza de clasificación (2,307 parámetros) → viable en CPU con 8 GB RAM

### Speech
> *"El corazón técnico del TT2 es BETO — bert-base-spanish-wwm-cased — un modelo Transformer bidireccional con 110 millones de parámetros preentrenado exclusivamente en corpus españoles, incluyendo prensa latinoamericana. ¿Por qué Transformer y no una red recurrente o expresiones regulares? Porque el mecanismo de auto-atención permite que cada token recalcule su representación considerando TODOS los demás tokens de la oración simultáneamente. Esto significa que la palabra 'menor' adquiere representaciones vectoriales radicalmente distintas dependiendo de si aparece como sujeto activo — 'un menor agredió' — o como víctima pasiva — 'sus hijos menores quedaron huérfanos'. Esta distinción es exactamente lo que el sistema necesita y ningún sistema léxico puede aproximar."*
>
> *"Un desafío crítico fue el hardware: el reentrenamiento completo de 110M de parámetros requiere GPU de al menos 16 GB. Nosotros trabajamos en CPU con 8 GB de RAM. La solución fue Linear Probing — congelamos todos los bloques Transformer del encoder y entrenamos únicamente la cabeza de clasificación lineal, reduciendo los parámetros entrenables de 110 millones a aproximadamente 2,300. Esto hizo el ajuste fino viable en hardware universitario."*

---

## Diapositiva 08 — La solución: Clasificación Escalonada v7.1
**Tiempo: 2:00** *(el aporte arquitectónico central)*

### Contenido visual
Diagrama de flujo vertical con 4 capas, cada una con su acción:

```
📰 Noticia entra al pipeline
    │
    ▼
[Capa 0 — Escudo Léxico]
  frozenset O(1) → ¿habla de deportes/economía/criptomonedas?
  SÍ → score = 0.0, DESCARTADA
    │
    ▼
[Capa 1 — Escudo Suave]
  ¿menciona "iniciativa de ley", "estadísticas del REDIM"?
  SÍ → score -= 0.35  (penalización, NO exclusión)
    │
    ▼
[Capa 2 — Inferencia BETO Fine-Tuned]
  P(relevante | texto) → suma al score acumulativo
  score > 0.50 → continúa
    │
    ▼
[Capa 3 — Post-filtro]
  "quedó al cuidado de" → +0.10/+0.25 (bonificación)
  "hijo adolescente mató" → penalización (rol invertido)
    │
    ▼
  score ≥ 0.80 → ALTA   |   ≥ 0.50 → MEDIA   |   < 0.50 → No relevante
```

- Etiqueta clave: **"Sistema Neuro-Simbólico: las reglas simbólicas modulan al componente neuronal"**

### Speech
> *"El Prototipo 3 con BETO en modo zero-shot reveló un nuevo problema que llamamos el Efecto Péndulo: el sistema oscilaba entre exceso de falsos positivos y exceso de falsos negativos. BETO es potente, pero opera sobre correlaciones estadísticas. Un artículo de opinión que dice 'miles de niños perdieron a su madre' obtenía score 0.81 — sin reportar ningún caso concreto. Un titular como 'Hijo adolescente mata a su madre' confundía al modelo porque 'hijo', 'madre' y 'asesinato' co-ocurren en el espacio semántico."*
>
> *"La solución fue una arquitectura neuro-simbólica de cuatro capas. El término 'neuro-simbólico' es preciso: las reglas simbólicas — que codifican conocimiento experto del dominio — no reemplazan al modelo neuronal, sino que modulan su salida mediante penalizaciones y bonificaciones aditivas. El Escudo Suave es el ejemplo más elegante: en lugar de bloquear absolutamente una noticia que menciona 'datos del REDIM', le resta 0.35 puntos al score. Si la noticia también relata un caso concreto de feminicidio, BETO le suma 0.75 — y el score ajustado de 0.40 la clasifica como Media en lugar de descartarla. Eso eliminó el Efecto Péndulo."*

---

## Diapositiva 09 — BERTopic: agrupamiento semántico
**Tiempo: 1:00**

### Contenido visual
Pipeline modular en 3 pasos:

```
Embeddings BETO (768D)
    → UMAP (768D → 5D, métrica coseno, preserva topología)
    → HDBSCAN (densidad variable, sin k fijo, genera outliers)
    → c-TF-IDF (representación léxica interpretable por tópico)
```

- Resultado real: **15 tópicos semánticos** sobre 634 noticias
- Outliers: 81.4% → reducidos a 55% con estrategia multi-etapa
- Ejemplo tópico: *"custodia DIF / menores testigos / manifestaciones colectivos"*

### Speech
> *"El agrupamiento semántico resuelve algo que la clasificación individual no puede: detectar qué noticias hablan del mismo caso criminal aunque provengan de medios con vocabularios completamente distintos. BERTopic encadena tres algoritmos: UMAP reduce los 768 embeddings de BETO a 5 dimensiones preservando la topología del espacio semántico; HDBSCAN agrupa por densidad sin necesitar un número de clústeres fijo; y c-TF-IDF extrae las palabras más representativas de cada tópico para hacerlos interpretables. El 81% inicial de outliers — noticias que no forman parte de ningún clúster — no es un error: son casos individuales sin cobertura paralela, que el sistema trata con mayor escepticismo en la clasificación."*

---

## Diapositiva 10 — DeepInvestigator: IA generativa bajo demanda
**Tiempo: 1:30**

### Contenido visual
Flujo de 4 pasos con íconos:

```
[Analista activa desde dashboard]
    ↓
① Gemini Flash → genera query específica (≤6 palabras, nombre víctima + detalle único)
    ↓
② DuckDuckGo (HTML + Lite) → URLs complementarias
    ↓
③ StealthSession → extrae contenido (hasta 15,000 caracteres)
    ↓
④ Gemini Flash → JSON estructurado con 7 campos:
   ubicacion | victimas | ninos_afectados | edades | situacion_actual | medios_contacto | resumen
```

- Dato clave: **promedio 47 segundos por caso**
- Nota: *"Diseño reactivo — NO automático sobre todo el corpus (latencia + cuota API)"*

### Speech
> *"Una vez que el analista identifica una noticia de Alta relevancia, activa el DeepInvestigator. Este módulo usa Gemini Flash — no para clasificar, sino para investigar. Primero genera una query de búsqueda de alta especificidad con el nombre de la víctima y detalles únicos del caso — preferible al título literal porque filtra resultados genéricos sobre la misma temática. Luego busca en DuckDuckGo, extrae el contenido de las URLs encontradas via StealthSession, y finalmente Gemini sintetiza toda la información en una ficha de caso JSON con siete campos estructurados. El campo más valioso es medios_contacto: Gemini retorna el DIF municipal y la Fiscalía competente según la ubicación del caso — incluso cuando la noticia no los menciona explícitamente, usando su conocimiento paramétrico. Por diseño deliberado, el módulo es reactivo: activarlo automáticamente sobre todo el corpus tomaría 90 minutos extra y saturaría la cuota gratuita de la API."*

---

## Diapositiva 11 — Resultados cuantitativos
**Tiempo: 1:30** *(la más fácil de defender)*

### Contenido visual
Tabla de cumplimiento de metas con ✓ en cada fila:

| Métrica | TT1 (P2) | Meta TT2 | Resultado P4 | ✓ |
|---|---|---|---|---|
| **Falsos positivos** | 60% | < 30% | ~20% | ✓ |
| **Fuentes monitoreadas** | 10 RSS | 45 RSS + GNews | 45 RSS + GNews + Stealth | ✓ |
| **Volumen de ingesta** | 281 noticias | >500 únicas | **634 únicas** | ✓ |
| **Motor de clasificación** | RegEx 72 patrones | BETO fine-tuning | BETO Finetuned + Escalonado | ✓ |
| **Persistencia** | CSV plano | PostgreSQL 16 | PostgreSQL 16 (ACID) | ✓ |

- Nota: **27 casos de Alta relevancia** (4.4% del corpus) — verificados manualmente

### Speech
> *"Los resultados cierran el ciclo que abrimos en el TT1. Las seis metas cuantitativas definidas al inicio del semestre fueron cumplidas. El dato más significativo es la tasa de falsos positivos: pasamos del 60% con RegEx al 20% con la arquitectura escalonada — una reducción del 67% en ruido semántico. El corpus de 634 noticias únicas procesadas en un solo ciclo de ejecución triplica el volumen máximo del TT1. Y las 27 noticias de Alta clasificación fueron verificadas manualmente — todas corresponden a casos reales de orfandad por feminicidio con NNA identificables."*

---

## Diapositiva 12 — El producto: Dashboard operativo
**Tiempo: 1:00**

### Contenido visual
- Screenshot del dashboard (imagen `dashboard_principal.png`)
- Etiquetas señalando: clasificación Alta/Media, score semántico, tópico BERTopic, botón "Investigar", buscador FTS, exportar CSV

### Speech
> *"El producto final es un dashboard Flask accesible desde cualquier navegador, desplegado en Docker con tres contenedores — la base de datos PostgreSQL, el analizador y la interfaz web. El analista ve inmediatamente las noticias ordenadas por score semántico, puede filtrar por clasificación, buscar con Full-Text Search en español con latencia O(log n) gracias a los índices GIN, y activar el DeepInvestigator sobre cualquier noticia de Alta relevancia con un clic. Los casos investigados se agregan a una lista de seguimiento exportable en CSV. Lo que antes eran decenas de horas de revisión manual se convierte en minutos de revisión semi-automatizada."*

---

## Diapositiva 13 — Conclusiones y trabajo futuro
**Tiempo: 1:00**

### Contenido visual
**2 columnas:**

**Aportaciones técnicas:**
- Arquitectura neuro-simbólica de clasificación escalonada (generalizable a otros dominios de monitoreo de medios)
- Pipeline de investigación profunda bajo demanda con LLM

**Trabajo futuro:**
- Aprendizaje activo → falsos positivos < 10%
- NER especializado en dominio (PER/LOC/ORG sin API externa)
- Expansión a redes sociales (X/Twitter, Telegram)
- API pública con anonimización LGDNNA

### Speech
> *"El sistema cumplió su objetivo: que ningún caso de NNA en orfandad por feminicidio sea invisible para las instituciones obligadas a protegerlo. Más allá del dominio específico, la arquitectura de clasificación escalonada es una contribución generalizable: demuestra empíricamente que integrar reglas simbólicas como moduladoras de un modelo neuronal resuelve el solapamiento semántico en dominios hiper-específicos de forma más robusta que el fine-tuning supervisado en solitario. El trabajo futuro prioritario es el aprendizaje activo: que el propio sistema identifique los casos de mayor incertidumbre y los presente al analista para etiquetado, reduciendo progresivamente los falsos positivos por debajo del 10%."*

---

## Diapositiva 14 — Cierre
**Tiempo: 0:30**

### Contenido visual
- Frase de impacto centrada:
  *"Detrás de cada caso de Alta relevancia hay un NNA que el Estado tiene la obligación legal de proteger."*
- Datos finales en pequeño: TT 2026-A135 · ESCOM-IPN · Junio 2026
- Agradecimiento a directores

### Speech
> *"Gracias. El sistema está operativo, documentado y listo para ser adoptado por organizaciones civiles. Quedo a disposición para responder sus preguntas."*

---

## Preguntas frecuentes que puede hacer el sinodal

> [!TIP]
> Prepara respuestas cortas (30–45 seg) para estas:

**1. ¿Por qué no usaron GPT-4 o Claude en lugar de BETO?**
> Tres razones: privacidad (datos de víctimas menores no pueden salir del sistema), costo (600 noticias en GPT-4 = ~$40 USD por ciclo), y reproducibilidad científica (los modelos propietarios modifican sus pesos sin aviso).

**2. ¿El 20% de falsos positivos sigue siendo alto?**
> Es significativamente mejor que el 60% del TT1. Además, el sistema está diseñado para que el analista humano haga la validación final — el 20% residual son los casos que BETO no puede resolver sin más contexto, exactamente para eso existe el DeepInvestigator.

**3. ¿Es ético usar IA para rastrear casos de feminicidio?**
> El sistema procesa exclusivamente información periodística pública. No identifica datos personales de NNA — eso está explícitamente excluido por diseño y alineado con la LGDNNA. El objetivo es visibilizar la crisis, no exponer a las víctimas.

**4. ¿Qué pasa si un medio cambia su feed RSS?**
> El módulo de gestión de fuentes del dashboard incluye un sondeo técnico previo (ping + validación del feed) antes de activar cualquier fuente nueva. Si un feed deja de funcionar, el Circuit Breaker lo detecta y el administrador recibe la alerta.

**5. ¿Cómo validan que las 27 noticias de Alta son casos reales?**
> Verificación manual: cada una de las 27 fue revisada individualmente por el equipo. Todas contienen menciones explícitas a NNA que quedaron sin madre, con datos de ubicación verificables y cobertura en medios identificados.
