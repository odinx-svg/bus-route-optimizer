@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Tutti - Build Windows Installer
color 0B

set "ROOT=%~dp0..\.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "APP_EXE=%ROOT%\dist\Tutti Desktop.exe"
set "INSTALLER_SCRIPT=%ROOT%\scripts\desktop\installer\TuttiSetup.iss"
set "INSTALLER_OUT_DIR=%ROOT%\dist\desktop-app"
set "APP_VERSION=0.1.0"
if /I "%CI%"=="true" set "TUTTI_NON_INTERACTIVE=1"

echo.
echo  ===============================================
echo      TUTTI - Build Installer EXE (Inno Setup)
echo  ===============================================
echo.

if not exist "%APP_EXE%" (
    echo  [1/4] Desktop EXE not found. Building first...
    call "%ROOT%\scripts\desktop\build-desktop-app-exe.bat"
    if %errorlevel% neq 0 (
        echo        ERROR: Could not build desktop EXE.
        if not defined TUTTI_NON_INTERACTIVE pause
        exit /b 1
    )
) else (
    echo  [1/4] Desktop EXE found.
)

echo  [2/4] Resolving app version...
for /f "tokens=3 delims= " %%V in ('type "%ROOT%\scripts\desktop\desktop_version.py" ^| findstr /B /C:"APP_VERSION"') do set "APP_VERSION=%%~V"
set "APP_VERSION=%APP_VERSION:"=%"
echo        Version: %APP_VERSION%

echo  [3/4] Detecting Inno Setup compiler...
set "ISCC_EXE="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC_EXE (
    echo        ERROR: Inno Setup not found.
    echo        Install from: https://jrsoftware.org/isinfo.php
    echo        Expected: ISCC.exe in Program Files ^(x86^)\\Inno Setup 6
    if not defined TUTTI_NON_INTERACTIVE pause
    exit /b 1
)
echo        ISCC: %ISCC_EXE%

echo  [4/4] Building installer...
if not exist "%INSTALLER_OUT_DIR%" mkdir "%INSTALLER_OUT_DIR%" >nul 2>&1
"%ISCC_EXE%" ^
  /DAppVersion=%APP_VERSION% ^
  "%INSTALLER_SCRIPT%"

if %errorlevel% neq 0 (
    echo        ERROR: Inno Setup build failed.
    if not defined TUTTI_NON_INTERACTIVE pause
    exit /b 1
)

echo.
echo  Installer created:
echo    %INSTALLER_OUT_DIR%\TuttiSetup.exe
echo.
echo  Next release assets recommendation:
echo    1. TuttiSetup.exe  ^<-- button web downloads this
echo    2. TuttiDesktopApp.zip  ^<-- desktop auto-update uses this
echo.
if not defined TUTTI_NON_INTERACTIVE pause
exit /b 0
