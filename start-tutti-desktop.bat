@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Tutti - Desktop Mode
color 0B

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "FRONTEND_DIST=%FRONTEND%\dist"
set "VENV=%ROOT%.venv"
set "VENV_PYTHON=%VENV%\Scripts\python.exe"

echo.
echo  ========================================
echo       TUTTI - Desktop Mode
echo  ========================================
echo.
echo  Este modo ejecuta:
echo   1) Backend FastAPI local
echo   2) Frontend compilado servido por backend
echo   3) Navegador en http://127.0.0.1:8000
echo.

echo  [1/4] Checking Python virtualenv...
if not exist "%VENV_PYTHON%" (
    echo        Creating virtual environment...
    python -m venv "%VENV%"
)

"%VENV_PYTHON%" -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo        Detected broken virtual environment, recreating...
    rmdir /S /Q "%VENV%" >nul 2>&1
    python -m venv "%VENV%"
)

echo  [2/4] Installing backend dependencies...
"%VENV_PYTHON%" -m pip install -q --upgrade pip
"%VENV_PYTHON%" -m pip install -q -r "%BACKEND%\requirements.txt"
if %errorlevel% neq 0 (
    echo        ERROR: Could not install backend dependencies.
    pause
    exit /b 1
)

echo  [3/4] Checking frontend dist...
if not exist "%FRONTEND_DIST%\index.html" (
    echo        Frontend dist not found. Building...
    pushd "%FRONTEND%"
    call npm install --silent
    if %errorlevel% neq 0 (
        popd
        echo        ERROR: npm install failed.
        pause
        exit /b 1
    )
    call npm run build
    if %errorlevel% neq 0 (
        popd
        echo        ERROR: npm run build failed.
        pause
        exit /b 1
    )
    popd
)
echo        Frontend dist OK.

echo  [4/4] Starting local desktop server...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000.*LISTENING"') do taskkill /F /PID %%a >nul 2>&1

set "SERVE_FRONTEND_DIST=true"
set "FRONTEND_DIST_DIR=%FRONTEND_DIST%"
set "APP_RUNTIME_MODE=stable"
set "CELERY_ENABLED=false"
set "WEBSOCKET_ENABLED=true"
set "USE_DATABASE=true"
set "DATABASE_URL=sqlite:///./data/tutti_desktop.db"
set "CORS_ORIGINS=http://127.0.0.1:8000,http://localhost:8000"

if not exist "%BACKEND%\data" mkdir "%BACKEND%\data" >nul 2>&1

echo @echo off > "%TEMP%\start_tutti_desktop_backend.bat"
echo cd /d "%BACKEND%" >> "%TEMP%\start_tutti_desktop_backend.bat"
echo set "SERVE_FRONTEND_DIST=%SERVE_FRONTEND_DIST%" >> "%TEMP%\start_tutti_desktop_backend.bat"
echo set "FRONTEND_DIST_DIR=%FRONTEND_DIST_DIR%" >> "%TEMP%\start_tutti_desktop_backend.bat"
echo set "APP_RUNTIME_MODE=%APP_RUNTIME_MODE%" >> "%TEMP%\start_tutti_desktop_backend.bat"
echo set "CELERY_ENABLED=%CELERY_ENABLED%" >> "%TEMP%\start_tutti_desktop_backend.bat"
echo set "WEBSOCKET_ENABLED=%WEBSOCKET_ENABLED%" >> "%TEMP%\start_tutti_desktop_backend.bat"
echo set "USE_DATABASE=%USE_DATABASE%" >> "%TEMP%\start_tutti_desktop_backend.bat"
echo set "DATABASE_URL=%DATABASE_URL%" >> "%TEMP%\start_tutti_desktop_backend.bat"
echo set "CORS_ORIGINS=%CORS_ORIGINS%" >> "%TEMP%\start_tutti_desktop_backend.bat"
echo "%VENV_PYTHON%" -m uvicorn main:app --host 127.0.0.1 --port 8000 >> "%TEMP%\start_tutti_desktop_backend.bat"

start "Tutti-Desktop-Backend" cmd /k "%TEMP%\start_tutti_desktop_backend.bat"

echo        Waiting backend health...
set "BACKEND_READY=0"
for /L %%i in (1,1,30) do (
    powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 set "BACKEND_READY=1"
    if "!BACKEND_READY!"=="1" goto :desktop_ready
    ping -n 2 127.0.0.1 >nul
)

echo        WARNING: backend health check timed out.
goto :open_browser

:desktop_ready
echo        Backend health OK.

:open_browser
start http://127.0.0.1:8000
echo.
echo  Desktop mode running at http://127.0.0.1:8000
echo  Press any key to stop...
pause >nul

echo.
echo  Stopping desktop mode...
del "%TEMP%\start_tutti_desktop_backend.bat" 2>nul
taskkill /FI "WINDOWTITLE eq Tutti-Desktop-Backend*" /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000.*LISTENING"') do taskkill /F /PID %%a >nul 2>&1
echo  Done.
