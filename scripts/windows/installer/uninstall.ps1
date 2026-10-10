$ErrorActionPreference = "Stop"
$AppName = "PDF Creator Studio"
$InstallRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\md-to-pdf-studio"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("DesktopDirectory")) "$AppName.lnk"
$StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) $AppName

Remove-Item -LiteralPath $DesktopShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $StartMenu -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $UninstallKey -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $InstallRoot -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "$AppName was removed. Profiles and generated PDFs were kept." -ForegroundColor Green
