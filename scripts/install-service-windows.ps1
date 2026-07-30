param(
    [string]$InstallDir = (Resolve-Path "$PSScriptRoot\..").Path,
    [switch]$NoAutoStart
)

$ErrorActionPreference = "Stop"
$TaskName = "BMX Broadcast Suite"
$Root = (Resolve-Path $InstallDir).Path
$Pythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"
$Logo = Join-Path $Root "logo.png"
$Icon = Join-Path $Root "data\bbs.ico"
$TrayScript = Join-Path $Root "scripts\start-tray-windows.ps1"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator to install the machine-wide BBS background task."
}
if (-not (Test-Path $Pythonw)) { throw "Run scripts\install-windows.ps1 before installing the service." }
if (-not (Test-Path (Join-Path $Root ".env"))) { throw "Configure BBS first; .env is missing." }
& (Join-Path $Root ".venv\Scripts\python.exe") -m connector.windows_assets | Out-Null

$action = New-ScheduledTaskAction `
    -Execute $Pythonw `
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

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $taskPrincipal `
    -Description "BMX Broadcast Suite connector; starts at machine boot." `
    -Force | Out-Null

$shell = New-Object -ComObject WScript.Shell
$launcher = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$TrayScript`""

$desktop = [Environment]::GetFolderPath("CommonDesktopDirectory")
$startMenu = Join-Path ([Environment]::GetFolderPath("CommonPrograms")) "BMX Broadcast Suite"
$startup = [Environment]::GetFolderPath("Startup")
New-Item -ItemType Directory -Force -Path $startMenu | Out-Null

function New-BBSShortcut([string]$Path, [string]$Arguments = "") {
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = "powershell.exe"
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$TrayScript`" $Arguments"
    $shortcut.WorkingDirectory = $Root
    if (Test-Path $Icon) { $shortcut.IconLocation = $Icon }
    $shortcut.Description = "BMX Broadcast Suite status and controls"
    $shortcut.Save()
}

New-BBSShortcut (Join-Path $desktop "BMX Broadcast Suite.lnk")
New-BBSShortcut (Join-Path $startMenu "BMX Broadcast Suite.lnk")
New-BBSShortcut (Join-Path $startup "BMX Broadcast Suite Tray.lnk")

if (-not $NoAutoStart) {
    Start-ScheduledTask -TaskName $TaskName
}
& $TrayScript

Write-Host "BBS 1.2.4 Windows background task installed." -ForegroundColor Green
Write-Host "The connector starts at machine boot and restarts after failures."
Write-Host "Desktop, Start Menu, and notification-area launchers were installed."
Write-Host "Diagnostics: http://localhost:8000/diagnostics"
