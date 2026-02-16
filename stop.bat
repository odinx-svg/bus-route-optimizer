@echo off
chcp 65001 >nul
REM =============================================================================
REM Tutti - Stop Script (Windows)
REM Detiene todos los servicios
REM =============================================================================

echo 🛑 Deteniendo servicios de Tutti...
docker-compose down

echo.
echo ✅ Todos los servicios han sido detenidos
pause
