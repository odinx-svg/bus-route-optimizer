@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%\..\.."
set "ROOT=%CD%"

set "FRONTEND=%ROOT%\frontend"
set "BACKEND=%ROOT%\backend"
set "OUT_ROOT=%ROOT%\dist\desktop"
set "OUT_APP=%OUT_ROOT%\TuttiDesktop"
set "OUT_ZIP=%OUT_ROOT%\TuttiDesktop.zip"

echo.
echo  ========================================
echo    Building Tutti Desktop Bundle
echo  ========================================
echo.

if not exist "%FRONTEND%\package.json" (
  echo ERROR: frontend folder not found
  exit /b 1
)
if not exist "%BACKEND%\main.py" (
  echo ERROR: backend folder not found
  exit /b 1
)

echo [1/5] Building frontend dist...
pushd "%FRONTEND%"
call npm install --silent
if %errorlevel% neq 0 (
  popd
  echo ERROR: npm install failed
  exit /b 1
)
call npm run build
if %errorlevel% neq 0 (
  popd
  echo ERROR: npm run build failed
  exit /b 1
)
popd

echo [2/5] Preparing output folder...
if exist "%OUT_APP%" rmdir /S /Q "%OUT_APP%"
mkdir "%OUT_APP%" >nul 2>&1

echo [3/5] Copying backend and assets...
robocopy "%BACKEND%" "%OUT_APP%\backend" /E /NFL /NDL /NJH /NJS /NC /NS ^
  /XD "__pycache__" ".pytest_cache" "tests" "benchmarks" "data" >nul
if %errorlevel% geq 8 (
  echo ERROR: robocopy backend failed
  exit /b 1
)

if not exist "%OUT_APP%\frontend" mkdir "%OUT_APP%\frontend" >nul 2>&1
robocopy "%FRONTEND%\dist" "%OUT_APP%\frontend\dist" /E /NFL /NDL /NJH /NJS /NC /NS >nul
if %errorlevel% geq 8 (
  echo ERROR: robocopy frontend dist failed
  exit /b 1
)

copy /Y "%ROOT%\start-tutti-desktop.bat" "%OUT_APP%\start-tutti-desktop.bat" >nul

if exist "%ROOT%\docs\setup\DESKTOP_DISTRIBUTION_ES.md" (
  if not exist "%OUT_APP%\docs" mkdir "%OUT_APP%\docs" >nul 2>&1
  copy /Y "%ROOT%\docs\setup\DESKTOP_DISTRIBUTION_ES.md" "%OUT_APP%\docs\DESKTOP_DISTRIBUTION_ES.md" >nul
)

echo [4/5] Creating zip package...
if exist "%OUT_ZIP%" del /F /Q "%OUT_ZIP%" >nul 2>&1
powershell -NoProfile -Command "Compress-Archive -Path '%OUT_APP%\*' -DestinationPath '%OUT_ZIP%' -Force"
if %errorlevel% neq 0 (
  echo ERROR: zip creation failed
  exit /b 1
)

echo [5/5] Done.
echo.
echo Output folder: %OUT_APP%
echo Output zip:    %OUT_ZIP%
echo.
echo Next step:
echo   - Entregar al cliente el ZIP
echo   - Cliente descomprime y ejecuta start-tutti-desktop.bat
echo.

popd
exit /b 0

