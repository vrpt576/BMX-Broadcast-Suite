# Windows Installation Guide

For the simplest installation, download and run `BMX-Broadcast-Suite-Setup-v1.2.5.exe` from the GitHub release. See the [Windows Setup Wizard](wizard-installer-windows.md). The commands below remain available for development and advanced installation.

## Requirements

- Windows 10 or 11
- Python 3.11 or newer
- Git for Windows
- Microsoft ODBC Driver 18 for SQL Server
- Network access to the RaceManager computer

## Install

1. Open PowerShell and clone the repository:

```powershell
git clone https://github.com/vrpt576/BMX-Broadcast-Suite.git
cd BMX-Broadcast-Suite
```

2. Run the installer. If PowerShell blocks unsigned scripts, use a process-only bypass:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\install-windows.ps1
```

To install dependencies and immediately register BBS for machine startup:

```powershell
.\scripts\install-windows.ps1 -InstallService
```

3. Start BBS:

```powershell
.\scripts\start-windows.ps1
```

You may also bypass the script and run `\.venv\Scripts\python.exe -m connector.run`.

4. Open `http://localhost:8000/configuration` and enter the track settings.

## Run without a terminal

After configuration, open an Administrator PowerShell window and run:

```powershell
.\scripts\install-service-windows.ps1
```

This creates a machine startup task named `BMX Broadcast Suite`, runs the connector as `SYSTEM`, restarts it after failures, and installs desktop, Start Menu, and notification-area launchers. See [Windows Background Operation and Tray](service-windows.md).

## Firewall

Allow inbound TCP traffic on the configured BBS port, normally 8000, when OBS or the Race Director runs on another computer. Windows may prompt for this the first time BBS starts.

## Updating

Stop BBS, back up `.env` and custom themes, run `git pull`, update dependencies, test diagnostics, then restart. See [Upgrading](upgrading.md).
