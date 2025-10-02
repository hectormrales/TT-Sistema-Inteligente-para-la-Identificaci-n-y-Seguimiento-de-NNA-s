# Cómo Ejecutar el Sistema Avanzado de Web Scraping

## 🚀 Sistema con Gestión Dinámica de Fuentes

### Características Principales

- ✅ **Gestión dinámica de fuentes RSS**: Agregar, editar, eliminar fuentes desde la web
- ✅ **Múltiples técnicas de scraping**: requests, selenium, rotación UA, delays, async
- ✅ **Scraping ético**: Verificación de robots.txt automática
- ✅ **Manejo inteligente de errores**: Auto-deshabilitación y recuperación
- ✅ **Persistencia de configuraciones**: Guardado automático en JSON
- ✅ **Interfaz web moderna**: Bootstrap 5 con modales interactivos

### 1. Demostración del Sistema Avanzado

```bash
# Ejecutar demostración completa del sistema
python demo_sistema_avanzado.py
```

Esta demostración mostrará:
- Gestión dinámica de fuentes
- Múltiples técnicas de web scraping
- Persistencia de configuraciones
- Manejo y recuperación de errores
- Estadísticas detalladas del sistema

## Versión Dockerizada (Recomendada)

### 1. Preparación del entorno

Asegúrate de tener Docker y Docker Compose instalados en tu sistema.

### 2. Construir y ejecutar con Docker Compose

```bash
# Construir las imágenes
docker-compose build

# Ejecutar los servicios
docker-compose up -d

# Ver logs
docker-compose logs -f web
```

### 3. Acceder a la aplicación

- **Dashboard principal**: http://localhost:5000
- **Gestión de fuentes**: http://localhost:5000 (sección "Gestión de Fuentes RSS")
- **API de análisis**: http://localhost:5000/api/analyze
- **API de fuentes**: http://localhost:5000/api/sources

### 4. Comandos útiles de Docker

```bash
# Detener servicios
docker-compose down

# Ver contenedores activos
docker ps

# Acceder al contenedor
docker exec -it sistema_inteligente_web_1 bash

# Ver logs en tiempo real
docker-compose logs -f
```

## Versión Local (Desarrollo)

### 1. Instalar dependencias

```bash
# Dependencias básicas
pip install -r requirements.txt

# Dependencias adicionales para sistema avanzado
pip install selenium==4.15.2 aiohttp==3.8.6 fake-useragent==1.4.0
```

### 2. Configurar ChromeDriver para Selenium

**Windows:**
```bash
# Descargar ChromeDriver desde https://chromedriver.chromium.org/
# Agregar al PATH del sistema
```

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install chromium-chromedriver

# Mac con Homebrew
brew install chromedriver
```

### 3. Ejecutar la aplicación

```bash
# Aplicación principal
python run.py

# O versión dockerizada para desarrollo
python app_docker.py
```

### 4. Acceder a la aplicación

- **Dashboard**: http://localhost:5000
- **Gestión de fuentes**: Panel en el dashboard
- **API completa**: http://localhost:5000/api/

## 🔧 Gestión de Fuentes RSS

### Desde la Interfaz Web

1. Ir a http://localhost:5000
2. Sección "Gestión de Fuentes RSS"
3. **Agregar fuente**: Botón "Agregar Nueva Fuente"
4. **Editar fuente**: Botón "Editar" en cada tarjeta
5. **Eliminar fuente**: Botón "Eliminar" con confirmación
6. **Probar fuente**: Botón "Probar Fuente" para verificar funcionamiento

### Desde la API

```bash
# Listar fuentes
curl http://localhost:5000/api/sources

# Agregar nueva fuente
curl -X POST http://localhost:5000/api/sources \
  -H "Content-Type: application/json" \
  -d '{"id":"nueva","name":"Nueva Fuente","url":"https://ejemplo.com/rss","type":"rss"}'

# Actualizar fuente
curl -X PUT http://localhost:5000/api/sources/nueva \
  -H "Content-Type: application/json" \
  -d '{"name":"Fuente Actualizada","config_technique":"selenium","config_delay":5}'

# Eliminar fuente
curl -X DELETE http://localhost:5000/api/sources/nueva
```

## 🛠️ Técnicas de Web Scraping Disponibles

1. **requests**: Solicitudes HTTP básicas (por defecto)
2. **selenium**: Navegador automatizado para sitios dinámicos
3. **rotating_user_agent**: Rotación automática de User Agents
4. **delayed_requests**: Solicitudes con delays progresivos
5. **async_requests**: Solicitudes asíncronas para mejor rendimiento

### Configuración de Técnicas

```json
{
  "technique": "selenium",
  "delay": 5,
  "max_retries": 3,
  "timeout": 30
}
```

## 📊 Monitoreo y Estadísticas

### Archivos de Configuración

- `data/sources_config.json`: Configuración de fuentes RSS
- `data/noticias.csv`: Artículos recopilados
- `data/feminicidios.csv`: Casos detectados

### Logs del Sistema

```bash
# Ver logs en tiempo real
tail -f logs/sistema.log

# Análisis de errores
grep "ERROR" logs/sistema.log
```

## 🛡️ Características de Seguridad y Ética

### Verificación de robots.txt

El sistema automáticamente:
- Verifica robots.txt de cada sitio
- Respeta las restricciones de scraping
- Usa delays apropiados según las reglas

### Manejo de Errores

- **Auto-deshabilitación**: Fuentes con >5 errores se deshabilitan
- **Delays progresivos**: Incremento automático de delays tras errores
- **Rotación de técnicas**: Cambio automático si una técnica falla

### Configuración Ética

```json
{
  "respect_robots_txt": true,
  "min_delay": 2,
  "max_retries": 3,
  "auto_disable_on_errors": true
}
```

## 🔍 Estructura del Proyecto

```
├── app/                     # Aplicación Flask principal
│   ├── routes.py           # Rutas y APIs
│   └── templates/          # Plantillas HTML con gestión de fuentes
├── src/
│   ├── collection/
│   │   ├── advanced_scraper.py      # Sistema avanzado de scraping
│   │   └── data_collector.py        # Recolector básico
│   ├── analysis/           # Análisis de contenido
│   └── processing/         # Procesamiento de texto
├── data/
│   ├── sources_config.json # Configuración dinámica de fuentes
│   ├── noticias.csv       # Artículos recopilados
│   └── feminicidios.csv   # Casos detectados
├── app_docker.py          # Aplicación con todas las funcionalidades
├── demo_sistema_avanzado.py # Demostración del sistema
└── requirements.txt       # Dependencias completas
```

## ⚠️ Resolución de Problemas

### ChromeDriver no encontrado

```bash
# Verificar instalación
chromedriver --version

# Instalar manualmente
# Windows: Descargar y agregar al PATH
# Linux: sudo apt install chromium-chromedriver
# Mac: brew install chromedriver
```

### Error de dependencias

```bash
# Reinstalar dependencias
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

### Fuentes RSS no responden

1. Verificar URL en navegador
2. Comprobar robots.txt del sitio
3. Probar técnica diferente (selenium vs requests)
4. Ajustar delays y timeouts

### Puerto 5000 ocupado

```bash
# Cambiar puerto en app_docker.py
app.run(host='0.0.0.0', port=5001, debug=True)
```

## 📞 Soporte

Para problemas o mejoras:
1. Ejecutar `demo_sistema_avanzado.py` para diagnóstico
2. Revisar logs en tiempo real
3. Verificar configuración de fuentes en data/sources_config.json
4. Comprobar estado de ChromeDriver y dependencias