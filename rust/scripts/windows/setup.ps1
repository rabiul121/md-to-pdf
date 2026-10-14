param([switch]$PackagedApp)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8

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
    if (-not $installed) { throw "Could not install $ScoopName. Install it manually, then rerun setup." }
    Refresh-ProcessPath
}

Write-Host "PDF Creator Studio (Rust): Windows dependency setup" -ForegroundColor Cyan
if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Pandoc..." -ForegroundColor Yellow
    Install-Dependency "JohnMacFarlane.Pandoc" "pandoc"
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

if ($PackagedApp) {
    Write-Host "Setup complete. Launch PDF Creator Studio from the Start menu or desktop." -ForegroundColor Green
} else {
    Write-Host "Setup complete. Build the Rust app with cargo build --manifest-path rust/Cargo.toml --release." -ForegroundColor Green
}
