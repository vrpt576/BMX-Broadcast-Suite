$ErrorActionPreference = "Stop"
$TaskName = "BMX Broadcast Suite"
$Root = [IO.Path]::GetFullPath((Resolve-Path "$PSScriptRoot\..").Path).TrimEnd("\")
$RootPrefix = $Root + [IO.Path]::DirectorySeparatorChar

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator to remove the machine-wide BBS task."
}

Get-CimInstance Win32_Process |
    Where-Object {
        -not [string]::IsNullOrWhiteSpace($_.ExecutablePath) -and
        [IO.Path]::GetFullPath($_.ExecutablePath).StartsWith(
            $RootPrefix,
            [StringComparison]::OrdinalIgnoreCase
        ) -and
        $_.CommandLine -match "connector\.tray_windows"
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$ownedTask = (
    $null -ne $task -and
    @($task.Actions).Where({
        -not [string]::IsNullOrWhiteSpace($_.Execute) -and
        [IO.Path]::GetFullPath($_.Execute).StartsWith(
            $RootPrefix,
            [StringComparison]::OrdinalIgnoreCase
        )
    }).Count -gt 0
)
if ($ownedTask) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$paths = @(
    (Join-Path ([Environment]::GetFolderPath("CommonDesktopDirectory")) "BMX Broadcast Suite.lnk"),
    (Join-Path ([Environment]::GetFolderPath("CommonPrograms")) "BMX Broadcast Suite"),
    (Join-Path ([Environment]::GetFolderPath("CommonStartup")) "BMX Broadcast Suite Tray.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Startup")) "BMX Broadcast Suite Tray.lnk")
)
foreach ($path in $paths) {
    Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "BBS Windows background task and launchers removed." -ForegroundColor Green
Write-Host "Project files, .env, themes, logs, and race state were preserved."
