@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Tutti - Desktop App
color 0B

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "FRONTEND_DIST=%FRONTEND%\dist"
set "DESKTOP_REQ=%ROOT%scripts\desktop\requirements-desktop.txt"
set "LAUNCHER=%ROOT%scripts\desktop\desktop_launcher.py"
set "VENV=%ROOT%.venv"
set "VENV_PYTHON=%VENV%\Scripts\python.exe"

echo.
echo  ========================================
echo      TUTTI - Desktop App (Native)
echo  ========================================
echo.

echo  [1/5] Checking Python virtualenv...
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

echo  [2/5] Installing backend dependencies...
"%VENV_PYTHON%" -m pip install -q --upgrade pip
"%VENV_PYTHON%" -m pip install -q -r "%BACKEND%\requirements.txt"
if %errorlevel% neq 0 (
    echo        ERROR: Could not install backend dependencies.
    pause
    exit /b 1
)

echo  [3/5] Installing desktop dependencies...
"%VENV_PYTHON%" -m pip install -q -r "%DESKTOP_REQ%"
if %errorlevel% neq 0 (
    echo        ERROR: Could not install desktop dependencies ^(pywebview^).
    pause
    exit /b 1
)

echo  [4/5] Checking frontend dist...
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

echo  [5/5] Launching native desktop window...
"%VENV_PYTHON%" "%LAUNCHER%"
if %errorlevel% neq 0 (
    echo.
    echo        ERROR: Desktop app exited with failure.
    pause
    exit /b 1
)

exit /b 0
