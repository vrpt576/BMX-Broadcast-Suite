$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$DataRoot = Join-Path $env:ProgramData "BMX Broadcast Suite\UserData"
$StartupError = Join-Path $DataRoot "startup-error.log"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "BBS virtual environment is missing. Run scripts\install-windows.ps1 first."
}

$rootPrefix = [IO.Path]::GetFullPath($Root).TrimEnd("\") + "\"
$existing = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        -not [string]::IsNullOrWhiteSpace($_.ExecutablePath) -and
        [IO.Path]::GetFullPath($_.ExecutablePath).StartsWith(
            $rootPrefix,
            [StringComparison]::OrdinalIgnoreCase
        ) -and
        $_.CommandLine -match "connector\.run"
    }
if ($existing) {
    exit 0
}

New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
Remove-Item -LiteralPath $StartupError -Force -ErrorAction SilentlyContinue
$process = Start-Process `
    -FilePath $Python `
    -ArgumentList "-m", "connector.run" `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 2
$process.Refresh()
if ($process.HasExited) {
    $detail = if (Test-Path -LiteralPath $StartupError) {
        (Get-Content -LiteralPath $StartupError -Raw).Trim()
    } else {
        "No startup traceback was written."
    }
    throw "BBS exited during startup with code $($process.ExitCode).`r`n$detail"
}
