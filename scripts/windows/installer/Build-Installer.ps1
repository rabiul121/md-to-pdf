param(
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$BuildRoot = Join-Path $RepoRoot "build\windows-installer"
$PackageDir = Join-Path $BuildRoot "package"
$StageDir = Join-Path $RepoRoot "build\windows-installer-stage"
$InstallerOutput = Join-Path $RepoRoot "dist\PdfCreatorStudio-Setup-1.0.0.exe"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$VenvFlet = Join-Path $RepoRoot ".venv\Scripts\flet.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { (Get-Command python -ErrorAction Stop).Source }
$Flet = if (Test-Path $VenvFlet) { $VenvFlet } else { (Get-Command flet -ErrorAction Stop).Source }
$CSharpCompiler = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $CSharpCompiler)) {
    $CSharpCompiler = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"
}

if (-not (Test-Path $CSharpCompiler)) { throw "The Windows .NET Framework C# compiler was not found." }
if (-not $SkipDependencyInstall) {
    & $Python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing PyInstaller for the desktop app build..." -ForegroundColor Yellow
        & $Python -m pip install pyinstaller
        if ($LASTEXITCODE -ne 0) { throw "Could not install PyInstaller." }
    }
}

if (Test-Path $BuildRoot) {
    Remove-Item -LiteralPath $BuildRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
New-Item -ItemType Directory -Path $StageDir -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $InstallerOutput) -Force | Out-Null

Write-Host "Packaging the Flet desktop app..." -ForegroundColor Cyan
$PackArgs = @(
    "pack", "src/ui/flet_app.py",
    "--name", "PDF Creator Studio",
    "--product-name", "PDF Creator Studio",
    "--file-description", "Multilingual document to PDF converter",
    "--product-version", "1.0.0",
    "--distpath", $PackageDir,
    "--yes",
    "--add-data", "assets:assets",
    "--add-data", "src/template.tex:src",
    "--add-data", "src/font_filter.lua:src",
    "--add-data", "docs:docs",
    "--pyinstaller-build-args=--workpath=$BuildRoot\pyinstaller-work",
    "--pyinstaller-build-args=--specpath=$RepoRoot"
)
& $Flet @PackArgs
if ($LASTEXITCODE -ne 0) { throw "flet pack failed with exit code $LASTEXITCODE." }
$GeneratedSpec = Join-Path $RepoRoot "PDF Creator Studio.spec"
if (Test-Path -LiteralPath $GeneratedSpec) {
    Move-Item -LiteralPath $GeneratedSpec -Destination (Join-Path $BuildRoot "PDF Creator Studio.spec") -Force
}

$Executable = Join-Path $PackageDir "PDF Creator Studio.exe"
if (-not (Test-Path -LiteralPath $Executable)) { throw "Expected packaged executable was not produced: $Executable" }
if (Test-Path -LiteralPath $StageDir) {
    Remove-Item -LiteralPath $StageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $StageDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PackageDir "scripts\windows") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PackageDir "scripts\windows\installer") -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $RepoRoot "scripts\windows\setup.ps1") -Destination (Join-Path $PackageDir "scripts\windows\setup.ps1")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "uninstall.ps1") -Destination (Join-Path $PackageDir "scripts\windows\installer\uninstall.ps1")
Copy-Item -LiteralPath (Join-Path $RepoRoot "docs\USER_GUIDE.md") -Destination (Join-Path $PackageDir "USER_GUIDE.md")
Copy-Item -LiteralPath (Join-Path $RepoRoot "LICENSE") -Destination (Join-Path $PackageDir "LICENSE")

$Payload = Join-Path $StageDir "app-payload.zip"
Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $Payload -CompressionLevel Optimal
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "install.ps1") -Destination (Join-Path $StageDir "install.ps1")

Write-Host "Building the per-user self-extracting setup executable..." -ForegroundColor Cyan
$BootstrapSource = Join-Path $PSScriptRoot "bootstrap.cs"
& $CSharpCompiler /nologo /target:winexe /out:$InstallerOutput /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll "/resource:$Payload,app-payload.zip" "/resource:$(Join-Path $PSScriptRoot 'install.ps1'),install.ps1" $BootstrapSource
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $InstallerOutput)) {
    throw "The installer bootstrap build failed with exit code $LASTEXITCODE."
}
Write-Host "Installer created: $InstallerOutput" -ForegroundColor Green
