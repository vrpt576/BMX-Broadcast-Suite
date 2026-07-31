param(
    [string]$InstallDir = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$DataDir = "",
    [switch]$InstallService
)
$ErrorActionPreference = 'Stop'
Write-Host "Installing BMX Broadcast Suite in $InstallDir" -ForegroundColor Cyan
Set-Location $InstallDir
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' was not found. Install Python 3.11+ first." }

if (-not (Test-Path .venv)) {
    & py -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw "Python virtual environment creation failed with exit code $LASTEXITCODE."
    }
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pip upgrade failed with exit code $LASTEXITCODE."
}
& .\.venv\Scripts\python.exe -m pip install -r connector\requirements.txt
if ($LASTEXITCODE -ne 0) {
    throw "BBS dependency installation failed with exit code $LASTEXITCODE."
}

if ([string]::IsNullOrWhiteSpace($DataDir)) {
    if (-not (Test-Path .env)) {
        Copy-Item connector\.env.example .env
        Write-Host "Created .env. Edit BBS_SQL_PASSWORD before live use." -ForegroundColor Yellow
    }
} else {
    $DataRoot = [IO.Path]::GetFullPath($DataDir).TrimEnd("\")
    New-Item -ItemType Directory -Force -Path `
        $DataRoot, `
        (Join-Path $DataRoot "connector\logs"), `
        (Join-Path $DataRoot "data"), `
        (Join-Path $DataRoot "themes") |
        Out-Null

    $DataEnv = Join-Path $DataRoot ".env"
    if (-not (Test-Path -LiteralPath $DataEnv)) {
        Copy-Item connector\.env.example $DataEnv
        Write-Host "Created $DataEnv. Configure RaceManager before live use." -ForegroundColor Yellow
    }

    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    $inheritance = (
        [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
        [Security.AccessControl.InheritanceFlags]::ObjectInherit
    )
    foreach ($sidValue in @("S-1-5-18", "S-1-5-32-544")) {
        $sid = New-Object Security.Principal.SecurityIdentifier($sidValue)
        $rule = New-Object Security.AccessControl.FileSystemAccessRule(
            $sid,
            [Security.AccessControl.FileSystemRights]::FullControl,
            $inheritance,
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow
        )
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $DataRoot -AclObject $acl
}

& .\.venv\Scripts\python.exe -m connector.windows_assets | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Windows icon generation failed with exit code $LASTEXITCODE."
}

Write-Host "Installation complete." -ForegroundColor Green
Write-Host "Configure: http://localhost:8000/configuration"
Write-Host "Start: .\scripts\start-windows.ps1"
Write-Host "Diagnostics: http://localhost:8000/diagnostics"
if ($InstallService) {
    & "$PSScriptRoot\install-service-windows.ps1" -InstallDir $InstallDir
}
