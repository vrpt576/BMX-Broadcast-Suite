# Windows Background Operation and Tray Icon

BBS 1.2.9 can run on Windows 10/11 without an open PowerShell window. A machine-wide Scheduled Task starts the connector at boot under the built-in `SYSTEM` account and restarts it after failures. A separate notification-area application shows status and controls the background runner.

## Install

Complete the normal [Windows installation](installation-windows.md), configure `.env`, and verify `/diagnostics`. Then open PowerShell as Administrator:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-service-windows.ps1
```

The installer:

- registers `BMX Broadcast Suite` in Task Scheduler
- starts BBS at machine boot, before a user logs in
- runs BBS invisibly as `SYSTEM` using the installed private
  `.venv\Scripts\python.exe`, `-m connector.run`, and the installation folder
  as its working directory
- retries once per minute after an unexpected failure
- generates `data\bbs.ico` from `logo.png`
- creates desktop and Start Menu launchers
- starts the tray icon automatically at user login
- starts BBS and the tray immediately

The setup wizard waits for `/health` before opening Configuration, so the
first page load does not require manually starting BBS from the tray.

Installed code under Program Files is read-only during normal operation.
Mutable operator and runtime data lives at:

```text
%ProgramData%\BMX Broadcast Suite\UserData
```

This includes `.env`, `connector\logs`, `data` state and caches, and custom
`themes`. Bundled themes remain available from the installation folder.

## Tray status and controls

Hover over the BBS icon to see connector, RaceManager, moto, and class status. Right-click it for:

- Open Race Director
- Open Configuration
- Open Diagnostics
- Open Logs
- Open Lineup Preview
- Start BBS
- Stop BBS
- Restart BBS
- Exit Tray Icon

Start, Stop, and Restart use a Windows User Account Control prompt because the background task is machine-wide. Exiting the tray icon does not stop BBS.

## Manual control

Open Task Scheduler and locate `BMX Broadcast Suite`, or use an Administrator PowerShell:

```powershell
Start-ScheduledTask -TaskName "BMX Broadcast Suite"
Stop-ScheduledTask -TaskName "BMX Broadcast Suite"
Get-ScheduledTaskInfo -TaskName "BMX Broadcast Suite"
```

Start only the tray:

```powershell
.\scripts\start-tray-windows.ps1
```

## Upgrade

Stop the task, update the application, reinstall dependencies, and rerun the service installer. Operator data under ProgramData is preserved:

```powershell
Stop-ScheduledTask -TaskName "BMX Broadcast Suite"
git pull
.\.venv\Scripts\python.exe -m pip install -r connector\requirements.txt
.\scripts\install-service-windows.ps1
```

The installer replaces the task definition and launchers without deleting configuration or runtime data.

## Remove background integration

Run PowerShell as Administrator:

```powershell
.\scripts\uninstall-service-windows.ps1
```

This removes the Scheduled Task and shortcuts. It preserves the repository and
all operator data under `%ProgramData%\BMX Broadcast Suite\UserData`.

## Uninstall the application

For an installation created by the setup EXE:

1. Open **Settings → Apps → Installed apps**.
2. Find **BMX Broadcast Suite**.
3. Select **Uninstall** and approve the Windows elevation prompt.

The uninstaller:

- verifies the requested folder is a BBS installation before deleting it
- stops and removes only the `BMX Broadcast Suite` Scheduled Task whose
  executable belongs to that installation
- stops only `connector.run` and `connector.tray_windows` processes using the
  installation's private `.venv` Python executable
- removes BBS-owned desktop, Start Menu, and Startup shortcuts
- removes matching legacy BBS Windows services, if present
- removes the Apps & Features registry entry
- removes installed application files

It does not stop unrelated Python processes.

### Preserved operator data

By default these items are copied to:

```text
%ProgramData%\BMX Broadcast Suite\UserData
```

Preserved items are:

- `.env` configuration and SQL credentials
- `config.json`, when present
- `connector\logs`
- `themes`, including track customizations
- `data`, including current-moto state, caches, and local race data

The preserved folder is restricted to the local SYSTEM account and
Administrators because `.env` can contain SQL credentials.

The setup wizard automatically restores these files during a reinstall.

To remove preserved data manually after uninstall:

```powershell
Remove-Item "$env:ProgramData\BMX Broadcast Suite\UserData" -Recurse -Force
```

To uninstall from an Administrator PowerShell:

```powershell
& "C:\Program Files\BMX Broadcast Suite\scripts\uninstall-windows.ps1"
```

Quiet uninstall, while still preserving operator data:

```powershell
& "C:\Program Files\BMX Broadcast Suite\scripts\uninstall-windows.ps1" -Quiet
```

Explicitly remove both the application and preserved operator data:

```powershell
& "C:\Program Files\BMX Broadcast Suite\scripts\uninstall-windows.ps1" -PurgeUserData
```

`-PurgeUserData` is irreversible and is never used by Apps & Features.

## Troubleshooting

- If the tray icon is absent, run `scripts\start-tray-windows.ps1`.
- If BBS is stopped, open Diagnostics after starting the task.
- If another process already uses port 8000, change `BBS_APP_PORT` in `.env`, reinstall the task, and set `BBS_TRAY_BASE_URL` for the tray.
- If the service can reach BBS but not SQL Server, verify the SQL host, dynamic TCP port, firewall, ODBC Driver 18, and SQL login.
- If Windows blocks a script, use `Set-ExecutionPolicy -Scope Process Bypass`; this affects only the current PowerShell session.
