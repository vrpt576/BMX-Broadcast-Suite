param(
    [string]$InstallDir = (Resolve-Path "$PSScriptRoot\..").Path,
    [switch]$InstallService
)
$ErrorActionPreference = 'Stop'
Write-Host "Installing BMX Broadcast Suite in $InstallDir" -ForegroundColor Cyan
Set-Location $InstallDir
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' was not found. Install Python 3.11+ first." }
if (-not (Test-Path .venv)) { py -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r connector\requirements.txt
if (-not (Test-Path .env)) { Copy-Item connector\.env.example .env; Write-Host "Created .env. Edit BBS_SQL_PASSWORD before live use." -ForegroundColor Yellow }
Write-Host "Installation complete." -ForegroundColor Green
Write-Host "Configure: http://localhost:8000/configuration"
Write-Host "Start: .\scripts\start-windows.ps1"
Write-Host "Diagnostics: http://localhost:8000/diagnostics"
if ($InstallService) {
    & "$PSScriptRoot\install-service-windows.ps1" -InstallDir $InstallDir
}
