# Windows Background Operation and Tray Icon

BBS 1.2.5 can run on Windows 10/11 without an open PowerShell window. A machine-wide Scheduled Task starts the connector at boot under the built-in `SYSTEM` account and restarts it after failures. A separate notification-area application shows status and controls the background runner.

## Install

Complete the normal [Windows installation](installation-windows.md), configure `.env`, and verify `/diagnostics`. Then open PowerShell as Administrator:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-service-windows.ps1
```

The installer:

- registers `BMX Broadcast Suite` in Task Scheduler
- starts BBS at machine boot, before a user logs in
- runs BBS without a terminal using `.venv\Scripts\pythonw.exe`
- retries once per minute after an unexpected failure
- generates `data\bbs.ico` from `logo.png`
- creates desktop and Start Menu launchers
- starts the tray icon automatically at user login
- starts BBS and the tray immediately

Project files, `.env`, themes, logs, cache, and race state remain in the repository directory.

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

Stop the task, back up `.env` and custom themes, update the repository, reinstall dependencies, and rerun the service installer:

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

This removes the Scheduled Task and shortcuts. It preserves the repository, `.env`, themes, logs, cache, and race state.

## Troubleshooting

- If the tray icon is absent, run `scripts\start-tray-windows.ps1`.
- If BBS is stopped, open Diagnostics after starting the task.
- If another process already uses port 8000, change `BBS_APP_PORT` in `.env`, reinstall the task, and set `BBS_TRAY_BASE_URL` for the tray.
- If the service can reach BBS but not SQL Server, verify the SQL host, dynamic TCP port, firewall, ODBC Driver 18, and SQL login.
- If Windows blocks a script, use `Set-ExecutionPolicy -Scope Process Bypass`; this affects only the current PowerShell session.
