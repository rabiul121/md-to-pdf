$ErrorActionPreference = "Stop"
$RustRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $RustRoot ".."))
$BuildRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "build\rust-installer"))
$CargoTargetRoot = if ($env:CARGO_TARGET_DIR) { [System.IO.Path]::GetFullPath($env:CARGO_TARGET_DIR) } else { Join-Path $RustRoot "target" }
$PackageDir = Join-Path $BuildRoot "package"
$ResourceDir = Join-Path $PackageDir "resources"
$VersionText = Get-Content -LiteralPath (Join-Path $RustRoot "Cargo.toml") -Raw
$VersionMatch = [regex]::Match($VersionText, '(?m)^version\s*=\s*"(?<version>[^"\r\n]+)"')
if (-not $VersionMatch.Success) { throw "Could not read the Rust application version." }
$Version = $VersionMatch.Groups["version"].Value
$Installer = Join-Path $RepoRoot "dist\PdfCreatorStudio-Setup-$Version.exe"
$BuildParent = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "build"))
$BuildPrefix = $BuildParent.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not $BuildRoot.StartsWith($BuildPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing to build outside the repository build directory." }
$BuildParentItem = Get-Item -LiteralPath $BuildParent -ErrorAction SilentlyContinue
if ($BuildParentItem -and ($BuildParentItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { throw "Refusing to use a linked build directory outside the repository." }
if (Test-Path -LiteralPath $BuildRoot) {
    $BuildRootItem = Get-Item -LiteralPath $BuildRoot -Force
    if ($BuildRootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw "Refusing to remove a linked installer build directory." }
}
$CSharpCompiler = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $CSharpCompiler)) { $CSharpCompiler = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe" }
if (-not (Test-Path -LiteralPath $CSharpCompiler)) { throw "The .NET Framework C# compiler is required to build the setup bootstrap." }

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "Rust and Cargo are required. Install the stable Rust MSVC toolchain and Visual Studio C++ Build Tools, then rerun this script."
}
if (Test-Path -LiteralPath $BuildRoot) { Remove-Item -LiteralPath $BuildRoot -Recurse -Force }
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
New-Item -ItemType Directory -Path $ResourceDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $ResourceDir "assets") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $ResourceDir "src") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $ResourceDir "docs") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PackageDir "input") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PackageDir "scripts\windows\installer") -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $Installer) -Force | Out-Null

Write-Host "Building the native Rust application..." -ForegroundColor Cyan
cargo build --manifest-path (Join-Path $RustRoot "Cargo.toml") --release
if ($LASTEXITCODE -ne 0) { throw "Cargo build failed with exit code $LASTEXITCODE." }
$Executable = Join-Path $CargoTargetRoot "release\pdf-creator-studio.exe"
if (-not (Test-Path -LiteralPath $Executable)) { throw "Rust desktop executable was not produced: $Executable" }
Copy-Item -LiteralPath $Executable -Destination (Join-Path $PackageDir "PDF Creator Studio.exe") -Force
$CliExecutable = Join-Path $CargoTargetRoot "release\pdf-creator-studio-cli.exe"
if (-not (Test-Path -LiteralPath $CliExecutable)) { throw "Rust CLI executable was not produced: $CliExecutable" }
Copy-Item -LiteralPath $CliExecutable -Destination (Join-Path $PackageDir "PDF Creator Studio CLI.exe") -Force

Copy-Item -Path (Join-Path $RepoRoot "assets\*") -Destination (Join-Path $ResourceDir "assets") -Recurse -Force
if (Test-Path -LiteralPath (Join-Path $RepoRoot "input")) {
    Copy-Item -Path (Join-Path $RepoRoot "input\*") -Destination (Join-Path $PackageDir "input") -Recurse -Force -ErrorAction SilentlyContinue
}
Get-ChildItem -LiteralPath (Join-Path $ResourceDir "assets") -Recurse -File |
    Where-Object { $_.Name -like "MonoLisaTextTrial*" -or $_.Name -like "MonoLisaCodeTrial*" -or $_.Name -like "Operator-*.ttf" } |
    Remove-Item -Force
Copy-Item -LiteralPath (Join-Path $RepoRoot "src\template.tex") -Destination (Join-Path $ResourceDir "src\template.tex") -Force
Copy-Item -LiteralPath (Join-Path $RepoRoot "src\font_filter.lua") -Destination (Join-Path $ResourceDir "src\font_filter.lua") -Force
Copy-Item -LiteralPath (Join-Path $RustRoot "docs\USER_GUIDE.md") -Destination (Join-Path $ResourceDir "docs\USER_GUIDE.md") -Force
Copy-Item -LiteralPath (Join-Path $RustRoot "scripts\windows\setup.ps1") -Destination (Join-Path $PackageDir "scripts\windows\setup.ps1") -Force
Copy-Item -LiteralPath (Join-Path $RepoRoot "scripts\windows\installer\uninstall.ps1") -Destination (Join-Path $PackageDir "scripts\windows\installer\uninstall.ps1") -Force
Copy-Item -LiteralPath (Join-Path $RustRoot "docs\USER_GUIDE.md") -Destination (Join-Path $PackageDir "USER_GUIDE.md") -Force
Copy-Item -LiteralPath (Join-Path $RepoRoot "LICENSE") -Destination (Join-Path $PackageDir "LICENSE") -Force
Set-Content -LiteralPath (Join-Path $PackageDir "version.txt") -Value $Version -Encoding ASCII

$Payload = Join-Path $BuildRoot "app-payload.zip"
Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $Payload -CompressionLevel Optimal -Force
$InstallScript = Join-Path $RepoRoot "scripts\windows\installer\install.ps1"
$Bootstrap = Join-Path $RepoRoot "scripts\windows\installer\bootstrap.cs"
Write-Host "Building the Windows installer..." -ForegroundColor Cyan
& $CSharpCompiler /nologo /target:winexe /out:$Installer "/win32icon:$(Join-Path $RepoRoot 'assets\pdf_icon.ico')" /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll "/resource:$Payload,app-payload.zip" "/resource:$InstallScript,install.ps1" $Bootstrap
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Installer)) { throw "Installer bootstrap compilation failed with exit code $LASTEXITCODE." }
Write-Host "Installer created: $Installer" -ForegroundColor Green
