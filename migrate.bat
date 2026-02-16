@echo off
chcp 65001 >nul
REM =============================================================================
REM Tutti - Migrate Script (Windows)
REM Ejecuta migraciones de base de datos
REM =============================================================================

echo 🔄 Ejecutando migraciones de base de datos...

REM Verificar que el backend está corriendo
docker-compose ps backend | findstr "Up" >nul
if errorlevel 1 (
    echo ❌ Error: El backend no está corriendo
    echo    Inicia los servicios primero con: start.bat
    pause
    exit /b 1
)

REM Ejecutar creación de tablas
docker-compose exec backend python -c "from db.database import create_tables; create_tables(); print('Tablas creadas')"

echo.
echo ✅ Migraciones completadas
pause
