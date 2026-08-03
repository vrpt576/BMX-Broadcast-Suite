param(
    [Parameter(Mandatory)][string]$Path,
    [switch]$AllowUnsigned
)
$ErrorActionPreference = "Stop"
$Artifact = (Resolve-Path $Path).Path
$Signature = Get-AuthenticodeSignature $Artifact
if (-not $AllowUnsigned -and $Signature.Status -ne "Valid") {
    throw "Release artifact is not validly Authenticode-signed: $($Signature.Status)"
}
Update-MpSignature
$Before = Get-Date
Start-MpScan -ScanType CustomScan -ScanPath $Artifact
$Threats = @(Get-MpThreatDetection | Where-Object {
    $_.InitialDetectionTime -ge $Before.AddMinutes(-1) -and
    @($_.Resources) -match [regex]::Escape($Artifact)
})
$Status = Get-MpComputerStatus
$Report = [ordered]@{
    artifact = [IO.Path]::GetFileName($Artifact)
    size = (Get-Item $Artifact).Length
    sha256 = (Get-FileHash $Artifact -Algorithm SHA256).Hash
    authenticode = $Signature.Status.ToString()
    signer = if ($Signature.SignerCertificate) { $Signature.SignerCertificate.Subject } else { $null }
    defender_engine = $Status.AMEngineVersion
    defender_definitions = $Status.AntivirusSignatureVersion
    defender_definitions_updated = $Status.AntivirusSignatureLastUpdated
    scan_completed = (Get-Date).ToString("o")
    detections = @($Threats | ForEach-Object ThreatName)
}
$ReportPath = "$Artifact.security.json"
$Report | ConvertTo-Json -Depth 5 | Set-Content $ReportPath -Encoding UTF8
if ($Threats.Count) { throw "Microsoft Defender detected the exact artifact. Do not publish it; submit it to Microsoft Security Intelligence. Report: $ReportPath" }
$Report
