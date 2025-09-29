# Sistema Inteligente para la Identificación y Seguimiento de NNA's

##  Descripción del Proyecto
Sistema web desarrollado en Flask para la **identificación automática de menciones de Niños, Niñas y Adolescentes (NNA)** en noticias, especialmente en casos relacionados con femicidios. El sistema utiliza técnicas de procesamiento de lenguaje natural y web scraping para recopilar, analizar y visualizar información relevante.

##  Funcionalidades Principales

-  **Detección automática de menciones de menores** en textos de noticias
-  **Recolección automática de noticias** desde feeds RSS
-  **Dashboard web interactivo** para visualización de resultados
-  **Resaltado visual** de casos que involucran menores
-  **Estadísticas en tiempo real** del análisis
-  **API REST** para integración con otros sistemas

##  Tecnologías Utilizadas

- **Backend**: Flask (Python)
- **Procesamiento de datos**: Pandas
- **Web scraping**: BeautifulSoup4, Requests
- **Machine Learning**: Scikit-learn (TF-IDF, K-Means, LDA)
- **Frontend**: HTML, CSS, JavaScript
- **Almacenamiento**: CSV (con opción a base de datos)

##  Estado Actual - FUNCIONAL 

La aplicación está **completamente funcional** con las siguientes características implementadas:

- **Servidor Flask ejecutándose correctamente**
- **Dashboard web accesible y funcional**
- **Recolección de noticias desde RSS feeds**
- **Detección de menciones de menores operativa**
- **Interfaz de usuario intuitiva**
- **Sistema de pruebas implementado**

##  Inicio Rápido

### Opción 1: Scripts automatizados (Recomendado)
```powershell
# Para configuración inicial (solo la primera vez):
.\setup.ps1

# Para iniciar la aplicación:
.\start.ps1
```

### Opción 2: Manual
```powershell
# Activar entorno virtual
.\venv\Scripts\Activate.ps1

# Ejecutar aplicación
python run.py
```

### Acceso al sistema:
1. **Dashboard principal**: `http://127.0.0.1:5000/dashboard`
2. **Recolectar noticias**: Hacer clic en "Recolectar Noticias"
3. **Ver resultados**: Los casos con menores aparecerán resaltados

##  Estructura del Proyecto

```
TT-1-Sistema-Inteligente-para-la-Identificaci-n-y-Seguimiento-de-NNA-s/
│
├──  run.py                      # Punto de entrada de la aplicación
├──  config.py                   # Configuración general
├──  requirements.txt            # Dependencias
├──  test_app.py                # Script de pruebas
│
├──  app/                        # Aplicación Flask
│   ├── __init__.py               # Inicialización
│   ├── routes.py                 # Rutas y endpoints
│   └── templates/
│       └── dashboard.html        # Interfaz web
│
├──  src/                       # Código fuente principal
│   ├── collection/
│   │   └── data_collector.py     # Recolección de noticias
│   ├── processing/
│   │   └── text_processor.py     # Procesamiento de texto
│   ├── analysis/
│   │   └── news_analyzer.py      # Análisis con ML
│   └── utils/
│       └── file_handler.py       # Manejo de archivos
│
└──  data/                      # Datos procesados
    └── noticias_analizadas.csv   # Resultados del análisis
```

##  Configuración

### RSS Feeds (config.py)
```python
RSS_FEEDS = [
    'https://www.jornada.com.mx/rss/politica.xml',
    'https://www.proceso.com.mx/feed',
    'https://aristeguinoticias.com/feed/',
]
```

### Palabras Clave para Detección de Menores
```python
keywords = [
    'hijo', 'hija', 'hijos', 'hijas', 
    'menor', 'menores', 'niño', 'niña', 
    'adolescente', 'huérfano', 'huérfana'
]
```

##  API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/dashboard` | Dashboard principal |
| POST | `/collect-news` | Recolectar y analizar noticias |
| GET | `/api/status` | Estado del sistema |

##  Pruebas del Sistema

Ejecutar suite de pruebas:
```bash
.\.venv\Scripts\python.exe .\test_app.py
```

**Resultados esperados**:
-  Detección de menciones de menores
-  Procesamiento de texto
-  Carga de datos CSV

##  Problemas Solucionados

1. ** Dependencias faltantes** → ✅ Instaladas en entorno virtual
2. ** Error con spaCy** → ✅ Implementado procesamiento alternativo
3. ** Archivo CSV inexistente** → ✅ Creación automática con datos de ejemplo
4. ** Rutas no encontradas** → ✅ Sistema de rutas corregido

##  Próximas Mejoras

- [ ] Integración completa con spaCy para NLP avanzado
- [ ] Base de datos PostgreSQL/SQLite
- [ ] Clustering automático con ML
- [ ] Sistema de alertas en tiempo real
- [ ] API para exportación de reportes
- [ ] Autenticación y autorización

##  Documentación Adicional

- Ver `COMO_EJECUTAR.md` para instrucciones detalladas de instalación
- Los logs de la aplicación aparecen en la consola durante la ejecución

##  Contribución

Para contribuir al proyecto:
1. Fork del repositorio
2. Crear rama de feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit de cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

##  Licencia

Este proyecto está bajo una licencia de uso académico/educativo.

---

** Objetivo**: Contribuir a la protección de menores mediante tecnología de análisis automatizado de noticias.