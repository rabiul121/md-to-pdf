param(
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$ProjectMetadata = Get-Content -LiteralPath (Join-Path $RepoRoot "pyproject.toml") -Raw
$VersionMatch = [regex]::Match($ProjectMetadata, '(?m)^version\s*=\s*"(?<version>[^"\r\n]+)"')
if (-not $VersionMatch.Success) { throw "Could not read the project version from pyproject.toml." }
$ProductVersion = $VersionMatch.Groups["version"].Value
$BuildRoot = Join-Path $RepoRoot "build\windows-installer"
$PackageDir = Join-Path $BuildRoot "package"
$PackAssets = Join-Path $RepoRoot ".installer-assets-stage"
$StageDir = Join-Path $RepoRoot "build\windows-installer-stage"
$InstallerOutput = Join-Path $RepoRoot "dist\PdfCreatorStudio-Setup-$ProductVersion.exe"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { (Get-Command python -ErrorAction Stop).Source }
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
if (Test-Path $PackAssets) {
    Remove-Item -LiteralPath $PackAssets -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
New-Item -ItemType Directory -Path $PackAssets -Force | Out-Null
New-Item -ItemType Directory -Path $StageDir -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $InstallerOutput) -Force | Out-Null

# Package project assets from a staging copy so locally installed trial fonts
# are never redistributed by the application installer.
Copy-Item -Path (Join-Path $RepoRoot "assets\*") -Destination $PackAssets -Recurse -Force
Get-ChildItem -LiteralPath $PackAssets -Recurse -File -Filter "MonoLisa*" |
    Remove-Item -Force

Write-Host "Packaging the Flet desktop app..." -ForegroundColor Cyan
$PackArgs = @(
    "pack", "src/ui/flet_app.py",
    "--name", "PDF Creator Studio",
    "--product-name", "PDF Creator Studio",
    "--file-description", "Multilingual document to PDF converter",
    "--product-version", $ProductVersion,
    "--distpath", $PackageDir,
    "--yes",
    "--add-data", ".installer-assets-stage:assets",
    "--add-data", "src/template.tex:src",
    "--add-data", "src/font_filter.lua:src",
    "--add-data", "docs:docs",
    "--pyinstaller-build-args=--workpath=$BuildRoot\pyinstaller-work",
    "--pyinstaller-build-args=--specpath=$RepoRoot"
)
& $Python -m flet_cli.cli @PackArgs
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
Set-Content -LiteralPath (Join-Path $PackageDir "version.txt") -Value $ProductVersion -Encoding ASCII

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

# Keep only the distributable in dist; the unpacked app, PyInstaller cache,
# staged payload, and generated spec are reproducible build intermediates.
Remove-Item -LiteralPath $BuildRoot, $StageDir, $PackAssets -Recurse -Force
