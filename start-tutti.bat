@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Tutti - Fleet Optimizer
color 0B

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "VENV=%ROOT%.venv"
set "VENV_PYTHON=%VENV%\Scripts\python.exe"

echo.
echo  ========================================
echo       TUTTI - Fleet Optimizer
echo       Quick Start Script v2.3
echo  ========================================
echo.

echo  [1/5] Checking Python...
if not exist "%VENV_PYTHON%" (
    echo        Creating virtual environment...
    python -m venv "%VENV%"
)

:: Repair broken venv launchers if project path changed
"%VENV_PYTHON%" -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo        Detected broken virtual environment, recreating...
    rmdir /S /Q "%VENV%" >nul 2>&1
    python -m venv "%VENV%"
)

for /f "tokens=2 delims= " %%v in ('"%VENV_PYTHON%" --version 2^>^&1') do echo        Python %%v
echo.

echo  [2/5] Checking Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo        ERROR: Node.js not found!
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo        Node %%v
echo.

echo  [3/5] Installing dependencies...
"%VENV_PYTHON%" -m pip install -q --upgrade pip
"%VENV_PYTHON%" -m pip install -q -r "%BACKEND%\requirements.txt"
if %errorlevel% neq 0 (
    echo        ERROR: Backend dependencies could not be updated
    pause
    exit /b 1
)
"%VENV_PYTHON%" -c "import reportlab, httpx, pulp, websockets, wsproto; from PIL import Image" >nul 2>&1 || "%VENV_PYTHON%" -m pip install -q reportlab pillow httpx pulp websockets wsproto
if %errorlevel% neq 0 (
    echo        ERROR: Critical Python dependencies check failed
    pause
    exit /b 1
)
echo        Dependencies OK
echo.

echo  [4/5] Syncing frontend dependencies...
if not exist "%BACKEND%\main.py" echo        WARNING: backend\main.py not found
if not exist "%BACKEND%\models.py" echo        WARNING: backend\models.py not found
if not exist "%BACKEND%\optimizer_v6.py" echo        WARNING: backend\optimizer_v6.py not found

echo        Running npm install to apply package updates...
pushd "%FRONTEND%"
call npm install --silent
if %errorlevel% neq 0 (
    popd
    echo        ERROR: Frontend dependencies could not be updated
    pause
    exit /b 1
)
popd
echo        Frontend dependencies OK
echo.

echo  [5/5] Starting servers...
echo.

:: Kill old processes
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5173"') do taskkill /F /PID %%a >nul 2>&1

:: Start Backend (crear archivo temporal de inicio)
echo        Starting backend...
echo @echo off > "%TEMP%\start_backend.bat"
echo cd /d "%BACKEND%" >> "%TEMP%\start_backend.bat"
echo "%VENV_PYTHON%" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload >> "%TEMP%\start_backend.bat"
start "Tutti-Backend" cmd /k "%TEMP%\start_backend.bat"
echo        Backend started on http://localhost:8000

:: Health check before starting frontend
echo        Waiting backend health check...
set "BACKEND_READY=0"
for /L %%i in (1,1,15) do (
    powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 set "BACKEND_READY=1"
    if "!BACKEND_READY!"=="1" goto :backend_ready
    ping -n 2 127.0.0.1 >nul
)
echo        WARNING: backend health check failed, continuing...
goto :start_frontend

:backend_ready
echo        Backend health OK

:: Start Frontend (crear archivo temporal de inicio)
:start_frontend
echo        Starting frontend...
echo @echo off > "%TEMP%\start_frontend.bat"
echo cd /d "%FRONTEND%" >> "%TEMP%\start_frontend.bat"
echo npm run dev >> "%TEMP%\start_frontend.bat"
start "Tutti-Frontend" cmd /k "%TEMP%\start_frontend.bat"
echo        Frontend started on http://localhost:5173

:: Wait frontend port before opening browser
echo        Waiting frontend startup...
for /L %%i in (1,1,20) do (
    netstat -aon | findstr ":5173.*LISTENING" >nul 2>&1 && goto :frontend_ready
    ping -n 2 127.0.0.1 >nul
)

:frontend_ready

echo.
echo  ========================================
echo       Servers are running!
echo.
echo    Backend:   http://localhost:8000
echo    Frontend:  http://localhost:5173
echo.

:: Open browser
echo  Opening browser...
start http://localhost:5173

echo.
echo  Press any key to STOP servers
echo  ========================================
pause >nul

:: Cleanup
echo.
echo  Stopping servers...
del "%TEMP%\start_backend.bat" 2>nul
del "%TEMP%\start_frontend.bat" 2>nul
taskkill /FI "WINDOWTITLE eq Tutti-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Tutti-Frontend*" /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5173"') do taskkill /F /PID %%a >nul 2>&1
echo  Done!
ping -n 3 127.0.0.1 >nul
