@echo off
setlocal
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File tools\pre_push_check.ps1
exit /b %ERRORLEVEL%
