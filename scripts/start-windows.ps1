param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path "$PSScriptRoot\..").Path
& .\.venv\Scripts\python.exe -m uvicorn connector.main:app --host 0.0.0.0 --port $Port
