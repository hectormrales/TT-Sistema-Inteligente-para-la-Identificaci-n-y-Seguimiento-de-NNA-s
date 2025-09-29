# Script para iniciar el Sistema Inteligente de NNA's
# Uso: .\start.ps1

Write-Host "🚀 Iniciando Sistema Inteligente para la Identificación y Seguimiento de NNA's..." -ForegroundColor Green

# Verificar que existe el entorno virtual
if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "❌ Error: No se encuentra el entorno virtual. Ejecuta primero setup.ps1" -ForegroundColor Red
    exit 1
}

# Activar entorno virtual e iniciar aplicación
Write-Host "📦 Activando entorno virtual..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

Write-Host "🌐 Iniciando servidor Flask..." -ForegroundColor Yellow
Write-Host "✅ La aplicación estará disponible en: http://127.0.0.1:5000/dashboard" -ForegroundColor Green
Write-Host "⚡ Para detener la aplicación presiona Ctrl+C" -ForegroundColor Cyan

python run.py