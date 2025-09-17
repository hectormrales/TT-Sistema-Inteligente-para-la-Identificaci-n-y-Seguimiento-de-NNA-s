# Cómo ejecutar el Sistema Inteligente para la Identificación y Seguimiento de NNA's

## Descripción
Este proyecto es un sistema Flask que identifica menciones de Niños, Niñas y Adolescentes (NNA) en noticias sobre femicidios mediante web scraping y procesamiento de lenguaje natural.

## Requisitos previos
- Python 3.7 o superior
- pip (gestor de paquetes de Python)

## Instrucciones de instalación y ejecución

### 1. Navegar al directorio del proyecto
```powershell
cd "c:\RN\TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s"
```

### 2. Activar el entorno virtual (si no está activado)
```powershell
venv\Scripts\activate
```

### 3. Verificar que las dependencias estén instaladas
```powershell
venv\Scripts\pip.exe install -r requirements.txt
```

### 4. Ejecutar la aplicación
```powershell
venv\Scripts\python.exe app\run.py
```

## Uso de la API

Una vez que la aplicación esté ejecutándose, estará disponible en `http://localhost:5000`

### Endpoint disponible:

**POST** `/api/process-url/<url>`
- Procesa una URL de noticia para identificar menciones de NNA
- Ejemplo: `http://localhost:5000/api/process-url/https://ejemplo.com/noticia`

### Ejemplo de uso:
```bash
curl "http://localhost:5000/api/process-url/https://ejemplo.com/noticia-femicidio"
```

## Estructura del proyecto

- `app/run.py` - Archivo principal de la aplicación Flask
- `app/API/routes.py` - Definición de las rutas de la API
- `app/Models/case.py` - Modelo de datos para los casos de femicidio
- `app/NLP/analyzer.py` - Análisis de texto con spaCy para identificar menciones de NNA
- `app/Scraper/scraper.py` - Web scraping de noticias
- `requirements.txt` - Dependencias del proyecto

## Notas importantes

1. El scraper está configurado para selectores CSS genéricos. Deberás ajustar los selectores en `scraper.py` según los sitios web específicos que quieras analizar.

2. La base de datos SQLite se creará automáticamente en `femicide_cases.db` la primera vez que ejecutes la aplicación.

3. El análisis de NLP busca palabras clave como: "hijo", "hija", "hijos", "hijas", "menor", "menores", "huérfanos".

## Solución de problemas

Si encuentras errores:
1. Verifica que el entorno virtual esté activado
2. Asegúrate de que todas las dependencias estén instaladas
3. Verifica que el modelo de spaCy esté descargado: `python -m spacy download es_core_news_sm`
