param(
    [string]$InstallDir = (Resolve-Path "$PSScriptRoot\..").Path,
    [switch]$NoAutoStart,
    [switch]$NoTrayLaunch
)

$ErrorActionPreference = "Stop"
$TaskName = "BMX Broadcast Suite"
$Root = (Resolve-Path $InstallDir).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Logo = Join-Path $Root "logo.png"
$Icon = Join-Path $Root "data\bbs.ico"
$TrayScript = Join-Path $Root "scripts\start-tray-windows.ps1"
$DataRoot = Join-Path $env:ProgramData "BMX Broadcast Suite\UserData"
$StartupError = Join-Path $DataRoot "startup-error.log"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator to install the machine-wide BBS background task."
}
if (-not (Test-Path $Python)) { throw "Run scripts\install-windows.ps1 before installing the service." }
if (-not (Test-Path (Join-Path $DataRoot ".env"))) {
    throw "Configure BBS first; $DataRoot\.env is missing."
}
& (Join-Path $Root ".venv\Scripts\python.exe") -m connector.windows_assets | Out-Null

$action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "-m connector.run" `
    -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)
$taskPrincipal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

$desktop = [Environment]::GetFolderPath("CommonDesktopDirectory")
$startMenu = Join-Path ([Environment]::GetFolderPath("CommonPrograms")) "BMX Broadcast Suite"
$startup = [Environment]::GetFolderPath("CommonStartup")

function New-BBSShortcut([string]$Path, [string]$Arguments = "") {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = "powershell.exe"
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$TrayScript`" $Arguments"
    $shortcut.WorkingDirectory = $Root
    if (Test-Path $Icon) { $shortcut.IconLocation = $Icon }
    $shortcut.Description = "BMX Broadcast Suite status and controls"
    $shortcut.Save()
}

function Get-StartupFailureDetail {
    if (Test-Path -LiteralPath $StartupError) {
        return (Get-Content -LiteralPath $StartupError -Raw).Trim()
    }
    return "No startup traceback was written. Review Task Scheduler history."
}

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $taskPrincipal `
        -Description "BMX Broadcast Suite connector; starts at machine boot." `
        -Force | Out-Null

    $registered = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $registeredAction = @($registered.Actions)[0]
    if (
        -not [IO.Path]::GetFullPath($registeredAction.Execute).Equals(
            [IO.Path]::GetFullPath($Python),
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        $registeredAction.Arguments -ne "-m connector.run" -or
        -not [IO.Path]::GetFullPath($registeredAction.WorkingDirectory).Equals(
            [IO.Path]::GetFullPath($Root),
            [StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw "The BBS Scheduled Task was created with an unexpected action."
    }

    if (-not $NoAutoStart) {
        Remove-Item -LiteralPath $StartupError -Force -ErrorAction SilentlyContinue
        Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        Start-Sleep -Seconds 2
        $registered = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        if ($registered.State -ne "Running") {
            $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
            $detail = Get-StartupFailureDetail
            throw "The BBS Scheduled Task exited during startup (result $($info.LastTaskResult)).`r`n$detail"
        }
    }

    New-Item -ItemType Directory -Force -Path $startMenu | Out-Null
    New-BBSShortcut (Join-Path $desktop "BMX Broadcast Suite.lnk")
    New-BBSShortcut (Join-Path $startMenu "BMX Broadcast Suite.lnk")
    New-BBSShortcut (Join-Path $startup "BMX Broadcast Suite Tray.lnk")

    if (-not $NoTrayLaunch) {
        & $TrayScript
    }
} catch {
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $existingTask) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    }
    foreach ($path in @(
        (Join-Path $desktop "BMX Broadcast Suite.lnk"),
        $startMenu,
        (Join-Path $startup "BMX Broadcast Suite Tray.lnk")
    )) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    }
    throw
}

Write-Host "BBS 1.2.10 Windows background task installed." -ForegroundColor Green
Write-Host "The connector starts at machine boot and restarts after failures."
Write-Host "Desktop, Start Menu, and notification-area launchers were installed."
Write-Host "Diagnostics: http://localhost:8000/diagnostics"
