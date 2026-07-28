#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Avoid duplicate tray indicators in the same desktop session.
if pgrep -u "$(id -u)" -f "python3 -m connector.tray" >/dev/null 2>&1; then
    exit 0
fi

exec /usr/bin/python3 -m connector.tray
