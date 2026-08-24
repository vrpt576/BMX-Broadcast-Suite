param(
    [string]$OutputDirectory = (Join-Path (Resolve-Path "$PSScriptRoot\..").Path "dist"),
    [switch]$AllowUncommitted,
    [switch]$Unsigned,
    [string]$CertificateThumbprint = "",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$Version = "1.2.17"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
$Packaging = Join-Path $Root "packaging\windows"
$Dependencies = Join-Path $Packaging "dependencies"
$Lock = Get-Content (Join-Path $Packaging "dependency-lock.json") -Raw | ConvertFrom-Json
$Staging = Join-Path ([IO.Path]::GetTempPath()) ("bbs-msi-" + [guid]::NewGuid().ToString("N"))
$Indexed = Join-Path $Staging "indexed"
$Payload = Join-Path $Staging "payload"
$Runtime = Join-Path $Payload "runtime"
$InstallerName = "BMX-Broadcast-Suite-Setup-v$Version.msi"
$Installer = Join-Path $OutputDirectory $InstallerName

function Assert-Hash([string]$Path, [string]$Expected) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing locked dependency: $Path" }
    $Actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    if ($Actual -ne $Expected) { throw "Dependency hash mismatch for $Path. Expected $Expected, found $Actual." }
}

function Expand-Nupkg([string]$Path, [string]$Destination) {
    $Zip = "$Destination.zip"
    Copy-Item -LiteralPath $Path -Destination $Zip -Force
    Expand-Archive -LiteralPath $Zip -DestinationPath $Destination -Force
}

function Write-ApplicationComponents([string]$PayloadRoot, [string]$OutputPath) {
    $Lines = @(
        '<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">',
        '  <Fragment>',
        '    <ComponentGroup Id="ApplicationFiles">'
    )
    $Index = 0
    foreach ($File in (Get-ChildItem $PayloadRoot -File -Recurse | Sort-Object FullName)) {
        $Relative = $File.FullName.Substring($PayloadRoot.Length + 1)
        if ($Relative -in @('BBSService.exe', 'BBSService.xml')) { continue }
        $Index++
        $Id = 'AppFile{0:D6}' -f $Index
        $Source = [Security.SecurityElement]::Escape($File.FullName)
        $Subdirectory = Split-Path $Relative -Parent
        $SubdirectoryAttribute = if ($Subdirectory) {
            ' Subdirectory="' + [Security.SecurityElement]::Escape($Subdirectory) + '"'
        } else { '' }
        $Lines += "      <Component Id=`"$Id`" Directory=`"INSTALLFOLDER`"$SubdirectoryAttribute Guid=`"*`">"
        $Lines += "        <File Source=`"$Source`" KeyPath=`"yes`" />"
        $Lines += '      </Component>'
    }
    $Lines += @('    </ComponentGroup>', '  </Fragment>', '</Wix>')
    Set-Content -LiteralPath $OutputPath -Value $Lines -Encoding UTF8
}

function Find-SignTool {
    $Found = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($Found) { return $Found.Source }
    $Candidates = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
        Where-Object FullName -match "\\x64\\signtool\.exe$" | Sort-Object FullName -Descending
    if ($Candidates) { return $Candidates[0].FullName }
    throw "signtool.exe was not found. Install the Windows SDK signing tools."
}

function Sign-File([string]$Path) {
    $SignTool = Find-SignTool
    & $SignTool sign /sha1 $CertificateThumbprint /fd SHA256 /td SHA256 /tr $TimestampUrl $Path
    if ($LASTEXITCODE -ne 0) { throw "Authenticode signing failed for $Path." }
    $Signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($Signature.Status -ne "Valid") { throw "Signature verification failed for ${Path}: $($Signature.Status)" }
}

if ($Unsigned -and $CertificateThumbprint) { throw "Choose either -Unsigned or -CertificateThumbprint, not both." }
if (-not $Unsigned -and -not $CertificateThumbprint) {
    throw "Release builds require -CertificateThumbprint. Use -Unsigned only for local validation; never publish an unsigned MSI without explicit approval and a clean Defender result."
}
if (-not (Test-Path (Join-Path $Root ".git"))) { throw "Build from a Git checkout." }
$Changes = @(& git -C $Root status --porcelain --untracked-files=all)
if (-not $AllowUncommitted -and $Changes.Count) { throw "Refusing to build from a dirty worktree." }
if ($AllowUncommitted -and @(& git -C $Root diff --name-only).Count) {
    throw "Stage every intended change before using -AllowUncommitted; the build uses the Git index."
}

$RequiredTracked = @(
    "packaging/windows/Product.wxs",
    "packaging/windows/BBSService.xml",
    "packaging/windows/dependency-lock.json",
    "packaging/windows/requirements-lock.txt",
    "packaging/windows/dependencies/WinSW-x64.exe",
    "packaging/windows/dependencies/WinSW-LICENSE.txt",
    "packaging/windows/dependencies/python-3.12.10-embed-amd64.zip",
    "packaging/windows/dependencies/Python-LICENSE.txt",
    "packaging/windows/dependencies/tools/wix.4.0.6.nupkg",
    "packaging/windows/dependencies/tools/WixToolset.Util.wixext.4.0.6.nupkg"
)
foreach ($Relative in $RequiredTracked) {
    & git -C $Root ls-files --error-unmatch -- $Relative 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Required MSI input is not tracked or staged: $Relative" }
}
$LockedWheels = Get-ChildItem (Join-Path $Dependencies "wheels") -Filter *.whl -File
if (-not $LockedWheels) { throw "The offline wheelhouse is empty." }
foreach ($Wheel in $LockedWheels) {
    $Relative = $Wheel.FullName.Substring($Root.Length + 1).Replace("\", "/")
    & git -C $Root ls-files --error-unmatch -- $Relative 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Offline dependency is not tracked or staged: $Relative" }
}
foreach ($Artifact in $Lock.artifacts) {
    Assert-Hash (Join-Path $Packaging ($Artifact.path -replace "/", "\")) $Artifact.sha256
}

New-Item -ItemType Directory -Force -Path $Staging, $Indexed, $Payload, $Runtime, $OutputDirectory | Out-Null
try {
    $Prefix = $Indexed.TrimEnd("\") + "\"
    & git -C $Root checkout-index --all --force --prefix=$Prefix
    if ($LASTEXITCODE -ne 0) { throw "Git could not materialize the indexed source." }

    foreach ($Name in @("connector", "database", "themes", "overlay", "assets", "controller", "exporter")) {
        $Source = Join-Path $Indexed $Name
        if (Test-Path $Source) { Copy-Item $Source $Payload -Recurse -Force }
    }
    foreach ($Name in @("README.md", "LICENSE", "logo.png")) {
        Copy-Item (Join-Path $Indexed $Name) $Payload -Force
    }
    Copy-Item (Join-Path $Dependencies "WinSW-x64.exe") (Join-Path $Payload "BBSService.exe")
    Copy-Item (Join-Path $Packaging "BBSService.xml") $Payload
    Copy-Item (Join-Path $Dependencies "WinSW-LICENSE.txt") $Payload
    Copy-Item (Join-Path $Dependencies "Python-LICENSE.txt") $Payload

    Expand-Archive (Join-Path $Dependencies "python-3.12.10-embed-amd64.zip") -DestinationPath $Runtime
    $Pth = Join-Path $Runtime "python312._pth"
    $PthLines = @(Get-Content $Pth | Where-Object { $_ -ne "#import site" }) + @("..", "Lib\site-packages", "import site")
    Set-Content -LiteralPath $Pth -Value $PthLines -Encoding Ascii
    $SitePackages = Join-Path $Runtime "Lib\site-packages"
    New-Item -ItemType Directory -Force -Path $SitePackages | Out-Null
    & python -m pip install --no-index --only-binary=:all: --require-hashes --ignore-installed `
        --find-links (Join-Path $Dependencies "wheels") --target $SitePackages `
        -r (Join-Path $Packaging "requirements-lock.txt")
    if ($LASTEXITCODE -ne 0) { throw "Offline locked dependency installation failed." }
    Push-Location $Payload
    try {
        & (Join-Path $Runtime "python.exe") -c "import fastapi, pyodbc, pydantic, uvicorn, PIL, pystray"
        if ($LASTEXITCODE -ne 0) { throw "The embedded Python runtime failed its import check." }
        & (Join-Path $Runtime "python.exe") -m connector.windows_assets | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Icon generation failed." }
    } finally { Pop-Location }
    Copy-Item (Join-Path $Payload "data\bbs.ico") (Join-Path $Payload "assets\bbs.ico") -Force
    Remove-Item (Join-Path $Payload "data") -Recurse -Force
    Get-ChildItem -LiteralPath $Payload -Directory -Filter "__pycache__" -Recurse |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $Payload -File -Filter "*.pyc" -Recurse |
        Remove-Item -Force
    if ($CertificateThumbprint) { Sign-File (Join-Path $Payload "BBSService.exe") }

    $ManifestItems = Get-ChildItem $Payload -File -Recurse | Sort-Object FullName | ForEach-Object {
        [ordered]@{
            path = $_.FullName.Substring($Payload.Length + 1).Replace("\", "/")
            size = $_.Length
            sha256 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
        }
    }
    $Commit = (& git -C $Root rev-parse HEAD).Trim()
    $Manifest = [ordered]@{ product="BMX Broadcast Suite"; version=$Version; commit=$Commit; files=$ManifestItems }
    $ManifestPath = Join-Path $Staging "artifact-manifest.json"
    $Manifest | ConvertTo-Json -Depth 6 | Set-Content $ManifestPath -Encoding UTF8
    New-Item -ItemType Directory -Force -Path (Join-Path $Payload "metadata") | Out-Null
    Copy-Item $ManifestPath (Join-Path $Payload "metadata\artifact-manifest.json")
    $Sbom = [ordered]@{
        bomFormat="CycloneDX"; specVersion="1.5"; version=1
        metadata=@{ component=@{ type="application"; name="BMX Broadcast Suite"; version=$Version } }
        components=@($Lock.artifacts | ForEach-Object { @{ type="library"; name=[IO.Path]::GetFileName($_.path); version=$_.version; hashes=@(@{alg="SHA-256";content=$_.sha256}); externalReferences=@(@{type="distribution";url=$_.source}) } })
    }
    $SbomPath = Join-Path $Staging "sbom.cdx.json"
    $Sbom | ConvertTo-Json -Depth 8 | Set-Content $SbomPath -Encoding UTF8
    Copy-Item $SbomPath (Join-Path $Payload "metadata\sbom.cdx.json")

    $ApplicationComponents = Join-Path $Staging "ApplicationFiles.wxs"
    Write-ApplicationComponents $Payload $ApplicationComponents

    $ToolDir = Join-Path $Staging "wix"
    $UtilDir = Join-Path $Staging "wix-util"
    Expand-Nupkg (Join-Path $Dependencies "tools\wix.4.0.6.nupkg") $ToolDir
    Expand-Nupkg (Join-Path $Dependencies "tools\WixToolset.Util.wixext.4.0.6.nupkg") $UtilDir
    $Wix = Join-Path $ToolDir "tools\net6.0\any\wix.dll"
    $Util = Join-Path $UtilDir "wixext4\WixToolset.Util.wixext.dll"
    & dotnet $Wix build (Join-Path $Packaging "Product.wxs") $ApplicationComponents -arch x64 -d "ProductVersion=$Version" `
        -d "PayloadRoot=$Payload" -ext $Util -pdbtype none -o $Installer
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Installer)) { throw "WiX did not produce the MSI." }
    if ($CertificateThumbprint) { Sign-File $Installer }

    $Hash = Get-FileHash $Installer -Algorithm SHA256
    "$($Hash.Hash)  $InstallerName" | Set-Content "$Installer.sha256.txt" -Encoding Ascii
    Copy-Item $ManifestPath (Join-Path $OutputDirectory "BMX-Broadcast-Suite-Setup-v$Version.manifest.json") -Force
    Copy-Item $SbomPath (Join-Path $OutputDirectory "BMX-Broadcast-Suite-Setup-v$Version.sbom.cdx.json") -Force
    $Signature = Get-AuthenticodeSignature $Installer
    [pscustomobject]@{ Path=$Installer; Size=(Get-Item $Installer).Length; SHA256=$Hash.Hash; Authenticode=$Signature.Status }
} finally {
    if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force -ErrorAction SilentlyContinue }
}
