# Windows MSI Installer

BBS 1.3.0 uses `BMX-Broadcast-Suite-Setup-v1.3.0.msi`, built by WiX Toolset v4. It retains the native MSI and Windows-service architecture introduced in v1.2.11.

The MSI contains an offline Python 3.12.10 runtime and hash-locked wheels. It does not run VBScript or PowerShell, change execution policy, download packages, or create a Scheduled Task. Windows Installer owns Apps & Features, files, shortcuts, upgrades, and uninstall. WinSW 2.12.0, pinned to the official release SHA-256, hosts the automatic `BMXBroadcastSuite` service.

## Install

**Running the MSI shows Windows' "Windows protected your PC" screen
first.** This build isn't signed with a paid code-signing certificate, so
SmartScreen doesn't recognize the publisher yet -- it isn't a sign
anything is wrong with the file. Click **More info**, then **Run anyway**
to continue.

Install the 64-bit Microsoft ODBC Driver 18 for SQL Server from Microsoft, then run the MSI as administrator. Legacy v1.2.9/v1.2.10 upgrades stop and delete only the exact old BBS task and preserve `%ProgramData%\BMX Broadcast Suite\UserData`.

The MSI never owns or replaces the protected `.env`. On first service start,
BBS creates it from the packaged example only when it is absent. During an
upgrade, BBS appends newly supported keys only when missing. Existing SQL,
network, theme, event, and secret values remain unchanged. Reinstalling the
same build is idempotent and does not rewrite the file.

## Uninstall

Use **Settings → Apps → Installed apps**. Operator data remains in ProgramData. To explicitly purge that data:

```powershell
msiexec.exe /x BMX-Broadcast-Suite-Setup-v1.3.0.msi PURGEUSERDATA=1
```

Normal uninstall stops and removes only the `BMXBroadcastSuite` service, then
removes the complete application-owned `%ProgramFiles%\BMX Broadcast Suite`
tree, shortcuts, and registration. Python bytecode generation is disabled for
the installed runtime, so the read-only Program Files tree does not accumulate
untracked caches. Unrelated Python processes are never searched for or stopped.
The protected ProgramData user-data directory remains unless
`PURGEUSERDATA=1` is explicitly supplied.

## Build and release gate

The build is offline and validates every pinned artifact:

```powershell
.\scripts\build-windows-installer.ps1 -CertificateThumbprint YOUR_SHA1_THUMBPRINT
```

For local testing only, use `-Unsigned`. Before publication, sign the MSI and scan the exact final file with current Defender definitions:

```powershell
.\scripts\test-windows-release-artifact.ps1 -Path .\dist\BMX-Broadcast-Suite-Setup-v1.3.0.msi
```

If Defender detects it, do not upload it; submit that exact artifact to Microsoft Security Intelligence. Outputs include the MSI, SHA-256 file, manifest, and CycloneDX SBOM.
