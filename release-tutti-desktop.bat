@echo off
setlocal
call "%~dp0scripts\desktop\release-desktop-oneclick.bat" %*
exit /b %errorlevel%
