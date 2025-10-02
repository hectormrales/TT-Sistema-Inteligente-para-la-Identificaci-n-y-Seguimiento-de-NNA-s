# build_docker_simple.ps1
# Script simplificado para construir y ejecutar con Docker

Write-Host "Construyendo Sistema Avanzado con Docker..." -ForegroundColor Green

# Variables
$IMAGE_NAME = "nna-sistema-avanzado"
$CONTAINER_NAME = "nna-container-avanzado"
$PORT = 5000

# Limpiar contenedores anteriores
Write-Host "Limpiando contenedores anteriores..." -ForegroundColor Yellow
docker stop $CONTAINER_NAME 2>$null
docker rm $CONTAINER_NAME 2>$null
docker rmi $IMAGE_NAME 2>$null

# Construir imagen
Write-Host "Construyendo imagen Docker..." -ForegroundColor Yellow
docker build -t $IMAGE_NAME .

if ($LASTEXITCODE -eq 0) {
    Write-Host "Imagen construida exitosamente" -ForegroundColor Green
    
    # Ejecutar contenedor
    Write-Host "Ejecutando contenedor..." -ForegroundColor Yellow
    docker run -d --name $CONTAINER_NAME -p ${PORT}:5000 -v ${PWD}/data:/app/data $IMAGE_NAME
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Contenedor iniciado exitosamente" -ForegroundColor Green
        Write-Host "Aplicacion disponible en: http://localhost:$PORT" -ForegroundColor Cyan
        
        # Mostrar logs
        Write-Host "Logs iniciales:" -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        docker logs $CONTAINER_NAME --tail 10
        
        Write-Host "Comandos utiles:" -ForegroundColor Cyan
        Write-Host "  Ver logs: docker logs -f $CONTAINER_NAME"
        Write-Host "  Acceder: docker exec -it $CONTAINER_NAME /bin/bash"
        Write-Host "  Detener: docker stop $CONTAINER_NAME"
        Write-Host "  Demo: docker exec $CONTAINER_NAME python demo_docker.py"
        
    } else {
        Write-Host "Error ejecutando contenedor" -ForegroundColor Red
    }
} else {
    Write-Host "Error construyendo imagen" -ForegroundColor Red
}

Write-Host "Script completado" -ForegroundColor Green