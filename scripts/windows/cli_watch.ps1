$ErrorActionPreference = "Stop"
$Launcher = Join-Path $PSScriptRoot "..\..\launchers\start.ps1"
& $Launcher -Cli -Auto
exit $LASTEXITCODE
