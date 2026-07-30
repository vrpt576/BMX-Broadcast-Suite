param(
    [string]$OutputDirectory = (Join-Path (Resolve-Path "$PSScriptRoot\..").Path "dist")
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..").Path
$staging = Join-Path ([IO.Path]::GetTempPath()) ("bbs-installer-" + [guid]::NewGuid().ToString("N"))
$payloadRoot = Join-Path $staging "payload"
$installer = Join-Path $OutputDirectory "BMX-Broadcast-Suite-Setup-v1.2.6.exe"
$temporaryInstaller = Join-Path $staging "BBS-Setup.exe"

$odbcMsi = Join-Path $root "packaging\windows\dependencies\msodbcsql18-x64.msi"
$expectedOdbcHash = "20314529110DA3365A252164A657BDC837A18BE5839105AA5F5ACF0A8D2F4B82"

if (-not (Test-Path -LiteralPath $odbcMsi)) {
    throw "Missing offline ODBC installer: $odbcMsi"
}

$actualOdbcHash = (Get-FileHash -LiteralPath $odbcMsi -Algorithm SHA256).Hash
if ($actualOdbcHash -ne $expectedOdbcHash) {
    throw "ODBC installer hash mismatch. Expected $expectedOdbcHash but found $actualOdbcHash."
}

$odbcSignature = Get-AuthenticodeSignature -LiteralPath $odbcMsi
if ($odbcSignature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    throw "ODBC installer does not have a valid digital signature: $($odbcSignature.StatusMessage)"
}

if ($odbcSignature.SignerCertificate.Subject -notmatch "Microsoft") {
    throw "ODBC installer signature is valid, but the signer is not recognized as Microsoft."
}

New-Item -ItemType Directory -Force -Path $payloadRoot, $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
$installer = Join-Path $OutputDirectory "BMX-Broadcast-Suite-Setup-v1.2.6.exe"
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
    Copy-Item -LiteralPath $odbcMsi -Destination (Join-Path $staging "msodbcsql18-x64.msi")

@'
@echo off
setlocal
set "SOURCE_ROOT=%~dp0"
set "SOURCE_ROOT=%SOURCE_ROOT:~0,-1%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-wizard-windows.ps1" -SourceRoot "%SOURCE_ROOT%"
exit /b %ERRORLEVEL%
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
FriendlyName=BMX Broadcast Suite 1.2.6 Setup
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
%FILE4%=
[Strings]
FILE0=setup.cmd
FILE1=install-wizard-windows.ps1
FILE2=bbs-payload.zip
FILE3=logo.png
FILE4=msodbcsql18-x64.msi
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
