param(
    [Parameter(Mandatory)]
    [string]$InstallDir,
    [string]$PreserveRoot = (Join-Path $env:ProgramData "BMX Broadcast Suite\UserData")
)

$ErrorActionPreference = "Stop"
$Root = [IO.Path]::GetFullPath($InstallDir).TrimEnd("\")
$Preserved = [IO.Path]::GetFullPath($PreserveRoot).TrimEnd("\")

New-Item -ItemType Directory -Path $Preserved -Force | Out-Null

$items = @(
    ".env"
    "config.json"
    "connector\logs"
    "themes"
    "data"
)

$legacyConfiguration = (
    (Test-Path -LiteralPath (Join-Path $Root ".env") -PathType Leaf) -or
    (Test-Path -LiteralPath (Join-Path $Root "config.json") -PathType Leaf)
)
if ($legacyConfiguration) {
    foreach ($relative in $items) {
        $source = Join-Path $Root $relative
        $destination = Join-Path $Preserved $relative
        if (
            -not (Test-Path -LiteralPath $source) -or
            (Test-Path -LiteralPath $destination)
        ) {
            continue
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force |
            Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
    }
}

New-Item -ItemType Directory -Force -Path `
    (Join-Path $Preserved "connector\logs"), `
    (Join-Path $Preserved "data"), `
    (Join-Path $Preserved "themes") |
    Out-Null

Write-Host "Prepared preserved BBS operator data in $Preserved." -ForegroundColor Green
