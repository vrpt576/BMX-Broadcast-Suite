param(
    [string]$Python = "",
    [switch]$SkipRegistry
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$Sandbox = Join-Path ([IO.Path]::GetTempPath()) ("bbs-uninstall-test-" + [guid]::NewGuid().ToString("N"))
$InstallDir = Join-Path $Sandbox "BMX Broadcast Suite"
$PreserveRoot = Join-Path $Sandbox "Preserved"
$RegistryKey = "HKCU:\Software\BMXBroadcastSuite-Uninstall-Test"
$unrelated = $null

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) {
        throw "Validation failed: $Message"
    }
}

try {
    New-Item -ItemType Directory -Force -Path `
        (Join-Path $InstallDir "connector\logs"), `
        (Join-Path $InstallDir "scripts"), `
        (Join-Path $InstallDir "themes\custom-track"), `
        (Join-Path $InstallDir "data") |
        Out-Null

    Set-Content -LiteralPath (Join-Path $InstallDir "connector\main.py") -Value "# validation marker"
    Set-Content -LiteralPath (Join-Path $InstallDir "connector\logs\bbs.log") -Value "operator log"
    Set-Content -LiteralPath (Join-Path $InstallDir "themes\custom-track\theme.json") -Value "{}"
    Set-Content -LiteralPath (Join-Path $InstallDir "data\current_moto.json") -Value "{}"
    Set-Content -LiteralPath (Join-Path $InstallDir ".env") -Value "BBS_SQL_PASSWORD=preserve-me"
    Set-Content -LiteralPath (Join-Path $InstallDir "application.txt") -Value "remove-me"
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "uninstall-worker-windows.ps1") -Destination (Join-Path $InstallDir "scripts")
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "uninstall-windows.ps1") -Destination (Join-Path $InstallDir "scripts")

    if ([string]::IsNullOrWhiteSpace($Python)) {
        $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($null -ne $pythonCommand) {
            $Python = $pythonCommand.Source
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($Python)) {
        $unrelated = Start-Process `
            -FilePath $Python `
            -ArgumentList '-c "import time; time.sleep(60)"' `
            -PassThru `
            -WindowStyle Hidden
    }

    & (Join-Path $PSScriptRoot "uninstall-worker-windows.ps1") `
        -InstallDir $InstallDir `
        -PreserveRoot $PreserveRoot `
        -SkipSystemIntegration

    Assert-True (-not (Test-Path -LiteralPath $InstallDir)) "application files were not removed"
    Assert-True (Test-Path -LiteralPath (Join-Path $PreserveRoot ".env")) ".env was not preserved"
    Assert-True (Test-Path -LiteralPath (Join-Path $PreserveRoot "connector\logs\bbs.log")) "logs were not preserved"
    Assert-True (Test-Path -LiteralPath (Join-Path $PreserveRoot "themes\custom-track\theme.json")) "themes were not preserved"
    Assert-True (Test-Path -LiteralPath (Join-Path $PreserveRoot "data\current_moto.json")) "race data was not preserved"
    if ($null -ne $unrelated) {
        $unrelated.Refresh()
        Assert-True (-not $unrelated.HasExited) "an unrelated Python process was terminated"
    }

    New-Item -ItemType Directory -Force -Path `
        (Join-Path $InstallDir "connector"), `
        (Join-Path $InstallDir "scripts") |
        Out-Null
    Set-Content -LiteralPath (Join-Path $InstallDir "connector\main.py") -Value "# reinstalled"
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "uninstall-windows.ps1") -Destination (Join-Path $InstallDir "scripts")

    & (Join-Path $PSScriptRoot "restore-user-data-windows.ps1") `
        -InstallDir $InstallDir `
        -PreserveRoot $PreserveRoot

    Assert-True (Test-Path -LiteralPath (Join-Path $PreserveRoot ".env")) "reinstall did not retain .env"
    Assert-True (Test-Path -LiteralPath (Join-Path $PreserveRoot "themes\custom-track\theme.json")) "reinstall did not retain themes"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $InstallDir ".env"))) "reinstall copied mutable configuration into Program Files"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $InstallDir "themes\custom-track\theme.json"))) "reinstall copied custom themes into Program Files"

    if ($SkipRegistry) {
        Write-Warning "Registry validation was skipped by request."
    } else {
        & (Join-Path $PSScriptRoot "register-uninstall-windows.ps1") `
            -InstallDir $InstallDir `
            -Version "1.2.9" `
            -RegistryKey $RegistryKey

        $registration = Get-ItemProperty -Path $RegistryKey
        Assert-True ($registration.DisplayName -eq "BMX Broadcast Suite") "Apps & Features name is incorrect"
        Assert-True ($registration.DisplayVersion -eq "1.2.9") "Apps & Features version is incorrect"
        Assert-True ($registration.UninstallString -like "*uninstall-windows.ps1*") "uninstall command is missing"
        Assert-True ($registration.QuietUninstallString -like "*-Quiet*") "quiet uninstall command is missing"
    }

    Write-Host "Windows uninstall validation passed." -ForegroundColor Green
} finally {
    if ($null -ne $unrelated) {
        Stop-Process -Id $unrelated.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $RegistryKey -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Sandbox -Recurse -Force -ErrorAction SilentlyContinue
}
