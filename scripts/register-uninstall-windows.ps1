param(
    [string]$InstallDir = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$Version = "1.2.9",
    [string]$RegistryKey = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BMXBroadcastSuite"
)

$ErrorActionPreference = "Stop"
$Root = [IO.Path]::GetFullPath($InstallDir).TrimEnd("\")
$Uninstaller = Join-Path $Root "scripts\uninstall-windows.ps1"
$Icon = Join-Path $Root "data\bbs.ico"

if (-not (Test-Path -LiteralPath $Uninstaller -PathType Leaf)) {
    throw "The BBS uninstaller is missing: $Uninstaller"
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if ((Test-Path -LiteralPath $Python) -and -not (Test-Path -LiteralPath $Icon)) {
    & $Python -m connector.windows_assets | Out-Null
}

$sizeBytes = (
    Get-ChildItem -LiteralPath $Root -File -Recurse -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum
).Sum
$estimatedSize = [Math]::Max(1, [Math]::Ceiling($sizeBytes / 1KB))
$uninstallCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Uninstaller`" -InstallDir `"$Root`""

New-Item -Path $RegistryKey -Force | Out-Null
New-ItemProperty -Path $RegistryKey -Name DisplayName -Value "BMX Broadcast Suite" -PropertyType String -Force | Out-Null
New-ItemProperty -Path $RegistryKey -Name DisplayVersion -Value $Version -PropertyType String -Force | Out-Null
New-ItemProperty -Path $RegistryKey -Name DisplayIcon -Value $Icon -PropertyType String -Force | Out-Null
New-ItemProperty -Path $RegistryKey -Name InstallLocation -Value $Root -PropertyType String -Force | Out-Null
New-ItemProperty -Path $RegistryKey -Name InstallDate -Value (Get-Date -Format "yyyyMMdd") -PropertyType String -Force | Out-Null
New-ItemProperty -Path $RegistryKey -Name URLInfoAbout -Value "https://github.com/vrpt576/BMX-Broadcast-Suite" -PropertyType String -Force | Out-Null
New-ItemProperty -Path $RegistryKey -Name UninstallString -Value $uninstallCommand -PropertyType String -Force | Out-Null
New-ItemProperty -Path $RegistryKey -Name QuietUninstallString -Value "$uninstallCommand -Quiet" -PropertyType String -Force | Out-Null
New-ItemProperty -Path $RegistryKey -Name EstimatedSize -Value ([int]$estimatedSize) -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $RegistryKey -Name NoModify -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $RegistryKey -Name NoRepair -Value 1 -PropertyType DWord -Force | Out-Null

Write-Host "Registered BMX Broadcast Suite $Version in Windows Apps & Features." -ForegroundColor Green
