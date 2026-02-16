@echo off
chcp 65001 >nul
REM =============================================================================
REM Tutti - Logs Script (Windows)
REM Muestra logs de los servicios

echo 📋 Mostrando logs de todos los servicios (Ctrl+C para salir)...
docker-compose logs -f --tail=100
