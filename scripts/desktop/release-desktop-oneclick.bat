@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0release-desktop-oneclick.ps1" %*
exit /b %errorlevel%
