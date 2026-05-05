# Documentación del Sistema Inteligente para la Identificación y Seguimiento de NNA (v5.1)

## 1. Introducción
Este sistema es una plataforma avanzada de análisis de noticias diseñada para identificar, recolectar y dar seguimiento a casos de Niños, Niñas y Adolescentes (NNA) que quedan en situación de orfandad o desamparo como víctimas indirectas de feminicidios en México.

El sistema combina técnicas de **Web Scraping de sigilo**, **Procesamiento de Lenguaje Natural (NLP)** y **Modelos de Lenguaje (BETO)** para diferenciar casos reales de noticias estadísticas o ruidosas.

---

## 2. Arquitectura del Sistema
El sistema sigue un flujo de trabajo modular compuesto por 4 fases principales:

### A. Recolección (Collection)
*   **Fuentes**: Google News, RSS feeds de medios nacionales, búsqueda directa y raspado de sitios específicos.
*   **Sigilo**: Uso de `cloudscraper` para bypass de Cloudflare, rotación de User-Agents y Proxies, y retrasos log-normales para emular comportamiento humano.
*   **Circuit Breaker**: Mecanismo de protección que suspende temporalmente el acceso a dominios que detectan actividad automatizada.

### B. Procesamiento y Limpieza
*   **Deduplicación**: Eliminación de noticias repetidas mediante SimHash y similitud de títulos/contenido.
*   **Limpieza NLP**: Normalización de texto, eliminación de stop-words y tokenización para español.

### C. Análisis de Relevancia (Pipeline de Inteligencia)
El sistema utiliza un pipeline de **4 ejes de validación** para asignar una clasificación final:
1.  **Eje Feminicidio**: Identifica términos relacionados con el crimen.
2.  **Eje NNA Indirecto**: Detecta patrones de orfandad, desamparo y resguardo institucional (DIF).
3.  **Eje Caso Individual**: Filtra noticias estadísticas o de política pública.
4.  **Eje Semántico (BETO)**: Inferencia profunda mediante un modelo Transformer (BERT en español) para confirmar el contexto del caso.

### D. Persistencia y Visualización
*   **Base de Datos**: PostgreSQL con soporte para búsqueda de texto completo (FTS).
*   **Dashboard**: Interfaz web (Flask) para la visualización de casos de alta relevancia, métricas geográficas y análisis de tópicos.

---

## 3. Componentes Principales

### `src/collection/collector.py`
Orquestador de la recolección inicial. Implementa el **Scoring Heurístico** que realiza un filtrado rápido por palabras clave y patrones regex.
*   **Novedad v5.1**: Incluye penalizaciones para menores como víctimas directas o agresores.

### `src/analysis/analyzer.py`
El motor principal del pipeline. Coordina los 11 pasos del análisis, desde la vectorización TF-IDF hasta la persistencia final.
*   **Novedad v5.1**: Implementa la lógica de clasificación estricta y orquestación de inferencia por lotes.

### `src/analysis/semantic_detector.py`
Implementa el modelo **BETO** (bert-base-spanish-wwm-cased).
*   **Modo Zero-Shot**: Clasifica noticias comparando el embedding del texto contra descripciones semánticas de categorías.
*   **Batch Inference**: Optimizado para procesar cientos de noticias simultáneamente mediante paralelismo vectorial.

### `src/collection/scraper.py`
Módulo de bajo nivel encargado de las peticiones HTTP. Implementa la clase `StealthSession` que gestiona cookies, proxies y cabeceras para evitar bloqueos.

---

## 4. Configuración y Ejecución

### Requisitos Técnicos
*   Python 3.10+
*   PostgreSQL 14+
*   PyTorch (CUDA recomendado para análisis semántico acelerado)

### Archivos de Configuración
*   `config.py`: Definición de umbrales, pesos de relevancia, credenciales de DB y lista de proxies.

### Comandos de Uso
*   **Ciclo Completo**: `python scheduler.py full` (Recolecta y analiza).
*   **Solo Análisis**: `python scheduler.py analyze` (Procesa datos locales con BETO).
*   **Servidor Web**: `python app.py` (Lanza el dashboard).
*   **Migración**: `python migrate_db_v9.py` (Actualiza el esquema de base de datos).

---

## 5. Mantenimiento y Mejora Continua
Para mantener la precisión del sistema se recomienda:
1.  **Actualizar Proxies**: En `config.py` para asegurar que el scraping no se detenga.
2.  **Monitorear Falsos Positivos**: Si se detectan nuevos tipos de ruido, añadir patrones en `STATS_POLICY_PATTERNS` en `collector.py`.
3.  **Fine-tuning**: Con el tiempo, se pueden usar las noticias marcadas manualmente como "Alta" para realizar un fine-tuning del modelo BETO y aumentar la precisión por encima del 95%.

---
**Desarrollado como parte del Proyecto TT - Sistema Inteligente NNA.**
