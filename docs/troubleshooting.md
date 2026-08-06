# Troubleshooting

## PowerShell says the script is not digitally signed

```powershell
Unblock-File .\scripts\start-windows.ps1
.\scripts\start-windows.ps1
```

Only unblock a script after verifying that it came from the official project
repository. The MSI installation does not depend on PowerShell scripts.

## SQL will not connect

Follow [Prepare the USA BMX RaceManager PC for BBS](racemanager-pc-setup.md), then open `/diagnostics`. Confirm host, instance or port, `RACE` database, `bbs_connector` login, ODBC driver, firewall, SQL TCP/IP, and that RaceManager is running. Test the discovered port from the BBS computer, not only from the RaceManager computer.

When using a TCP port, leave the BBS SQL instance field blank. BBS gives a named instance precedence over the port. Never expose the SQL port to the public Internet.

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

## Lineup API reports `Invalid column name 'Nickname'`

This indicates a pre-1.2.0 connector is querying a RaceManager schema that does not contain the optional `MB.Race_Riders.Nickname` column. Upgrade to BBS 1.2.0 or newer. Version 1.2.0 detects the column and returns `nickname: null` when it is absent.

Verify the endpoint directly:

```bash
curl http://localhost:8000/api/lineup/current
```

A healthy response contains moto, class, rider, source, and freshness fields rather than HTTP 503.

## Current overlay appears but lineup is blank

The normal lineup URL obeys broadcast controller state. During setup, use:

`http://localhost:8000/overlay/lineup?preview=true`

For live operation, use the URL without preview mode and activate the lineup through `/controller`.

## Browser Source is missing from OBS

Use the native OBS Studio package rather than the Snap build. See [OBS Setup](obs-setup.md).
