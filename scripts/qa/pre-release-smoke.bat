@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pre-release-smoke.ps1" %*
exit /b %errorlevel%
