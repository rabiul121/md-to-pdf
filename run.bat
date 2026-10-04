@echo off
setlocal
:: Root convenience launcher; see launchers\start.bat for shared Python selection.
call "%~dp0launchers\start.bat" %*
exit /b %ERRORLEVEL%
