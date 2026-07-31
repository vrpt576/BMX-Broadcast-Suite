param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$targets = @(
    "connector/service_status.py",
    "connector/tray.py",
    "connector/tray_windows.py",
    "docs/installation-linux.md",
    "docs/installation-windows.md",
    "docs/service-linux.md",
    "docs/service-windows.md",
    "docs/wizard-installer-windows.md",
    "scripts/build-windows-installer.ps1",
    "scripts/install-linux.sh",
    "scripts/install-service-linux.sh",
    "scripts/install-wizard-windows.ps1",
    "tests/test_diagnostics_service.py",
    "tests/test_service_status.py",
    "tests/test_windows_installer.py"
)

$updated = @()
foreach ($relative in $targets) {
    $path = Join-Path $Root $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        continue
    }

    $text = [IO.File]::ReadAllText($path)
    $replacement = $text.Replace("1.2.6", "1.2.8").Replace("1.2.7", "1.2.8")
    if ($replacement -ne $text) {
        [IO.File]::WriteAllText(
            $path,
            $replacement,
            [Text.UTF8Encoding]::new($false)
        )
        $updated += $relative
    }
}

Write-Host "BBS release references prepared for v1.2.8." -ForegroundColor Green
if ($updated.Count -gt 0) {
    Write-Host "Updated:"
    $updated | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "No remaining v1.2.6/v1.2.7 release references were found in known files."
}
