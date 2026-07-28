#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARNING: $*" >&2; }

command -v python3 >/dev/null || fail "Python 3 is required."
python3 - <<'PY' || exit 1
import sys
if sys.version_info < (3, 11):
    raise SystemExit("ERROR: Python 3.11 or newer is required.")
print(f"Python {sys.version.split()[0]} detected")
PY

python3 -m venv --help >/dev/null 2>&1 || fail "python3-venv is required. Install it with: sudo apt install python3-venv"
command -v odbcinst >/dev/null || fail "unixODBC is required. Install unixodbc and unixodbc-dev."

if ! odbcinst -q -d 2>/dev/null | grep -Fq "ODBC Driver 18 for SQL Server"; then
    warn "Microsoft ODBC Driver 18 for SQL Server was not detected. Install it before connecting to RaceManager."
fi

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r connector/requirements.txt

if [[ ! -f .env ]]; then
    cp connector/.env.example .env
    echo "Created .env; open /configuration or edit .env before live use."
fi

mkdir -p data connector/logs

cat <<EOF2
BBS 1.2.0 installed in $ROOT
Start:       $ROOT/.venv/bin/python -m connector.run
Configuration: http://localhost:8000/configuration
Diagnostics:   http://localhost:8000/diagnostics
Controller:    http://localhost:8000/controller
OBS setup:     docs/obs-setup.md
EOF2
