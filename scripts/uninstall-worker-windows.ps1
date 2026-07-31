param(
    [Parameter(Mandatory)]
    [string]$InstallDir,
    [string]$PreserveRoot = (Join-Path $env:ProgramData "BMX Broadcast Suite\UserData"),
    [string]$RegistryKey = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BMXBroadcastSuite",
    [switch]$PurgeUserData,
    [switch]$SkipSystemIntegration
)

$ErrorActionPreference = "Stop"
$TaskName = "BMX Broadcast Suite"
$Root = [IO.Path]::GetFullPath($InstallDir).TrimEnd("\")
$RootPrefix = $Root + [IO.Path]::DirectorySeparatorChar
$Preserved = [IO.Path]::GetFullPath($PreserveRoot).TrimEnd("\")

if (
    [string]::IsNullOrWhiteSpace($Root) -or
    $Root -eq [IO.Path]::GetPathRoot($Root) -or
    $Root -eq [IO.Path]::GetFullPath($env:ProgramFiles).TrimEnd("\") -or
    -not (Test-Path -LiteralPath (Join-Path $Root "connector\main.py") -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $Root "scripts\uninstall-worker-windows.ps1") -PathType Leaf)
) {
    throw "Refusing to uninstall because '$Root' is not a valid BMX Broadcast Suite installation."
}
if (
    $Preserved.Equals($Root, [StringComparison]::OrdinalIgnoreCase) -or
    $Preserved.StartsWith($RootPrefix, [StringComparison]::OrdinalIgnoreCase)
) {
    throw "The preserved user-data path must be outside the application installation."
}

function Test-PathInsideRoot([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }
    try {
        return [IO.Path]::GetFullPath($Path).StartsWith(
            $RootPrefix,
            [StringComparison]::OrdinalIgnoreCase
        )
    } catch {
        return $false
    }
}

if (-not $SkipSystemIntegration) {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $task) {
        $ownedTask = @($task.Actions).Where({
            Test-PathInsideRoot $_.Execute
        }).Count -gt 0
        if ($ownedTask) {
            Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }
    }

    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            (Test-PathInsideRoot $_.ExecutablePath) -and
            $_.CommandLine -match "connector\.(run|tray_windows)"
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }

    foreach ($serviceName in @("BMXBroadcastSuite", "BMX Broadcast Suite")) {
        $service = Get-CimInstance Win32_Service -Filter "Name='$serviceName'" -ErrorAction SilentlyContinue
        if ($null -ne $service -and $service.PathName -like "*$Root*") {
            Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
            & sc.exe delete $serviceName | Out-Null
        }
    }
}

if ($PurgeUserData) {
    if (Test-Path -LiteralPath $Preserved) {
        Remove-Item -LiteralPath $Preserved -Recurse -Force
    }
} else {
    New-Item -ItemType Directory -Path $Preserved -Force | Out-Null
    try {
        if ($SkipSystemIntegration) {
            throw [OperationCanceledException]::new(
                "ACL hardening skipped during non-administrative validation."
            )
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
        Set-Acl -LiteralPath $Preserved -AclObject $acl
    } catch [OperationCanceledException] {
        Write-Verbose $_.Exception.Message
    } catch {
        Write-Warning "Could not restrict preserved-data permissions: $($_.Exception.Message)"
    }
    foreach ($relative in @(".env", "config.json", "connector\logs", "themes", "data")) {
        $source = Join-Path $Root $relative
        if (-not (Test-Path -LiteralPath $source)) {
            continue
        }
        $destination = Join-Path $Preserved $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        if (Test-Path -LiteralPath $source -PathType Container) {
            if (Test-Path -LiteralPath $destination) {
                Remove-Item -LiteralPath $destination -Recurse -Force
            }
            Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
        } else {
            Copy-Item -LiteralPath $source -Destination $destination -Force
        }
    }
}

if (-not $SkipSystemIntegration) {
    $shortcutPaths = @(
        (Join-Path ([Environment]::GetFolderPath("CommonDesktopDirectory")) "BMX Broadcast Suite.lnk")
        (Join-Path ([Environment]::GetFolderPath("DesktopDirectory")) "BMX Broadcast Suite.lnk")
        (Join-Path ([Environment]::GetFolderPath("CommonPrograms")) "BMX Broadcast Suite")
        (Join-Path ([Environment]::GetFolderPath("Programs")) "BMX Broadcast Suite")
        (Join-Path ([Environment]::GetFolderPath("CommonStartup")) "BMX Broadcast Suite Tray.lnk")
        (Join-Path ([Environment]::GetFolderPath("Startup")) "BMX Broadcast Suite Tray.lnk")
    )
    foreach ($path in $shortcutPaths) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    }

    Remove-Item -LiteralPath $RegistryKey -Recurse -Force -ErrorAction SilentlyContinue
}

for ($attempt = 1; $attempt -le 5; $attempt++) {
    try {
        Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction Stop
        break
    } catch {
        if ($attempt -eq 5) {
            throw
        }
        Start-Sleep -Milliseconds 500
    }
}

Write-Host "BMX Broadcast Suite was removed from $Root." -ForegroundColor Green
if (-not $PurgeUserData) {
    Write-Host "Operator data was preserved in $Preserved." -ForegroundColor Yellow
}
