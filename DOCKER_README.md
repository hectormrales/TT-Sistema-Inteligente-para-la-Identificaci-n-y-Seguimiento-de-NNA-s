# 🐳 Sistema Inteligente NNA - Containerizado con Docker

## 📋 Resumen del Proyecto

Sistema completo para la **Identificación y Seguimiento de Niños, Niñas y Adolescentes (NNA)** en noticias mexicanas, ahora optimizado y containerizado con Docker para máxima portabilidad y facilidad de despliegue.

## 🚀 ¿Qué se logró con Docker?

### ✅ **Depuración Completada**
- ❌ Eliminados archivos de caché (`__pycache__/`)
- ❌ Removidas librerías problemáticas (gensim, spacy, nltk)
- ❌ Archivos de demo obsoletos eliminados
- ✅ Proyecto optimizado solo con librerías estables

### 🐳 **Containerización Completa**
- ✅ **Dockerfile** multi-stage con Python 3.11-slim
- ✅ **docker-compose.yml** con 2 servicios independientes
- ✅ **Usuario no-root** para seguridad
- ✅ **Health checks** automáticos
- ✅ **Volúmenes** para persistencia de datos

### 🏗️ **Arquitectura Docker**

```
📦 nna-sistema/
├── 🔬 nna-analyzer     (Backend de análisis automático)
├── 🌐 nna-webapp       (Interfaz web en puerto 5000)
└── 🔗 nna-network      (Red interna Docker)
```

## 📊 **Resultados del Análisis**

### 🎯 **Pipeline de 7 Pasos Implementado**
1. **Recolección RSS** → Noticias mexicanas en tiempo real
2. **Almacenamiento CSV** → Persistencia en `/data/noticias.csv`
3. **Vectorización TF-IDF** → Análisis de contenido textual
4. **Modelado LDA** → 5 tópicos principales identificados
5. **Clustering K-Means** → 4 grupos de noticias similares
6. **Análisis de Similitud** → Scoring de relevancia
7. **Detección NNA** → 143 sinónimos especializados

### 📈 **Métricas de Éxito**
- **146 noticias** procesadas en demo
- **41 casos NNA** identificados (28.1% tasa de detección)
- **4 clusters** de agrupación automática
- **5 tópicos** principales extraídos
- **143 sinónimos** en diccionario especializado

## 🛠️ **Comandos Docker**

### 🏃 **Ejecutar Sistema Completo**
```bash
docker-compose up -d
```

### 📊 **Ver Estado de Contenedores**
```bash
docker-compose ps
```

### 📝 **Ver Logs en Tiempo Real**
```bash
# Todos los servicios
docker-compose logs -f

# Solo analizador
docker-compose logs -f nna-analyzer

# Solo webapp
docker-compose logs -f nna-webapp
```

### 🔄 **Actualizar y Reconstruir**
```bash
docker-compose up --build -d
```

### 🛑 **Detener Sistema**
```bash
docker-compose down
```

### 🗑️ **Limpiar Completamente**
```bash
docker-compose down --volumes --rmi all
```

## 🌐 **Acceso a la Aplicación**

- **Dashboard Web**: [http://localhost:5000](http://localhost:5000)
- **API Estadísticas**: [http://localhost:5000/api/stats](http://localhost:5000/api/stats)
- **API Noticias**: [http://localhost:5000/api/noticias](http://localhost:5000/api/noticias)
- **API Búsqueda**: [http://localhost:5000/api/search?q=feminicidio](http://localhost:5000/api/search?q=feminicidio)

## 📁 **Estructura de Archivos Docker**

```
📂 Proyecto/
├── 🐳 Dockerfile              # Configuración de imagen
├── 🐳 docker-compose.yml      # Orquestación de servicios
├── 🐳 .dockerignore           # Archivos excluidos
├── 🐳 demo_docker.py          # Analizador automático
├── 🐳 app_docker.py           # Aplicación web Flask
├── 📋 requirements.txt        # Dependencias optimizadas
└── 🎨 templates/
    └── dashboard_docker.html   # Interfaz web moderna
```

## 🔧 **Configuración Interna**

### 🐍 **Python Environment**
- **Base**: `python:3.11-slim`
- **Usuario**: `appuser` (no-root)
- **Directorio**: `/app`
- **Puerto**: `5000`

### 📦 **Dependencias Core**
```
pandas==2.2.2          # Análisis de datos
scikit-learn==1.4.2    # Machine Learning
Flask==3.0.3           # Web framework
requests==2.31.0       # HTTP client
beautifulsoup4==4.12.2 # Web scraping
schedule==1.2.2        # Tareas programadas
```

### ⏰ **Programación Automática**
- **Recolección**: Cada 6 horas
- **Análisis**: Cada 12 horas
- **Inicio**: Ejecución completa al arrancar

## 🎯 **Funcionalidades del Dashboard**

### 📊 **Estadísticas en Tiempo Real**
- Total de noticias procesadas
- Casos NNA identificados
- Número de clusters formados
- Tópicos principales extraídos

### 🔍 **Búsqueda Inteligente**
- Búsqueda con sinónimos automáticos
- Filtrado por casos NNA únicamente
- Paginación de resultados
- Destacado de coincidencias

### 📈 **Análisis Avanzado**
- Scoring de similitud por noticia
- Clasificación automática en clusters
- Identificación de tópicos principales
- Metadatos enriquecidos

### 💾 **Exportación de Datos**
- Descarga CSV completa
- API REST para integración
- Datos persistentes en volúmenes Docker

## 🔐 **Seguridad y Mejores Prácticas**

### 🛡️ **Configuración Segura**
- Contenedores ejecutados como usuario no-root
- Imagen base mínima (slim)
- Dependencias fijas con versiones específicas
- Red interna aislada

### 📊 **Monitoreo**
- Health checks automáticos
- Logs estructurados con timestamps
- Reinicio automático en caso de falla
- Métricas de performance disponibles

## 🚀 **Próximos Pasos**

1. **Producción**: Usar `docker-compose.prod.yml` con NGINX
2. **Escalabilidad**: Añadir más nodos de análisis
3. **Monitoreo**: Integrar Prometheus + Grafana  
4. **CI/CD**: Pipelines automáticos con GitHub Actions
5. **Base de Datos**: Migrar de CSV a PostgreSQL

## 📞 **Soporte**

Para troubleshooting o mejoras:
1. Verificar logs: `docker-compose logs -f`
2. Revisar estado: `docker-compose ps`
3. Reconstruir: `docker-compose up --build -d`
4. Reset completo: `docker-compose down --volumes`

---
**✅ Proyecto completamente containerizado y listo para producción**