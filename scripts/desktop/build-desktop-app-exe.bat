@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Tutti - Build Desktop EXE
color 0B

set "ROOT=%~dp0..\.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "LAUNCHER=%ROOT%\scripts\desktop\desktop_launcher.py"
set "APP_ICON=%ROOT%\scripts\desktop\assets\tutti-symbol.ico"
set "DESKTOP_REQ=%ROOT%\scripts\desktop\requirements-desktop.txt"
set "VENV=%ROOT%\.venv"
set "VENV_PYTHON=%VENV%\Scripts\python.exe"
set "FINAL_EXE=%ROOT%\dist\Tutti Desktop.exe"
set "BUILD_ONEFILE_NAME=Tutti Desktop Portable Build"
set "BUILD_ONEDIR_NAME=Tutti Desktop"
set "PYI_ONEFILE_DIST=%ROOT%\dist\_pyi_onefile"
set "PYI_ONEDIR_DIST=%ROOT%\dist\_pyi_onedir"
set "PYI_ONEFILE_WORK=%ROOT%\build\pyi-work-onefile"
set "PYI_ONEDIR_WORK=%ROOT%\build\pyi-work-onedir"
set "PYI_SPEC=%ROOT%\build"
set "INSTALLER_PAYLOAD_DIR=%ROOT%\dist\desktop-app\installer-payload"
if /I "%CI%"=="true" set "TUTTI_NON_INTERACTIVE=1"

echo.
echo  ===========================================
echo      TUTTI - Build Desktop EXE (Windows)
echo  ===========================================
echo.

echo  [1/6] Checking virtualenv...
if not exist "%VENV_PYTHON%" (
    python -m venv "%VENV%"
)

echo  [2/6] Installing Python dependencies...
"%VENV_PYTHON%" -m pip install -q --upgrade pip
"%VENV_PYTHON%" -m pip install -q -r "%BACKEND%\requirements.txt"
"%VENV_PYTHON%" -m pip install -q -r "%DESKTOP_REQ%"
"%VENV_PYTHON%" -m pip install -q pyinstaller
if %errorlevel% neq 0 (
    echo        ERROR: Python dependency install failed.
    if not defined TUTTI_NON_INTERACTIVE pause
    exit /b 1
)

echo  [2b/6] Syncing CBC solver binary...
if not exist "%BACKEND%\bin" mkdir "%BACKEND%\bin" >nul 2>&1
"%VENV_PYTHON%" -c "import pathlib,shutil,pulp,sys; src=pathlib.Path(pulp.__file__).resolve().parent/'solverdir'/'cbc'/'win'/'i64'/'cbc.exe'; dst=pathlib.Path(sys.argv[1]); dst.parent.mkdir(parents=True, exist_ok=True); assert src.exists(), f'CBC not found: {src}'; shutil.copy2(src, dst)" "%BACKEND%\bin\cbc.exe"
if %errorlevel% neq 0 (
    echo        ERROR: Could not sync CBC binary to backend\bin\cbc.exe
    if not defined TUTTI_NON_INTERACTIVE pause
    exit /b 1
)

echo  [3/6] Building frontend dist...
pushd "%FRONTEND%"
call npm install --silent
    if %errorlevel% neq 0 (
        popd
        echo        ERROR: npm install failed.
        if not defined TUTTI_NON_INTERACTIVE pause
        exit /b 1
    )
call npm run build
    if %errorlevel% neq 0 (
        popd
        echo        ERROR: npm run build failed.
        if not defined TUTTI_NON_INTERACTIVE pause
        exit /b 1
    )
popd

echo  [4/6] Cleaning previous desktop build...
taskkill /F /IM "Tutti Desktop.exe" >nul 2>&1
taskkill /F /IM "%BUILD_ONEFILE_NAME%.exe" >nul 2>&1
if not exist "%ROOT%\dist" mkdir "%ROOT%\dist" >nul 2>&1
if exist "%PYI_ONEFILE_DIST%" rmdir /S /Q "%PYI_ONEFILE_DIST%" >nul 2>&1
if exist "%PYI_ONEDIR_DIST%" rmdir /S /Q "%PYI_ONEDIR_DIST%" >nul 2>&1
if exist "%PYI_ONEFILE_WORK%" rmdir /S /Q "%PYI_ONEFILE_WORK%" >nul 2>&1
if exist "%PYI_ONEDIR_WORK%" rmdir /S /Q "%PYI_ONEDIR_WORK%" >nul 2>&1
if not exist "%PYI_ONEFILE_WORK%" mkdir "%PYI_ONEFILE_WORK%" >nul 2>&1
if not exist "%PYI_ONEDIR_WORK%" mkdir "%PYI_ONEDIR_WORK%" >nul 2>&1
if not exist "%PYI_SPEC%" mkdir "%PYI_SPEC%" >nul 2>&1

set /a CLEAN_TRIES=0
:cleanup_locked_exe
if exist "%FINAL_EXE%" (
  del /Q "%FINAL_EXE%" >nul 2>&1
  if exist "%FINAL_EXE%" (
    set /a CLEAN_TRIES+=1
    if !CLEAN_TRIES! GEQ 5 (
      echo        WARNING: "%FINAL_EXE%" sigue bloqueado.
      echo        Se continuara con el nuevo EXE en "%PYI_ONEFILE_DIST%".
      goto :cleanup_done
    )
    timeout /t 1 /nobreak >nul
    goto :cleanup_locked_exe
  )
)
:cleanup_done

echo  [5/7] Building portable onefile executable...
set "PYI=%VENV%\Scripts\pyinstaller.exe"
"%PYI%" --noconfirm --clean --windowed --onefile ^
  --name "%BUILD_ONEFILE_NAME%" ^
  --icon "%APP_ICON%" ^
  --distpath "%PYI_ONEFILE_DIST%" ^
  --workpath "%PYI_ONEFILE_WORK%" ^
  --specpath "%PYI_SPEC%" ^
  --paths "%BACKEND%" ^
  --hidden-import main ^
  --hidden-import parser ^
  --hidden-import models ^
  --hidden-import db.database ^
  --hidden-import db.models ^
  --collect-submodules fastapi ^
  --collect-submodules starlette ^
  --collect-submodules pydantic ^
  --collect-submodules uvicorn ^
  --collect-submodules websockets ^
  --collect-submodules wsproto ^
  --collect-submodules sqlalchemy ^
  --collect-submodules pandas ^
  --collect-submodules openpyxl ^
  --collect-submodules reportlab ^
  --collect-submodules pulp ^
  --collect-data pulp ^
  --collect-binaries pulp ^
  --add-data "%BACKEND%;backend" ^
  --add-data "%FRONTEND%\dist;frontend\dist" ^
  "%LAUNCHER%"
if %errorlevel% neq 0 (
    echo        ERROR: PyInstaller onefile build failed.
    if not defined TUTTI_NON_INTERACTIVE pause
    exit /b 1
)

echo  [6/7] Building installer onedir payload...
"%PYI%" --noconfirm --clean --windowed --onedir ^
  --name "%BUILD_ONEDIR_NAME%" ^
  --icon "%APP_ICON%" ^
  --distpath "%PYI_ONEDIR_DIST%" ^
  --workpath "%PYI_ONEDIR_WORK%" ^
  --specpath "%PYI_SPEC%" ^
  --paths "%BACKEND%" ^
  --hidden-import main ^
  --hidden-import parser ^
  --hidden-import models ^
  --hidden-import db.database ^
  --hidden-import db.models ^
  --collect-submodules fastapi ^
  --collect-submodules starlette ^
  --collect-submodules pydantic ^
  --collect-submodules uvicorn ^
  --collect-submodules websockets ^
  --collect-submodules wsproto ^
  --collect-submodules sqlalchemy ^
  --collect-submodules pandas ^
  --collect-submodules openpyxl ^
  --collect-submodules reportlab ^
  --collect-submodules pulp ^
  --collect-data pulp ^
  --collect-binaries pulp ^
  --add-data "%BACKEND%;backend" ^
  --add-data "%FRONTEND%\dist;frontend\dist" ^
  "%LAUNCHER%"
if %errorlevel% neq 0 (
    echo        ERROR: PyInstaller onedir build failed.
    if not defined TUTTI_NON_INTERACTIVE pause
    exit /b 1
)

echo  [7/7] Packaging portable ZIP and installer payload...
set "BUILT_PORTABLE_EXE=%PYI_ONEFILE_DIST%\%BUILD_ONEFILE_NAME%.exe"
if not exist "%BUILT_PORTABLE_EXE%" (
    echo        ERROR: Portable EXE not found: %BUILT_PORTABLE_EXE%
    if not defined TUTTI_NON_INTERACTIVE pause
    exit /b 1
)
set "BUILT_ONEDIR_ROOT=%PYI_ONEDIR_DIST%\%BUILD_ONEDIR_NAME%"
set "BUILT_ONEDIR_EXE=%BUILT_ONEDIR_ROOT%\%BUILD_ONEDIR_NAME%.exe"
if not exist "%BUILT_ONEDIR_EXE%" (
    echo        ERROR: Installer payload EXE not found: %BUILT_ONEDIR_EXE%
    if not defined TUTTI_NON_INTERACTIVE pause
    exit /b 1
)

set /a COPY_TRIES=0
set "EXE_FOR_PACKAGE=%FINAL_EXE%"
:copy_to_final_exe
copy /Y "%BUILT_PORTABLE_EXE%" "%FINAL_EXE%" >nul 2>&1
if exist "%FINAL_EXE%" goto :copy_done
set /a COPY_TRIES+=1
if !COPY_TRIES! GEQ 5 goto :copy_fallback
timeout /t 1 /nobreak >nul
goto :copy_to_final_exe

:copy_fallback
echo        WARNING: Could not copy EXE to final path; file may be locked.
echo        Packaging from temporary path instead.
set "EXE_FOR_PACKAGE=%BUILT_PORTABLE_EXE%"
:copy_done

if not exist "%ROOT%\dist\desktop-app" mkdir "%ROOT%\dist\desktop-app" >nul 2>&1
if exist "%ROOT%\dist\desktop-app\release" rmdir /S /Q "%ROOT%\dist\desktop-app\release" >nul 2>&1
mkdir "%ROOT%\dist\desktop-app\release" >nul 2>&1
copy /Y "%EXE_FOR_PACKAGE%" "%ROOT%\dist\desktop-app\release\Tutti Desktop.exe" >nul
powershell -Command "Compress-Archive -Path '%ROOT%\dist\desktop-app\release\*' -DestinationPath '%ROOT%\dist\desktop-app\TuttiDesktopApp.zip' -Force" >nul 2>&1
if exist "%INSTALLER_PAYLOAD_DIR%" rmdir /S /Q "%INSTALLER_PAYLOAD_DIR%" >nul 2>&1
mkdir "%INSTALLER_PAYLOAD_DIR%" >nul 2>&1
xcopy "%BUILT_ONEDIR_ROOT%\*" "%INSTALLER_PAYLOAD_DIR%\" /E /I /Y >nul
if not exist "%INSTALLER_PAYLOAD_DIR%\Tutti Desktop.exe" (
    echo        ERROR: Installer payload copy failed: %INSTALLER_PAYLOAD_DIR%\Tutti Desktop.exe missing
    if not defined TUTTI_NON_INTERACTIVE pause
    exit /b 1
)

echo.
echo  Build completed:
echo    Portable EXE: %FINAL_EXE%
echo    Portable ZIP: %ROOT%\dist\desktop-app\TuttiDesktopApp.zip
echo    Installer payload: %INSTALLER_PAYLOAD_DIR%
if not exist "%FINAL_EXE%" (
  echo    NOTE: Final EXE path was locked. Use temporary EXE:
  echo    %BUILT_PORTABLE_EXE%
)
echo.
if not defined TUTTI_NON_INTERACTIVE pause
exit /b 0
