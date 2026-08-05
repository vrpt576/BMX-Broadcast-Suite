# Windows Installation Guide

Install Microsoft ODBC Driver 18 for SQL Server (64-bit), then install `BMX-Broadcast-Suite-Setup-v1.2.12.msi`. Python and all Python packages are included; setup performs no downloads.

After setup, open BMX Broadcast Suite from the desktop or Start Menu, choose Configuration, enter RaceManager SQL settings, and verify `http://127.0.0.1:8000/diagnostics`.

The `BMXBroadcastSuite` service starts at boot. Source/development installs may still use `scripts\install-windows.ps1` and `scripts\start-windows.ps1`, but those scripts are not part of the MSI flow.

Remote access remains disabled by default. See the main README before changing bind host, CORS origins, or control/admin tokens. See [Windows MSI Installer](wizard-installer-windows.md) and [Windows Service and Tray](service-windows.md).
