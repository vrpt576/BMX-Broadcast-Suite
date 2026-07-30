# Windows Setup Wizard

BBS 1.2.6 includes a graphical Windows installer:

```text
BMX-Broadcast-Suite-Setup-v1.2.6.exe
```

The wizard checks for Python 3.11+ and Microsoft ODBC Driver 18 for SQL Server, lets the operator choose an installation folder, installs the Python environment, and optionally registers BBS to start at machine boot. It also installs the desktop, Start Menu, and notification-area controls supplied by BBS.

## Before running the wizard

Install:

- Python 3.11 or newer from python.org; enable the Python launcher during setup.
- Microsoft ODBC Driver 18 for SQL Server.
- OBS Studio when overlays will be displayed on this computer.

The installer is currently unsigned, so Windows SmartScreen may show an Unknown Publisher warning. Verify that the installer came from the official BBS GitHub release before choosing **Run anyway**.

## Install

1. Right-click `BMX-Broadcast-Suite-Setup-v1.2.6.exe` and choose **Run as administrator**.
2. Confirm both prerequisite checks are green.
3. Choose the installation folder.
4. Leave machine-startup enabled for a race-day computer.
5. Select **Install**.
6. Complete RaceManager settings at `http://localhost:8000/configuration`.
7. Confirm `http://localhost:8000/diagnostics` is healthy.

The original PowerShell installation remains supported for administrators and development installations.

## Build the EXE

On Windows, from the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build-windows-installer.ps1
```

The generated EXE is written to `dist`. The builder uses Windows IExpress, which is included with supported Windows editions, and embeds a clean source payload plus the setup wizard.
