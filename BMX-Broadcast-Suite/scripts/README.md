# Installation scripts

## Windows

From an Administrator PowerShell prompt at the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-windows.ps1
.\scripts\start-windows.ps1
```

Open `http://localhost:8000/diagnostics` and resolve any red checks.

## Linux / bmxServer01

Microsoft ODBC Driver 18 for SQL Server and the Unix ODBC development package must be installed before `pyodbc` can connect. Then run:

```bash
./scripts/install-linux.sh
./.venv/bin/python -m uvicorn connector.main:app --host 0.0.0.0 --port 8000
```

For boot-time operation, copy and edit `bbs-connector.service.example`, then install it with systemd.
