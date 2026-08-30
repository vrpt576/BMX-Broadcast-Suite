# Windows installer security and antivirus policy

## Current signing status

BBS's Windows releases are currently unsigned -- this project does not
yet hold a code-signing certificate. Every MSI published to date is
unsigned; this is the current state of the project, not a hypothetical
fallback. Concretely, that means:

- Windows SmartScreen shows its "Windows protected your PC" warning the
  first time anyone runs the installer, because Windows can't verify a
  publisher identity for an unsigned file. See
  [Windows MSI Installer](wizard-installer-windows.md) for what an
  operator sees and how to continue past it.
- There's no Authenticode signature to check in the file's Properties ->
  Digital Signatures tab.
- Verify the file's integrity instead: compare its SHA-256 against the
  value published alongside it on the
  [GitHub release page](https://github.com/vrpt576/BMX-Broadcast-Suite/releases)
  before installing it (`Get-FileHash -Algorithm SHA256 <file>` in
  PowerShell). This proves the file matches what the project published;
  it doesn't establish who published it the way a code signature would
  -- the manifest, SBOM, and Defender scan that accompany every release
  exist as part of substituting for that.

Signing is planned for a future release -- see `ROADMAP.md`.

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
payload manifest, and CycloneDX SBOM. The build script supports Authenticode
signing when a certificate is supplied, and an explicit unsigned mode when
one isn't -- see "Current signing status" above for why current releases
use the latter.

## Public release gate

Before publishing a Windows binary:

1. Build from the clean release tag.
2. If a code-signing certificate is available, sign the MSI and bundled
   service wrapper with it. If none is available -- the current
   situation, see "Current signing status" above -- build unsigned with
   `-Unsigned` and publish it as such; state that plainly in the release
   notes rather than shipping it silently.
3. Run `scripts/test-windows-release-artifact.ps1` against the exact
   final MSI (add `-AllowUnsigned` for an unsigned build).
4. Record filename, size, SHA-256, Authenticode status, Defender engine and
   definition versions, and scan result.
5. If Defender detects the file, do not publish it. Submit that exact binary to
   Microsoft Security Intelligence and keep the GitHub release draft or
   source-only until Microsoft returns a determination.

The v1.2.9 and v1.2.10 source tags should remain intact. Any detected EXE assets
should be removed from public download or prominently marked as withdrawn;
historical tags do not need to be rewritten.
