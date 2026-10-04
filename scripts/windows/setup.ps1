$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))

function Refresh-ProcessPath {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $env:Path = (@($userPath, $machinePath) + @($env:Path -split ";") | Where-Object { $_ } | Select-Object -Unique) -join ";"
}

function Install-Dependency([string]$WingetId, [string]$ScoopName) {
    $installed = $false
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        & winget install --id $WingetId -e --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -eq 0) { $installed = $true }
    }
    if (-not $installed -and (Get-Command scoop -ErrorAction SilentlyContinue)) {
        & scoop install $ScoopName
        if ($LASTEXITCODE -eq 0) { $installed = $true }
    }
    if (-not $installed) {
        throw "Could not install $ScoopName. Install it manually, then rerun setup."
    }
    Refresh-ProcessPath
}

Write-Host "Multilingual Markdown to PDF: Windows setup" -ForegroundColor Cyan

if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Pandoc..." -ForegroundColor Yellow
    Install-Dependency "JohnMacFarlane.Pandoc" "pandoc"
}
if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Python 3..." -ForegroundColor Yellow
    Install-Dependency "Python.Python.3.12" "python"
}
if (-not (Get-Command xelatex -ErrorAction SilentlyContinue)) {
    Write-Host "Installing MiKTeX..." -ForegroundColor Yellow
    Install-Dependency "MiKTeX.MiKTeX" "miktex"
}
Refresh-ProcessPath

$missing = @("pandoc", "xelatex") | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) }
if ($missing.Count -gt 0) {
    throw "Required command(s) not found after installation: $($missing -join ', '). Restart PowerShell and rerun setup."
}
if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python 3 was not found after installation. Restart PowerShell and rerun setup."
}

$fontSource = Join-Path $RepoRoot "assets\fonts"
$fontsTarget = Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Fonts"
$fontRegistry = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts"
if (-not (Test-Path $fontSource)) { throw "Bundled fonts directory not found: $fontSource" }
New-Item -ItemType Directory -Path $fontsTarget -Force | Out-Null
New-Item -Path $fontRegistry -Force | Out-Null

$fontFiles = Get-ChildItem -Path $fontSource -Recurse -File | Where-Object {
    ($_.Extension -in @(".ttf", ".otf", ".ttc")) -and ($_.Name -notin @("seguiemj.ttf", "seguisym.ttf"))
}
foreach ($font in $fontFiles) {
    $destination = Join-Path $fontsTarget $font.Name
    Copy-Item -LiteralPath $font.FullName -Destination $destination -Force
    $fontType = if ($font.Extension -eq ".otf") { "OpenType" } else { "TrueType" }
    New-ItemProperty -Path $fontRegistry -Name "$($font.BaseName) ($fontType)" -Value $destination -PropertyType String -Force | Out-Null
}

$nativeMethods = @'
using System;
using System.Runtime.InteropServices;
public static class FontChangeNotification {
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint flags, uint timeout, out UIntPtr result);
}
'@
Add-Type -TypeDefinition $nativeMethods -ErrorAction SilentlyContinue
[UIntPtr]$notifyResult = [UIntPtr]::Zero
[FontChangeNotification]::SendMessageTimeout([IntPtr]0xffff, 0x001D, [UIntPtr]::Zero, $null, 2, 1000, [ref]$notifyResult) | Out-Null

Write-Host "Setup complete. Start the app with run.bat or launchers\start.bat --cli." -ForegroundColor Green
