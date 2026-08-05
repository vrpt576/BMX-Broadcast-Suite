# Installation and release scripts

Windows end users install the WiX MSI. It owns the `BMXBroadcastSuite` service, Apps & Features entry, upgrades, shortcuts, and uninstall; operator data in ProgramData is preserved by default.

```powershell
.\scripts\build-windows-installer.ps1 -CertificateThumbprint YOUR_SHA1_THUMBPRINT
.\scripts\test-windows-release-artifact.ps1 -Path .\dist\BMX-Broadcast-Suite-Setup-v1.2.12.msi
```

`-Unsigned` is only for local packaging validation. The installer build and install are offline and never alter PowerShell execution policy. Source developers can use `install-windows.ps1`, `start-windows.ps1`, and `start-tray-windows.ps1` directly.

On Linux, install ODBC prerequisites, then run `install-linux.sh`; use `install-service-linux.sh` for systemd operation.
