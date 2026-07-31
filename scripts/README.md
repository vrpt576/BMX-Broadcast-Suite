# Installation scripts

## Windows

From an Administrator PowerShell prompt at the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-windows.ps1
.\scripts\start-windows.ps1
```

Open `http://localhost:8000/diagnostics` and resolve any red checks.

For machine startup, automatic restart, desktop/Start Menu launchers, and the tray controller:

```powershell
.\scripts\install-service-windows.ps1
```

Remove only the background integration with:

```powershell
.\scripts\uninstall-service-windows.ps1
```

Packaged installations register with Apps & Features. Remove the full
application while preserving operator data with:

```powershell
.\scripts\uninstall-windows.ps1
```

Run the non-administrative packaging smoke test with:

```powershell
.\scripts\validate-windows-uninstall.ps1
```

## Linux / bmxServer01

Microsoft ODBC Driver 18 for SQL Server and the Unix ODBC development package must be installed before `pyodbc` can connect. Then run:

```bash
./scripts/install-linux.sh
./.venv/bin/python -m uvicorn connector.main:app --host 0.0.0.0 --port 8000
```

For boot-time operation, copy and edit `bbs-connector.service.example`, then install it with systemd.
