param([string]$InstallDir = (Resolve-Path "$PSScriptRoot\..").Path)
$ErrorActionPreference = 'Stop'
Write-Host "Installing BMX Broadcast Suite in $InstallDir" -ForegroundColor Cyan
Set-Location $InstallDir
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' was not found. Install Python 3.11+ first." }
if (-not (Test-Path .venv)) { py -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r connector\requirements.txt
if (-not (Test-Path .env)) { Copy-Item connector\.env.example .env; Write-Host "Created .env. Edit BBS_SQL_PASSWORD before live use." -ForegroundColor Yellow }
Write-Host "Installation complete." -ForegroundColor Green
Write-Host "Start: .\.venv\Scripts\python.exe -m uvicorn connector.main:app --host 0.0.0.0 --port 8000"
Write-Host "Diagnostics: http://localhost:8000/diagnostics"
