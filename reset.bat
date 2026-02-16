@echo off
chcp 65001 >nul
REM =============================================================================
REM Tutti - Reset Script (Windows)
REM Reset completo: detiene servicios, borra volúmenes y reconstruye
REM ⚠️  ATENCIÓN: Esto borrará TODOS los datos de la base de datos
REM =============================================================================

echo ⚠️  ATENCIÓN: Esto borrará todos los datos de la base de datos
echo.
set /p confirm="¿Estás seguro? (escribe 'si' para continuar): "

if /I not "%confirm%"=="si" (
    echo ❌ Cancelado
    pause
    exit /b 0
)

echo.
echo 🛑 Deteniendo servicios...
docker-compose down

echo.
echo 🗑️  Borrando volúmenes...
docker-compose down -v

echo.
echo 🧹 Limpiando imágenes huérfanas...
docker system prune -f

echo.
echo 🔨 Reconstruyendo imágenes...
docker-compose build --no-cache

echo.
echo 🚀 Iniciando servicios...
docker-compose up -d

echo.
echo ✅ Reset completo finalizado
echo.
echo 📋 URLs disponibles:
echo    Frontend: http://localhost:5173
echo    Backend:  http://localhost:8000
pause
