# Windows Service and Tray

The v1.2.13 MSI installs an automatic Windows service named `BMXBroadcastSuite`. It uses the MSI's private Python runtime and WinSW 2.12.0; no console window, script launcher, or Scheduled Task is involved.

```powershell
Get-Service BMXBroadcastSuite
Start-Service BMXBroadcastSuite
Stop-Service BMXBroadcastSuite
Restart-Service BMXBroadcastSuite
```

The service runs `runtime\python.exe -m connector.run` from read-only Program Files. Configuration, credentials, logs, state, caches, and custom themes live in `%ProgramData%\BMX Broadcast Suite\UserData`, restricted to SYSTEM and Administrators. Default uninstall preserves this directory.

Desktop, Start Menu, and common Startup shortcuts launch `runtime\pythonw.exe -m connector.tray_windows` directly. The tray provides status, quick links, and UAC-scoped Start/Stop/Restart controls. Exiting the tray does not stop the service.
