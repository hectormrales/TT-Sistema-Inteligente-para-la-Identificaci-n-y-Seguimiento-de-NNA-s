# Script de configuración inicial del Sistema Inteligente de NNA's
# Uso: .\setup.ps1

Write-Host "🔧 Configurando Sistema Inteligente para la Identificación y Seguimiento de NNA's..." -ForegroundColor Green

# Verificar Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python encontrado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: Python no está instalado o no está en el PATH" -ForegroundColor Red
    exit 1
}

# Eliminar entorno virtual anterior si existe
if (Test-Path ".\venv") {
    Write-Host "🧹 Eliminando entorno virtual anterior..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force ".\venv"
}

# Crear nuevo entorno virtual
Write-Host "📦 Creando nuevo entorno virtual..." -ForegroundColor Yellow
python -m venv venv

# Activar entorno virtual
Write-Host "🔌 Activando entorno virtual..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Actualizar pip
Write-Host "⬆️ Actualizando pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Instalar dependencias
Write-Host "📚 Instalando dependencias..." -ForegroundColor Yellow
pip install -r requirements.txt

# Descargar modelo de SpaCy
Write-Host "🧠 Descargando modelo de SpaCy para español..." -ForegroundColor Yellow
python -m spacy download es_core_news_sm

# Ejecutar pruebas
Write-Host "🧪 Ejecutando pruebas del sistema..." -ForegroundColor Yellow
python test_app.py

Write-Host "✅ ¡Configuración completada exitosamente!" -ForegroundColor Green
Write-Host "🚀 Para iniciar la aplicación ejecuta: .\start.ps1" -ForegroundColor Cyan