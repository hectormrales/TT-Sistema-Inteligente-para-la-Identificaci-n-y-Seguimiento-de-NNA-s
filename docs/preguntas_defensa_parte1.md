# Banco de Preguntas para la Defensa — TT2
## PARTE 1: General → Técnico-Medio
*Basado en el código fuente real del repositorio*

---

## BLOQUE 1 — Preguntas Generales (el sinodal de Ciencias Sociales)

---

### P1. ¿Por qué es relevante este sistema para la sociedad mexicana?

> México registró más de 8,000 feminicidios entre 2010 y 2023. La REDIM estima que al menos 3,500 NNA perdieron a su madre en ese periodo. No existe un padrón oficial ni un mecanismo que opere en tiempo real. Las organizaciones civiles lo hacen **manualmente**: decenas de horas semanales revisando portales. El sistema automatiza ese descubrimiento para que el tiempo del personal especializado se invierta en la intervención directa, no en buscar los casos.

### P2. ¿El sistema reemplaza al trabajador social o al analista?

> No. El sistema **asiste**: filtra y clasifica noticias, pero la validación final y la intervención siempre son humanas. El `DeepInvestigator` no se ejecuta automáticamente — el analista lo activa manualmente desde el dashboard sobre cada caso. La IA hace el barrido; el humano toma la decisión.

### P3. ¿Qué tan ético es usar IA para rastrear casos de feminicidio y NNA?

> El sistema procesa exclusivamente **información periodística pública**. La tabla `detecciones` no almacena nombres de menores, CURP ni domicilio. Alineado con el artículo 76 de la LGDNNA (interés superior del menor) y el principio de minimización de datos de la LFPDPPP. El objetivo es visibilizar la *existencia del problema*, no exponer a las víctimas.

### P4. ¿Qué garantiza que las 27 noticias de "Alta" son casos reales?

> Verificación manual: cada una fue revisada por el equipo. Adicionalmente, el post-filtro (`_PATRONES_VP` en `semantic_detector.py`) exige evidencia fáctica explícita — patrones como `"quedaron en orfandad"`, `"resguardo del DIF"` o `"dejando a sus hijos"` — antes de confirmar Alta.

### P5. ¿Por qué no pedirle a los medios que compartan sus datos directamente?

> Porque esa información **no existe como dato estructurado**. Los periodistas mencionan a los hijos colateralmente dentro del texto. No hay un campo "menores afectados" en ninguna base de datos periodística. El sistema extrae ese dato implícito del texto no estructurado mediante PLN, lo cual no es obtenible por acuerdos de intercambio.

---

## BLOQUE 2 — Metodología y Decisiones de Diseño

---

### P6. ¿Por qué prototipado incremental y no cascada?

> El dominio tenía dos incertidumbres técnicas irresolubles upfront: qué proporción de medios bloquearía el scraping y cómo se distribuirían los falsos positivos. El prototipado incremental convirtió cada fallo en un requerimiento medible para el siguiente ciclo. Esto está en la Tabla de Trazabilidad (§5): cada RF/RNF tiene el prototipo que lo originó.

### P7. ¿Cuál fue la decisión de diseño más difícil?

> La transición Zero-Shot → Fine-Tuning en P3→P4. El Zero-Shot fue atractivo porque no requería datos etiquetados, pero los scores para "relevante" y "no relevante" diferían solo 0.02-0.05, causando el **Efecto Péndulo**. Fine-Tuning implicó construir corpus manualmente y resolver el problema de RAM con Linear Probing. Costoso, pero fue el único camino al ~20% de FP.

### P8. ¿Por qué no Scrum?

> Scrum requiere roles diferenciados (Product Owner, Scrum Master) y sprints fijos, incompatibles con un proyecto de investigación de un solo equipo. Se usó **Evolutionary Prototyping**, que comparte los principios iterativos de Scrum pero es aplicable a equipos pequeños de I+D.

---

## BLOQUE 3 — Scraping y Recolección

---

### P9. ¿Por qué no DuckDuckGo como motor principal de scraping?

> DDG es un **motor de búsqueda**, no una fuente de contenido. Cada noticia requeriría 3 requests (query → resultados → artículo), triplica la latencia y está sujeto a rate-limiting agresivo. Un feed RSS entrega los últimos 20-50 artículos en un XML de <50 KB con **una sola petición**. DDG sí se usa, pero solo en el `DeepInvestigator` para búsquedas reactivas puntuales sobre un caso específico.

### P10. ¿Por qué no la API de Google?

> La Custom Search API de Google tiene 100 consultas/día gratis. Con 45 fuentes y ciclos cada 6 horas se necesitan ≥180 consultas/día solo para monitoreo básico. El costo escala a >$5 USD/día. Los feeds RSS son gratuitos, sin límite de solicitudes y son la tecnología diseñada precisamente para consumo automatizado.

### P11. ¿Qué es TLS fingerprinting y por qué es el problema central del scraping moderno?

> Cuando se establece una conexión HTTPS, el cliente negocia parámetros de cifrado generando un **hash JA3** que identifica unívocamente la librería SSL. `Python/requests` produce un JA3 distinto al de Chrome, aunque el User-Agent diga "Chrome". Cloudflare detecta esa asimetría en milisegundos. La solución — implementada en `StealthSession._get_session()` — usa `cloudscraper` con `browser='chrome', platform='windows'`, que reemplaza la pila TLS completa para generar un JA3 idéntico al de un Chrome real en Windows.

### P12. ¿El scraper respeta robots.txt?

> Sí. La clase `RobotsChecker` en `scraper.py` lee y parsea el `robots.txt` de cada dominio **antes** de hacer cualquier solicitud. El bot se identifica con `NNA-Analyzer-Bot/4.0` (no se camufla). Respeta el `Crawl-delay` especificado y cachea los resultados por dominio para no repetir la petición en cada ciclo.

### P13. ¿Por qué distribución lognormal en los delays y no uniforme?

> Una distribución uniforme U(8,20) genera delays perfectamente equidistribuidos, algo imposible en un humano real. Un WAF que observe el patrón verá que nunca hay delays >20s ni <8s — señal inequívoca de bot. Los humanos tienen distribución con **cola derecha larga** (lognormal): mayoría en 8-15s, pero con pausas ocasionales de 25-45s simulando lectura de un artículo largo. En código: `μ=2.5, σ=0.7` → mediana ≈12.2s, moda ≈7.8s, P95 ≈32s. Estadísticamente indistinguible de un usuario leyendo noticias.

### P14. ¿Qué hace el Circuit Breaker y en qué se diferencia de un try/except?

> Un `try/except` maneja un fallo puntual y reintenta inmediatamente. `DomainCircuitBreaker` en `scraper.py` implementa tres estados: **CLOSED** (normal), **OPEN** (tras 3 fallos consecutivos — rechaza requests sin intentarlos por 5 min) y **HALF-OPEN** (permite 1 request de prueba; si falla → OPEN por 10 min). Sin esto, el scraper seguiría golpeando dominios bloqueados agotando el timeout de 25s en cada intento y agravando el ban.

### P15. ¿Cómo se limpia el texto HTML antes de pasarlo al modelo?

> **RSS (65% del corpus):** `feedparser` extrae `title` y `summary` directamente del XML — texto ya limpio.

> **StealthSession (35%):** En `_scrape_content()` se eliminan con `decompose()` los tags `<script>`, `<style>`, `<nav>`, `<header>`, `<footer>`, `<aside>`, `<form>`, `<iframe>`, `<button>`, `<noscript>`. Se extrae el elemento `<article>` o `<main>` antes de recurrir al documento completo. `get_text(separator=' ', strip=True)` convierte el DOM a texto plano y `" ".join(text.split())` colapsa espacios. Resultado truncado a 4,000 caracteres.

> **Para deduplicación**, `_normalize_for_dedup()` añade: lowercase, elimina URLs con regex, elimina puntuación no alfanumérica y colapsa espacios.

### P16. ¿Qué pasa si un medio cambia el formato de su feed RSS?

> El estándar RSS 2.0 tiene esquema **inmutable** — `<title>`, `<description>`, `<link>` no cambian. Si el feed se mueve de `/feed` a `/rss`, el autodescubrimiento prueba 16 paths comunes (`COMMON_RSS_PATHS`). Si desaparece definitivamente, el dashboard muestra el estado de cada fuente para que el administrador la reemplace.

---

*— FIN PARTE 1 — Di "continua" para las preguntas de BETO, clasificación escalonada, base de datos y DeepInvestigator.*
