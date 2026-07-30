param(
    [string]$OutputDirectory = (Join-Path (Resolve-Path "$PSScriptRoot\..").Path "dist")
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..").Path
$staging = Join-Path ([IO.Path]::GetTempPath()) ("bbs-installer-" + [guid]::NewGuid().ToString("N"))
$payloadRoot = Join-Path $staging "payload"
$installer = Join-Path $OutputDirectory "BMX-Broadcast-Suite-Setup-v1.2.5.exe"
$temporaryInstaller = Join-Path $staging "BBS-Setup.exe"

New-Item -ItemType Directory -Force -Path $payloadRoot, $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
$installer = Join-Path $OutputDirectory "BMX-Broadcast-Suite-Setup-v1.2.5.exe"
try {
    Get-ChildItem -LiteralPath $root -Force |
        Where-Object { $_.Name -notin @(".git", ".venv", ".test-venv", ".pytest_cache", "data", "dist", "debug-installer") } |
        Copy-Item -Destination $payloadRoot -Recurse -Force

    Get-ChildItem -Path $payloadRoot -Directory -Filter "__pycache__" -Recurse |
        Remove-Item -Recurse -Force
    Get-ChildItem -Path $payloadRoot -File -Include "*.pyc", "*.pyo" -Recurse |
        Remove-Item -Force

    Compress-Archive -Path (Join-Path $payloadRoot "*") -DestinationPath (Join-Path $staging "bbs-payload.zip") -CompressionLevel Optimal
    Copy-Item (Join-Path $root "scripts\install-wizard-windows.ps1") $staging
    Copy-Item (Join-Path $root "logo.png") $staging

    @'
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-wizard-windows.ps1" -SourceRoot "%~dp0"
'@ | Set-Content -LiteralPath (Join-Path $staging "setup.cmd") -Encoding Ascii

    $sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=0
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$temporaryInstaller
FriendlyName=BMX Broadcast Suite 1.2.5 Setup
AppLaunched=setup.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=setup.cmd
UserQuietInstCmd=setup.cmd
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0=$staging\
[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
%FILE3%=
[Strings]
FILE0=setup.cmd
FILE1=install-wizard-windows.ps1
FILE2=bbs-payload.zip
FILE3=logo.png
"@
    $sedPath = Join-Path $staging "installer.sed"
    $sed | Set-Content -LiteralPath $sedPath -Encoding Ascii
    & "$env:SystemRoot\System32\iexpress.exe" /N /Q $sedPath
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    $lastLength = -1
    $stableChecks = 0
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path $temporaryInstaller) {
            $length = (Get-Item $temporaryInstaller).Length
            if ($length -gt 1000000 -and $length -eq $lastLength) {
                $stableChecks++
                if ($stableChecks -ge 4) { break }
            } else {
                $stableChecks = 0
            }
            $lastLength = $length
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-Path $temporaryInstaller) -or (Get-Item $temporaryInstaller).Length -le 1000000) {
        throw "IExpress did not create a complete installer."
    }
    Move-Item -LiteralPath $temporaryInstaller -Destination $installer -Force
    Get-FileHash -Algorithm SHA256 $installer
} finally {
    if (Test-Path $staging) {
        Start-Sleep -Seconds 1
        Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    }
}
