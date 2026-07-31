param(
    [string]$InstallDir = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$PreserveRoot = (Join-Path $env:ProgramData "BMX Broadcast Suite\UserData"),
    [switch]$PurgeUserData,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    $arguments = @(
        "-NoProfile"
        "-ExecutionPolicy Bypass"
        "-File `"$PSCommandPath`""
        "-InstallDir `"$InstallDir`""
        "-PreserveRoot `"$PreserveRoot`""
    )
    if ($PurgeUserData) { $arguments += "-PurgeUserData" }
    if ($Quiet) { $arguments += "-Quiet" }

    $process = Start-Process powershell.exe -Verb RunAs -ArgumentList ($arguments -join " ") -PassThru -Wait
    exit $process.ExitCode
}

if (-not $Quiet) {
    Add-Type -AssemblyName System.Windows.Forms
    $choice = [Windows.Forms.MessageBox]::Show(
        "Remove BMX Broadcast Suite?`r`n`r`nConfiguration, credentials, logs, themes, and race data will be preserved in:`r`n$PreserveRoot",
        "Uninstall BMX Broadcast Suite",
        [Windows.Forms.MessageBoxButtons]::YesNo,
        [Windows.Forms.MessageBoxIcon]::Question
    )
    if ($choice -ne [Windows.Forms.DialogResult]::Yes) {
        exit 0
    }
}

$workerSource = Join-Path $InstallDir "scripts\uninstall-worker-windows.ps1"
if (-not (Test-Path -LiteralPath $workerSource -PathType Leaf)) {
    throw "The BBS uninstall worker is missing: $workerSource"
}

$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("bbs-uninstall-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
$temporaryWorker = Join-Path $temporaryRoot "uninstall-worker-windows.ps1"
Copy-Item -LiteralPath $workerSource -Destination $temporaryWorker -Force

try {
    $workerArguments = @(
        "-NoProfile"
        "-ExecutionPolicy Bypass"
        "-File `"$temporaryWorker`""
        "-InstallDir `"$InstallDir`""
        "-PreserveRoot `"$PreserveRoot`""
    )
    if ($PurgeUserData) { $workerArguments += "-PurgeUserData" }

    $process = Start-Process `
        powershell.exe `
        -ArgumentList ($workerArguments -join " ") `
        -WorkingDirectory $temporaryRoot `
        -PassThru `
        -Wait
    exit $process.ExitCode
} finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}
