param(
    [Parameter(Mandatory)]
    [string]$InstallDir,
    [string]$PreserveRoot = (Join-Path $env:ProgramData "BMX Broadcast Suite\UserData")
)

$ErrorActionPreference = "Stop"
$Root = [IO.Path]::GetFullPath($InstallDir).TrimEnd("\")
$Preserved = [IO.Path]::GetFullPath($PreserveRoot).TrimEnd("\")

if (-not (Test-Path -LiteralPath $Preserved -PathType Container)) {
    return
}

$items = @(
    ".env"
    "config.json"
    "connector\logs"
    "themes"
    "data"
)

foreach ($relative in $items) {
    $source = Join-Path $Preserved $relative
    if (-not (Test-Path -LiteralPath $source)) {
        continue
    }

    $destination = Join-Path $Root $relative
    $parent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Path $parent -Force | Out-Null

    if (Test-Path -LiteralPath $source -PathType Container) {
        New-Item -ItemType Directory -Path $destination -Force | Out-Null
        Copy-Item -Path (Join-Path $source "*") -Destination $destination -Recurse -Force
    } else {
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
}

Write-Host "Restored preserved BBS operator data from $Preserved." -ForegroundColor Green
