@echo off
setlocal
chcp 65001 > nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cli_watch.ps1" %*
exit /b %ERRORLEVEL%
