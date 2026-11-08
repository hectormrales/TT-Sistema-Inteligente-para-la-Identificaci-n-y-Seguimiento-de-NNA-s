# Futuro Con Derechos · Plataforma Inteligente NNA (v2026)

Sistema de monitoreo periodístico, extracción estructurada con Inteligencia Artificial y gestión de expedientes para la identificación y acompañamiento de Niñas, Niños y Adolescentes (NNA) en situación de orfandad por feminicidio en México.

---

## Arquitectura del Sistema (2026)

```text
[1. Descubrimiento Dirigido]
  • 35+ Feeds RSS de Medios Nacionales y Regionales
  • Google News RSS (Decodificación batchexecute Fbv4je)
  • Bing News RSS (Extracción de URL directa + snippet)
  • DuckDuckGo Búsqueda por Rango de Fechas (df=YYYY-MM-DD..YYYY-MM-DD, kl=mx-es)
        │
        ▼
[2. Extracción Full-Text Anti-Bot]
  • Scrapling (Adaptive DOM + Impersonación TLS/HTTP2 Chrome vía curl_cffi)
  • Trafilatura + Extractor JSON-LD (Cuerpo completo de hasta 8,000 caracteres)
        │
        ▼
[3. Deduplicación en Cascada]
  • Hash MD5 Exacto → Jaccard Shingles → SimHash (Hamming ≤ 6)
        │
        ▼
[4. Motor de Extracción Estructurada (`LLMExtractor` + 5 Candados)]
  • Candado 1: Hecho concreto (descarta marchas, leyes, estadísticas, opinión)
  • Candado 2: Ocurrido en México (estado/municipio identificable)
  • Candado 3: Víctima mortal es mujer/madre (descarta infanticidio donde la única fallecida es menor)
  • Candado 4: Menor NO es el agresor (descarta matricidios/parricidios)
  • Candado 5: Existen NNA sobrevivientes en orfandad/desamparo + Cita Textual Verificada
        │
        ▼
[5. Consolidación de Expedientes (`ExpedienteCaso` en PostgreSQL / SQLite)]
  • Agrupa múltiples notas periodísticas del mismo feminicidio bajo un único expediente
  • Flujo de seguimiento ONG: detectado → en_verificacion → contacto_dif_fiscalia → en_acompanamiento → archivado
  • Bitácora institucional de seguimiento y exportación a PDF/CSV
```

---

## Ejecución Rápida

### Opción A — Ejecución Local Directa (Sin Docker)

```powershell
# 1. Instalar dependencias ligeras
pip install -r requirements.txt

# 2. Iniciar la plataforma web (en puerto 5000)
python wsgi.py
```

- Abre en tu navegador: `http://localhost:5000`
- Si PostgreSQL no está corriendo localmente, el sistema activa automáticamente una base de datos local en `data/nna_local.db` para que puedas probar todas las funciones de inmediato.

### Opción B — Ejecución con Docker Compose (PostgreSQL 16 + Scheduler + Webapp)

```powershell
docker compose up -d --build
```

---

## Pruebas Automatizadas

```powershell
pytest -v
```
