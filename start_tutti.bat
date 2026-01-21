@echo off
title Tutti - Bus Route Optimizer
color 0A

echo.
echo  ████████╗██╗   ██╗████████╗████████╗██╗
echo  ╚══██╔══╝██║   ██║╚══██╔══╝╚══██╔══╝██║
echo     ██║   ██║   ██║   ██║      ██║   ██║
echo     ██║   ██║   ██║   ██║      ██║   ██║
echo     ██║   ╚██████╔╝   ██║      ██║   ██║
echo     ╚═╝    ╚═════╝    ╚═╝      ╚═╝   ╚═╝
echo.
echo  Starting Tutti System...
echo.

:: Start Backend
echo [1/2] Starting Backend (FastAPI)...
start "Tutti Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

:: Wait for backend to initialize
timeout /t 3 /nobreak > nul

:: Start Frontend
echo [2/2] Starting Frontend (Vite)...
start "Tutti Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:: Wait for frontend to initialize
timeout /t 4 /nobreak > nul

:: Open browser
echo.
echo Opening browser...
start http://localhost:5173

echo.
echo ══════════════════════════════════════════════════
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo ══════════════════════════════════════════════════
echo.
echo   Press any key to close this window.
echo   (Backend and Frontend will keep running)
echo.
pause > nul
