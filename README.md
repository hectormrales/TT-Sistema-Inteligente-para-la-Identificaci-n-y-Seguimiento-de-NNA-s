# Sistema Inteligente para Identificación y Seguimiento de NNA

## 🎯 **Descripción del Proyecto**

Sistema automatizado para detectar y analizar menciones de **Niños, Niñas y Adolescentes (NNA)** en medios digitales mexicanos, utilizando técnicas de Machine Learning y procesamiento de lenguaje natural.

## 🚀 **Inicio Rápido con Docker**

### **Prerrequisitos**
- Docker Desktop instalado
- Puerto 5000 disponible

### **Ejecutar Sistema**
```bash
# Clonar e ingresar al directorio
cd /ruta/del/proyecto

# Iniciar sistema completo
docker-compose up -d

# Verificar estado
docker-compose ps

# Acceder al dashboard
# Abrir: http://localhost:5000
```

### **Comandos Útiles**
```bash
# Ver logs en vivo
docker-compose logs -f

# Detener sistema
docker-compose down

# Reiniciar con reconstrucción
docker-compose up --build -d
```

## 📊 **Funcionalidades**

### ✅ **Análisis Automático**
- **Recolección RSS** de 8 fuentes mexicanas cada 6 horas
- **Procesamiento NLP** completo con 7 etapas
- **Detección NNA** con diccionario de sinónimos especializado
- **Clustering** automático de noticias similares
- **Análisis de tópicos** con LDA

### ✅ **Interfaz Web**
- **Dashboard interactivo** con Bootstrap
- **Búsqueda inteligente** con expansión de sinónimos
- **Estadísticas en tiempo real**
- **Exportación CSV** de resultados
- **Paginación** automática de noticias

### ✅ **API REST**
```bash
GET  /api/stats           # Estadísticas generales
GET  /api/noticias        # Lista paginada de noticias
GET  /api/search?q=texto  # Búsqueda con sinónimos
POST /api/analyze         # Ejecutar análisis completo
GET  /api/export/csv      # Descargar datos CSV
GET  /api/health          # Estado del sistema
```

## 🏗️ **Arquitectura del Sistema**

### **Componentes Docker**
```
📦 Sistema Multi-Container
├── 🔬 nna-analyzer    # Análisis automático en background
├── 🌐 nna-webapp      # Interfaz web (puerto 5000)
└── 🔗 nna-network     # Red interna Docker
```

### **Pipeline de Análisis (7 Etapas)**
```
1️⃣ Recolección RSS     → Feeds de noticias mexicanas
2️⃣ Almacenamiento CSV  → Persistencia de datos
3️⃣ Vectorización TF-IDF → Representación numérica
4️⃣ Modelado LDA        → Identificación de tópicos
5️⃣ Clustering K-Means  → Agrupación por similitud
6️⃣ Análisis Similitud  → Cálculo de distancias
7️⃣ Detección NNA       → Clasificación especializada
```

## 📁 **Estructura del Proyecto**

```
📁 sistema-nna/
├── 🐳 docker-compose.yml      # Orquestación de contenedores
├── 🐳 Dockerfile              # Configuración de imagen
├── ⚙️  app_docker.py           # Aplicación web Flask
├── 🤖 demo_docker.py           # Analizador automático
├── ⚙️  config.py               # Configuración del sistema
├── 📋 requirements.txt         # Dependencias Python
├── 📁 src/
│   ├── analysis/
│   │   ├── simplified_analyzer.py    # Motor de análisis principal
│   │   └── synonym_dictionary.py     # Diccionario NNA especializado
│   └── collection/
│       └── data_collector.py         # Recolector RSS
├── 📁 app/
│   ├── __init__.py
│   └── templates/
│       └── dashboard_docker.html     # Interfaz web moderna
└── 📁 data/
    ├── noticias.csv             # Datos procesados
    └── synonym_dictionary.json  # Diccionario de sinónimos
```

## 🔧 **Tecnologías Utilizadas**

### **Core Analysis**
- **pandas 2.2.2** - Manipulación de datos
- **scikit-learn 1.4.2** - Machine Learning (TF-IDF, LDA, K-Means)
- **numpy** - Cálculos numéricos

### **Web Scraping**
- **requests 2.31.0** - Peticiones HTTP
- **beautifulsoup4 4.12.2** - Parsing HTML/XML
- **lxml 5.3.0** - Procesador XML rápido

### **Web Application**
- **Flask 3.0.3** - Framework web
- **Flask-CORS 4.0.1** - Cross-origin requests

### **Automation**
- **schedule 1.2.2** - Tareas programadas
- **Docker** - Containerización

## 📊 **Resultados del Análisis**

### **Métricas Actuales**
- 📰 **146 noticias** recolectadas y procesadas
- 👶 **41 casos NNA** detectados (28.1% tasa de detección)
- 🏷️  **4 clusters** de noticias similares generados
- 🎯 **5 tópicos** principales identificados

### **Fuentes RSS Monitoreadas**
- La Jornada (Política)
- Proceso
- Aristegui Noticias
- Animal Político
- Sin Embargo
- Forbes México
- El Sol de México
- El Financiero

## 🔍 **Diccionario NNA Especializado**

Basado en vocabularios oficiales:
- **UN Women** - Glosario de género
- **CEPAL** - Terminología especializada
- **INMUJERES** - Vocabulario institucional
- **143 términos** relacionados con NNA y violencia de género

## 🚨 **Solución de Problemas**

### **Error: Puerto 5000 ocupado**
```bash
# Encontrar proceso usando el puerto
netstat -ano | findstr :5000

# Cambiar puerto en docker-compose.yml
ports:
  - "5001:5000"  # Usar puerto 5001 en su lugar
```

### **Error: Docker no responde**
```bash
# Reiniciar Docker Desktop
# Verificar que está ejecutándose
docker --version

# Limpiar contenedores
docker-compose down --volumes
docker system prune -f
```

### **Ver logs detallados**
```bash
# Logs del analizador
docker-compose logs nna-analyzer

# Logs de la webapp
docker-compose logs nna-webapp

# Todos los logs
docker-compose logs
```

---

## 🚀 **Sistema completamente automatizado y listo para producción**

Para soporte técnico, verificar logs del sistema y estado de contenedores Docker.