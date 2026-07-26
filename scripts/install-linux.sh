#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v python3 >/dev/null || { echo "Python 3 is required." >&2; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r connector/requirements.txt
if [[ ! -f .env ]]; then cp connector/.env.example .env; echo "Created .env; configure BBS_SQL_PASSWORD before live use."; fi
mkdir -p data
cat <<EOF
BBS installed in $ROOT
Start: $ROOT/.venv/bin/python -m connector.run
Diagnostics: http://localhost:8000/diagnostics
EOF
