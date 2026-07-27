# Troubleshooting

## PowerShell says the script is not digitally signed

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start-windows.ps1
```

This only changes the current PowerShell session.

## SQL will not connect

Open `/diagnostics`. Confirm host, instance or port, database, login, ODBC driver, firewall, SQL TCP/IP, and that RaceManager is running. Test from the BBS computer, not only from the RaceManager computer.

## Blank OBS overlay

Open the same URL in Chrome or Edge on the OBS computer. Confirm the BBS address and port, Windows Firewall, and Browser Source dimensions. Refresh the OBS browser cache.

## Wrong moto or rider list

Confirm the Race Director's moto and phase. The cache is deliberately rejected for a different moto or phase. Check `/logs` for SQL errors and cache messages.

## Port already in use

Change `BBS_APP_PORT` in `.env`, restart BBS, and update all OBS URLs.

## Configuration changes do not apply

SQL and theme changes apply to new requests. Host, port, CORS, and logging startup settings require a restart.

## Useful evidence for a bug report

Include BBS version, diagnostics output, relevant downloaded log, operating system, RaceManager version if known, exact overlay URL, and steps to reproduce. Remove passwords before sharing files.
