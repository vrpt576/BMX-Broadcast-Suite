# Windows MSI Installer

BBS 1.2.11 replaces the former IExpress EXE with `BMX-Broadcast-Suite-Setup-v1.2.11.msi`, built by WiX Toolset v4.

The MSI contains an offline Python 3.12.10 runtime and hash-locked wheels. It does not run VBScript or PowerShell, change execution policy, download packages, or create a Scheduled Task. Windows Installer owns Apps & Features, files, shortcuts, upgrades, and uninstall. WinSW 2.12.0, pinned to the official release SHA-256, hosts the automatic `BMXBroadcastSuite` service.

## Install

Install the 64-bit Microsoft ODBC Driver 18 for SQL Server from Microsoft, then run the MSI as administrator. Legacy v1.2.9/v1.2.10 upgrades stop and delete only the exact old BBS task and preserve `%ProgramData%\BMX Broadcast Suite\UserData`.

## Uninstall

Use **Settings → Apps → Installed apps**. Operator data remains in ProgramData. To explicitly purge that data:

```powershell
msiexec.exe /x BMX-Broadcast-Suite-Setup-v1.2.11.msi PURGEUSERDATA=1
```

## Build and release gate

The build is offline and validates every pinned artifact:

```powershell
.\scripts\build-windows-installer.ps1 -CertificateThumbprint YOUR_SHA1_THUMBPRINT
```

For local testing only, use `-Unsigned`. Before publication, sign the MSI and scan the exact final file with current Defender definitions:

```powershell
.\scripts\test-windows-release-artifact.ps1 -Path .\dist\BMX-Broadcast-Suite-Setup-v1.2.11.msi
```

If Defender detects it, do not upload it; submit that exact artifact to Microsoft Security Intelligence. Outputs include the MSI, SHA-256 file, manifest, and CycloneDX SBOM.
