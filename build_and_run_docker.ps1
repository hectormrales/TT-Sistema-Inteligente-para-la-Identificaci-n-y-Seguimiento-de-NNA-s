# build_and_run_docker.ps1
# Script para construir y ejecutar el sistema avanzado con Docker

Write-Host "🚀 CONSTRUYENDO Y EJECUTANDO SISTEMA AVANZADO CON DOCKER" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green

# Variables
$IMAGE_NAME = "nna-sistema-avanzado"
$CONTAINER_NAME = "nna-container-avanzado"
$PORT = 5000

# Función para mostrar estado
function Show-Status {
    param([string]$Message, [string]$Color = "Yellow")
    Write-Host "`n🔄 $Message" -ForegroundColor $Color
}

# Función para mostrar éxito
function Show-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

# Función para mostrar error
function Show-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

# Paso 1: Limpiar contenedores anteriores
Show-Status "Limpiando contenedores anteriores..."
docker stop $CONTAINER_NAME 2>$null
docker rm $CONTAINER_NAME 2>$null
docker rmi $IMAGE_NAME 2>$null

# Paso 2: Construir imagen
Show-Status "Construyendo imagen Docker..."
$buildResult = docker build -t $IMAGE_NAME . 2>&1

if ($LASTEXITCODE -eq 0) {
    Show-Success "Imagen construida exitosamente"
} else {
    Show-Error "Error construyendo imagen"
    Write-Host $buildResult -ForegroundColor Red
    exit 1
}

# Paso 3: Ejecutar contenedor
Show-Status "Ejecutando contenedor..."
$runResult = docker run -d --name $CONTAINER_NAME -p ${PORT}:5000 -v ${PWD}/data:/app/data $IMAGE_NAME

if ($LASTEXITCODE -eq 0) {
    Show-Success "Contenedor iniciado exitosamente"
    
    # Mostrar información del contenedor
    Write-Host "`n📊 INFORMACIÓN DEL CONTENEDOR" -ForegroundColor Cyan
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host "🏷️  Imagen: $IMAGE_NAME" -ForegroundColor White
    Write-Host "📦 Contenedor: $CONTAINER_NAME" -ForegroundColor White
    Write-Host "🌐 URL: http://localhost:$PORT" -ForegroundColor White
    Write-Host "💾 Datos persistentes: ./data" -ForegroundColor White
    
    # Esperar que la aplicación inicie
    Show-Status "Esperando que la aplicación inicie..."
    Start-Sleep -Seconds 10
    
    # Verificar logs
    Write-Host "`n📋 LOGS INICIALES:" -ForegroundColor Cyan
    docker logs $CONTAINER_NAME --tail 20
    
    # Probar conectividad
    Show-Status "Probando conectividad..."
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$PORT" -UseBasicParsing -TimeoutSec 10
        if ($response.StatusCode -eq 200) {
            Show-Success "Aplicación web accesible"
        } else {
            Show-Error "Aplicación no responde correctamente"
        }
    } catch {
        Show-Error "No se pudo conectar a la aplicación: $_"
    }
    
    # Comandos útiles
    Write-Host "`n🛠️  COMANDOS ÚTILES:" -ForegroundColor Cyan
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host "Ver logs en tiempo real:" -ForegroundColor White
    Write-Host "   docker logs -f $CONTAINER_NAME" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Acceder al contenedor:" -ForegroundColor White
    Write-Host "   docker exec -it $CONTAINER_NAME /bin/bash" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Ejecutar demostración:" -ForegroundColor White
    Write-Host "   docker exec $CONTAINER_NAME python demo_docker.py" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Detener contenedor:" -ForegroundColor White
    Write-Host "   docker stop $CONTAINER_NAME" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Reiniciar contenedor:" -ForegroundColor White
    Write-Host "   docker restart $CONTAINER_NAME" -ForegroundColor Gray
    
    # Información de acceso
    Write-Host "`n🌐 ACCESO A LA APLICACIÓN:" -ForegroundColor Cyan
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host "Dashboard principal: http://localhost:$PORT" -ForegroundColor White
    Write-Host "Gestión de fuentes: http://localhost:$PORT (sección Gestión de Fuentes RSS)" -ForegroundColor White
    Write-Host "API de fuentes: http://localhost:$PORT/api/sources" -ForegroundColor White
    Write-Host "API de análisis: http://localhost:$PORT/api/analyze" -ForegroundColor White
    
} else {
    Show-Error "Error ejecutando contenedor"
    Write-Host $runResult -ForegroundColor Red
    exit 1
}

Write-Host "`n🎉 SISTEMA AVANZADO LISTO CON DOCKER!" -ForegroundColor Green
Write-Host "Accede a http://localhost:$PORT para usar el sistema" -ForegroundColor Yellow