@echo off
chcp 65001 >nul
REM =============================================================================
REM Tutti - Start Script (Windows)
REM Inicia todos los servicios en modo desarrollo
REM =============================================================================

echo ╔════════════════════════════════════════════════════════════╗
echo ║                  🚌 TUTTI - START                          ║
echo ║           Iniciando servicios de desarrollo                ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Verificar que Docker está instalado
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Docker no está instalado
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Docker Compose no está instalado
    exit /b 1
)

echo 🔍 Verificando estado de los servicios...
echo.

REM Detener servicios existentes si hay conflictos
docker-compose down --remove-orphans >nul 2>&1

echo 🔨 Construyendo imágenes (si es necesario)...
docker-compose build --parallel

echo.
echo 🚀 Iniciando servicios...
docker-compose up -d

echo.
echo ⏳ Esperando a que los servicios estén listos...
echo.

REM Esperar unos segundos para que los servicios inicien
timeout /t 5 /nobreak >nul

echo ╔════════════════════════════════════════════════════════════╗
echo ║              ✅ SERVICIOS INICIADOS                        ║
echo ╠════════════════════════════════════════════════════════════╣
echo ║  🌐 Frontend:    http://localhost:5173                     ║
echo ║  🔌 Backend API: http://localhost:8000                     ║
echo ║  📚 API Docs:    http://localhost:8000/docs                ║
echo ║  🔑 Health:      http://localhost:8000/health              ║
echo ║  🐘 PostgreSQL:  localhost:5432                            ║
echo ║  ⚡ Redis:       localhost:6379                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo 📋 Comandos útiles:
echo    docker-compose logs -f [servicio]  - Ver logs
echo    docker-compose down                - Detener todo
echo    docker-compose down -v             - Reset completo
echo.
echo 🎉 ¡Tutti está listo para desarrollar!
pause
