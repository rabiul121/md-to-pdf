@echo off
setlocal
chcp 65001 > nul
if /I "%~1"=="--cli" (
	if /I "%~2"=="--auto" (
		powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -Cli -Auto
	) else (
		powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -Cli
	)
) else if /I "%~1"=="--auto" (
	if /I "%~2"=="--cli" (
		powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -Cli -Auto
	) else (
		powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -Auto
	)
) else (
	powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
)
exit /b %ERRORLEVEL%
