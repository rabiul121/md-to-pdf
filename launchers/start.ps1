param(
    [switch]$Cli,
    [switch]$Auto
)

$ErrorActionPreference = "Stop"
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Converter = Join-Path $RepoRoot "main.py"
$Python = Get-Command python -ErrorAction SilentlyContinue
if ($Python) {
    $Arguments = @($Converter)
    if ($Cli) { $Arguments += "--cli" }
    if ($Auto) { $Arguments += "--auto" }
    & $Python.Source @Arguments
    exit $LASTEXITCODE
}

$PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($PythonLauncher) {
    $Arguments = @("-3", $Converter)
    if ($Cli) { $Arguments += "--cli" }
    if ($Auto) { $Arguments += "--auto" }
    & $PythonLauncher.Source @Arguments
    exit $LASTEXITCODE
} else {
    Write-Error "Python 3 is required. Install Python, then run this launcher again."
    exit 1
}
