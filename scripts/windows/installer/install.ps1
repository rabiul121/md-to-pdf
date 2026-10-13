$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
$AppName = "PDF Creator Studio"
$InstallRoot = Join-Path $env:LOCALAPPDATA "Programs\$AppName"
$Payload = Join-Path $PSScriptRoot "app-payload.zip"
$VersionFile = Join-Path $InstallRoot "version.txt"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\md-to-pdf-studio"

try {
    if (-not (Test-Path -LiteralPath $Payload)) {
        throw "The application payload was not found beside the installer bootstrap."
    }

    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
    Expand-Archive -LiteralPath $Payload -DestinationPath $InstallRoot -Force

    $SetupScript = Join-Path $InstallRoot "scripts\windows\setup.ps1"
    if (-not (Test-Path -LiteralPath $SetupScript)) {
        throw "The installed dependency setup script is missing."
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SetupScript -PackagedApp
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency setup failed with exit code $LASTEXITCODE. Rerun setup.ps1 from the installed folder after resolving the dependency error."
    }

    $Executable = Join-Path $InstallRoot "PDF Creator Studio.exe"
    if (-not (Test-Path -LiteralPath $Executable)) {
        throw "The application executable was not installed."
    }
    if (-not (Test-Path -LiteralPath $VersionFile)) {
        throw "The installed version metadata is missing."
    }
    $ProductVersion = (Get-Content -LiteralPath $VersionFile -Raw).Trim()

    $Shell = New-Object -ComObject WScript.Shell
    $Desktop = [Environment]::GetFolderPath("DesktopDirectory")
    $StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) $AppName
    New-Item -ItemType Directory -Path $StartMenu -Force | Out-Null
    foreach ($ShortcutPath in @((Join-Path $Desktop "$AppName.lnk"), (Join-Path $StartMenu "$AppName.lnk"))) {
        $Shortcut = $Shell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = $Executable
        $Shortcut.WorkingDirectory = $InstallRoot
        $Shortcut.IconLocation = "$Executable,0"
        $Shortcut.Description = "Convert multilingual documents to PDF"
        $Shortcut.Save()
    }

    New-Item -Path $UninstallKey -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name DisplayName -Value $AppName -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name DisplayVersion -Value $ProductVersion -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name Publisher -Value "md-to-pdf" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name InstallLocation -Value $InstallRoot -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name DisplayIcon -Value "$Executable,0" -PropertyType String -Force | Out-Null
    $Uninstaller = Join-Path $InstallRoot "scripts\windows\installer\uninstall.ps1"
    New-ItemProperty -Path $UninstallKey -Name UninstallString -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Uninstaller`"" -PropertyType String -Force | Out-Null

    Write-Host "$AppName was installed successfully." -ForegroundColor Green
    Write-Host "Desktop and Start menu shortcuts were created. User profiles and PDFs are stored separately from the program files."
} catch {
    Write-Error $_
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, "$AppName setup failed", "OK", "Error") | Out-Null
    exit 1
}
