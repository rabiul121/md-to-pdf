@echo off
setlocal
title Install Dependencies (Windows)
chcp 65001 > nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 exit /b 1

pause
exit /b 0
