# Windows Installation Guide

Before installing BBS, follow [Prepare the USA BMX RaceManager PC for BBS](racemanager-pc-setup.md). That guide enables the SQL network connection, creates a dedicated `db_datareader` login, and restricts the Windows Firewall rule to the BBS computer. It does not modify RaceManager tables or race data.

Install Microsoft ODBC Driver 18 for SQL Server (64-bit), then download and install the [latest BBS Windows MSI](https://github.com/vrpt576/BMX-Broadcast-Suite/releases/latest). Python and all Python packages are included; setup performs no downloads.

After setup, open BMX Broadcast Suite from the desktop or Start Menu, choose Configuration, and enter the RaceManager PC's LAN address, discovered SQL port, `RACE` database, and dedicated read-only credentials. Leave the SQL instance blank when using a TCP port; BBS gives a named instance precedence over the port. Verify the result at `http://127.0.0.1:8000/diagnostics`.

The `BMXBroadcastSuite` service starts at boot. Source/development installs may still use `scripts\install-windows.ps1` and `scripts\start-windows.ps1`, but those scripts are not part of the MSI flow.

Remote BBS administration remains disabled by default. Keep RaceManager SQL traffic on a trusted LAN, restrict the SQL firewall rule to the BBS computer, and never forward the SQL port through an Internet router. See the main README before changing bind host, CORS origins, or control/admin tokens. See [Windows MSI Installer](wizard-installer-windows.md) and [Windows Service and Tray](service-windows.md).
