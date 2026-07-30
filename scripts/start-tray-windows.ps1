$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Pythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $Pythonw)) {
    throw "BBS virtual environment is missing. Run scripts\install-windows.ps1 first."
}

$existing = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match "connector\.tray_windows" }
if ($existing) { exit 0 }

Start-Process -FilePath $Pythonw `
    -ArgumentList "-m", "connector.tray_windows" `
    -WorkingDirectory $Root `
    -WindowStyle Hidden
