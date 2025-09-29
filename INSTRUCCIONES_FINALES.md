# 🚀 Guía Completa de Ejecución - Sistema de NNA's

## ✅ ESTADO ACTUAL: PROYECTO FUNCIONAL

¡El proyecto está **100% operativo**! Todas las dependencias han sido resueltas y la aplicación funciona correctamente.

---

## 🎯 Resumen de lo que se configuró:

### ✅ Entorno Virtual Configurado:
- Eliminado entorno virtual anterior problemático
- Creado nuevo entorno virtual limpio (`venv/`)
- Todas las dependencias instaladas correctamente

### ✅ Dependencias Resueltas:
- **Flask 2.3.3** - Servidor web ✅
- **pandas 2.2.2** - Manejo de datos ✅  
- **spaCy 3.8.7** - Procesamiento de lenguaje natural ✅
- **scikit-learn 1.5.2** - Machine Learning ✅
- **beautifulsoup4** - Web scraping ✅
- **requests** - HTTP requests ✅
- **Modelo spaCy español** descargado ✅

### ✅ Aplicación Probada:
- ✅ Flask se ejecuta en `http://127.0.0.1:5000`
- ✅ Dashboard accesible en `/dashboard`
- ✅ Sistema de pruebas funcional (142 noticias cargadas)
- ✅ Detección de menores operativa

---

## 🚀 INSTRUCCIONES DE EJECUCIÓN

### Método 1: Scripts Automatizados (MÁS FÁCIL)

```powershell
# Para iniciar la aplicación:
.\start.ps1
```

### Método 2: Manual

```powershell
# 1. Activar entorno virtual
.\venv\Scripts\Activate.ps1

# 2. Ejecutar aplicación  
python run.py

# 3. Abrir navegador en: http://127.0.0.1:5000/dashboard
```

### Método 3: Directo (sin activar entorno)

```powershell
.\venv\Scripts\python.exe run.py
```

---

## 🌐 ACCESO AL SISTEMA

Una vez ejecutado, la aplicación estará disponible en:

- **Dashboard Principal**: http://127.0.0.1:5000/dashboard
- **API Status**: http://127.0.0.1:5000/api/status
- **Health Check**: http://127.0.0.1:5000/health

---

## 🔧 FUNCIONALIDADES DISPONIBLES

### En el Dashboard Web:
1. **Ver noticias analizadas** (142 noticias precargadas)
2. **Recolectar nuevas noticias** (botón "Recolectar Noticias")
3. **Ver casos con menores resaltados** automáticamente
4. **Estadísticas en tiempo real**

### API Endpoints:
- `POST /collect-news` - Recolectar nuevas noticias
- `GET /api/status` - Estado del sistema
- `GET /dashboard` - Interfaz principal

---

## 🧪 VERIFICAR FUNCIONAMIENTO

Para probar que todo funciona:

```powershell
# Ejecutar suite de pruebas
.\venv\Scripts\python.exe test_app.py
```

**Resultado esperado:**
```
✅ CSV cargado exitosamente: 142 filas
✅ Procesamiento de texto funcionando
✅ Detección de menores operativa
✅ Pruebas completadas!
```

---

## ⚡ COMANDOS RÁPIDOS

```powershell
# Iniciar aplicación (recomendado)
.\start.ps1

# Ver logs en tiempo real
.\venv\Scripts\python.exe run.py

# Ejecutar pruebas
.\venv\Scripts\python.exe test_app.py

# Parar aplicación: Ctrl+C
```

---

## 🆘 SOLUCIÓN DE PROBLEMAS

### ❌ Error: "No module named 'pandas'"
**Solución**: Usar `.\venv\Scripts\python.exe` en lugar de solo `python`

### ❌ Puerto 5000 ocupado
**Solución**: Cambiar puerto en `run.py`:
```python
app.run(debug=True, port=8000)
```

### ❌ Error de permisos en PowerShell
**Solución**: 
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## 📊 DATOS DEL SISTEMA

- **Noticias precargadas**: 142 
- **Fuentes RSS configuradas**: 3
- **Modelos ML**: TF-IDF, K-Means
- **Idioma del modelo NLP**: Español (es_core_news_sm)

---

## 🎉 ¡LISTO PARA USAR!

El sistema está completamente funcional. Solo ejecuta `.\start.ps1` y comienza a usar la aplicación en `http://127.0.0.1:5000/dashboard`.

**Características principales funcionando:**
- ✅ Servidor Flask estable
- ✅ Detección automática de menores
- ✅ Dashboard web interactivo  
- ✅ Recolección de noticias RSS
- ✅ Análisis de texto con ML
- ✅ Sistema de pruebas completo