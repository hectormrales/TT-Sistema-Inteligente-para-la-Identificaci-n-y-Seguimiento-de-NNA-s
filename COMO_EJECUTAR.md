# Cómo ejecutar el Sistema Inteligente para la Identificación y Seguimiento de NNA's

## Descripción
Este proyecto es un sistema Flask que identifica menciones de Niños, Niñas y Adolescentes (NNA) en noticias mediante web scraping y procesamiento de lenguaje natural.

## ✅ Estado Actual - FUNCIONAL
La aplicación está **funcionando correctamente** después de las siguientes correcciones:
- ✅ Dependencias instaladas (Flask, pandas, beautifulsoup4, requests, etc.)
- ✅ Procesamiento de texto simplificado (sin spaCy por ahora)
- ✅ Dashboard web funcional con interfaz de usuario
- ✅ Recolección automática de noticias desde RSS
- ✅ Detección de menciones de menores funcionando
- ✅ Sistema de pruebas implementado

## Requisitos previos
- Python 3.7 o superior
- pip (gestor de paquetes de Python)

## Instrucciones de instalación y ejecución

### 1. Navegar al directorio del proyecto
```powershell
cd "c:\RN\TT-1\TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s"
```

### 2. Las dependencias ya están instaladas en el entorno virtual
El entorno virtual `.venv` ya está configurado con todas las dependencias necesarias.

### 3. Ejecutar la aplicación
```powershell
.\.venv\Scripts\python.exe .\run.py
```

### 4. Acceder al dashboard
Una vez ejecutada, abrir el navegador en: `http://127.0.0.1:5000/dashboard`

## Funcionalidades disponibles

### Dashboard Web (`http://127.0.0.1:5000/dashboard`)
- 📊 Visualización de noticias analizadas
- 🔍 Detección automática de menciones de NNA
- 📰 Botón para recolectar nuevas noticias
- 🎯 Resaltado de casos con menores identificados

### API Endpoints disponibles:

1. **GET** `/dashboard` - Dashboard principal
2. **POST** `/collect-news` - Recolecta noticias de RSS y las analiza
3. **GET** `/api/status` - Estado de la API

### Ejemplo de uso de la API:
```bash
# Recolectar noticias
curl -X POST "http://localhost:5000/collect-news"

# Verificar estado
curl "http://localhost:5000/api/status"
```

## Estructura del proyecto (actualizada)

```
├── run.py                          # Archivo principal de la aplicación Flask
├── app/
│   ├── __init__.py                # Inicialización de la app Flask
│   ├── routes.py                  # Rutas y endpoints de la API
│   └── templates/
│       └── dashboard.html         # Interfaz web del dashboard
├── src/
│   ├── collection/
│   │   └── data_collector.py      # Recolección de noticias desde RSS
│   ├── processing/
│   │   └── text_processor.py      # Procesamiento y limpieza de texto
│   ├── analysis/
│   │   └── news_analyzer.py       # Análisis con ML (TF-IDF, K-Means)
│   └── utils/
│       └── file_handler.py        # Manejo de archivos CSV
├── data/
│   └── noticias_analizadas.csv    # Datos procesados
├── config.py                      # Configuración (RSS feeds, parámetros)
├── requirements.txt               # Dependencias del proyecto
└── test_app.py                   # Script de pruebas
```

## Funciones principales implementadas

### 1. Detección de Menciones de Menores
- Palabras clave: "hijo", "hija", "menor", "niño", "huérfano", etc.
- Resaltado automático en el dashboard
- Estadísticas en tiempo real

### 2. Recolección de Noticias
- RSS feeds configurables en `config.py`
- Parsing automático de títulos, contenido y fechas
- Almacenamiento en CSV para análisis

### 3. Procesamiento de Texto
- Limpieza y normalización de texto
- Eliminación de acentos y puntuación
- Preparación para análisis ML futuros

## Pruebas del sistema

Para verificar que todo funciona correctamente:
```powershell
.\.venv\Scripts\python.exe .\test_app.py
```

Esto ejecuta pruebas de:
- ✅ Detección de menciones de menores
- ✅ Procesamiento de texto
- ✅ Carga de datos CSV

## Solución de problemas

Si encuentras errores:

1. **Error de dependencias**: Las dependencias ya están instaladas en `.venv`
2. **Error de spaCy**: Se eliminó la dependencia de spaCy temporalmente
3. **Archivo CSV no encontrado**: Se crea automáticamente con datos de ejemplo
4. **Puerto ocupado**: Cambia el puerto en `run.py` si el 5000 está ocupado

## Próximos pasos sugeridos

1. **Instalar spaCy** (opcional, para NLP avanzado):
```powershell
.\.venv\Scripts\pip.exe install spacy
.\.venv\Scripts\python.exe -m spacy download es_core_news_sm
```

2. **Agregar más fuentes RSS** en `config.py`

3. **Implementar clustering ML** usando las funciones en `news_analyzer.py`

4. **Configurar base de datos** (SQLite o PostgreSQL) en lugar de CSV
