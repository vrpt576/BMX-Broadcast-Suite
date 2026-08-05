# Windows installer security and antivirus policy

## Why the v1.2.9 and v1.2.10 EXEs were flagged

Those releases used an unsigned IExpress/WEXTRACT executable that unpacked a
nested archive and launched hidden VBScript and PowerShell with elevation and
`ExecutionPolicy Bypass`. The scripts installed hidden background Python,
created SYSTEM startup persistence, wrote machine registry entries, and used a
temporary self-removing uninstall worker. Each behavior had an installation
purpose, but their combination closely resembles common malware deployment
patterns and triggered Microsoft Defender's machine-learning detection
`Trojan:Win32/Wacatac.B!ml`.

Source review has not established malicious intent or behavior. It also cannot
establish that a particular compiled artifact is safe. Do not disable Defender
or add a broad exclusion to install a detected artifact.

## v1.2.11 remediation

The Windows package is now a WiX Toolset v4 MSI. Windows Installer owns file,
service, shortcut, upgrade, repair, and uninstall operations. The package has
no IExpress or WEXTRACT layer, no VBScript bootstrap, no hidden PowerShell
launcher, no execution-policy bypass, and no self-deleting uninstall worker.
The connector runs as the narrowly named `BMXBroadcastSuite` Windows service
through the pinned WinSW wrapper.

Build inputs are offline and hash-locked. The build emits the MSI, SHA-256,
payload manifest, and CycloneDX SBOM. Release builds support Authenticode
signing and refuse to proceed unless a certificate is supplied or the operator
explicitly selects the local-validation-only unsigned mode.

## Public release gate

Before publishing a Windows binary:

1. Build from the clean release tag.
2. Sign the MSI and bundled service wrapper with the project's trusted
   code-signing certificate. If none is available, record that limitation.
3. Run `scripts/test-windows-release-artifact.ps1` against the exact final MSI.
4. Record filename, size, SHA-256, Authenticode status, Defender engine and
   definition versions, and scan result.
5. If Defender detects the file, do not publish it. Submit that exact binary to
   Microsoft Security Intelligence and keep the GitHub release draft or
   source-only until Microsoft returns a determination.

The v1.2.9 and v1.2.10 source tags should remain intact. Any detected EXE assets
should be removed from public download or prominently marked as withdrawn;
historical tags do not need to be rewritten.
