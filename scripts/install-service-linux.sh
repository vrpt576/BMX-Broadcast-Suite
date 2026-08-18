#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_NAME="bbs-connector.service"
INSTALL_USER="${SUDO_USER:-$USER}"
INSTALL_GROUP="$(id -gn "$INSTALL_USER")"
USER_HOME="$(getent passwd "$INSTALL_USER" | cut -d: -f6)"

if [[ $EUID -eq 0 ]]; then
    SUDO=""
else
    command -v sudo >/dev/null || { echo "sudo is required." >&2; exit 1; }
    SUDO="sudo"
fi

[[ -x "$ROOT/.venv/bin/python" ]] || {
    echo "BBS virtual environment was not found. Run scripts/install-linux.sh first." >&2
    exit 1
}
[[ -f "$ROOT/.env" ]] || {
    echo "BBS .env was not found. Configure BBS before installing the service." >&2
    exit 1
}
command -v systemctl >/dev/null || { echo "systemd is required." >&2; exit 1; }

TMP_UNIT="$(mktemp)"
TMP_DESKTOP="$(mktemp)"
trap 'rm -f "$TMP_UNIT" "$TMP_DESKTOP"' EXIT

sed \
    -e "s|@BBS_ROOT@|$ROOT|g" \
    -e "s|@BBS_USER@|$INSTALL_USER|g" \
    -e "s|@BBS_GROUP@|$INSTALL_GROUP|g" \
    "$ROOT/packaging/linux/bbs-connector.service" > "$TMP_UNIT"

sed -e "s|@BBS_ROOT@|$ROOT|g" \
    "$ROOT/packaging/linux/bbs-tray.desktop" > "$TMP_DESKTOP"

$SUDO install -m 0644 "$TMP_UNIT" "/etc/systemd/system/$UNIT_NAME"
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now "$UNIT_NAME"

install -d -m 0755 "$USER_HOME/.local/share/applications" "$USER_HOME/.config/autostart"
install -m 0644 "$TMP_DESKTOP" "$USER_HOME/.local/share/applications/bbs-tray.desktop"
install -m 0644 "$TMP_DESKTOP" "$USER_HOME/.config/autostart/bbs-tray.desktop"
chown "$INSTALL_USER:$INSTALL_GROUP" \
    "$USER_HOME/.local/share/applications" "$USER_HOME/.config/autostart" \
    "$USER_HOME/.local/share/applications/bbs-tray.desktop" \
    "$USER_HOME/.config/autostart/bbs-tray.desktop"

# Desktop copies may require the trusted metadata flag on GNOME. Failure is harmless.
if [[ -d "$USER_HOME/Desktop" ]]; then
    install -m 0755 "$TMP_DESKTOP" "$USER_HOME/Desktop/BMX Broadcast Suite.desktop"
    chown "$INSTALL_USER:$INSTALL_GROUP" "$USER_HOME/Desktop/BMX Broadcast Suite.desktop"
    if command -v runuser >/dev/null && command -v gio >/dev/null; then
        runuser -u "$INSTALL_USER" -- gio set "$USER_HOME/Desktop/BMX Broadcast Suite.desktop" metadata::trusted true 2>/dev/null || true
    fi
fi

cat <<OUT
BBS 1.2.13 machine service installed and started.

Service:    systemctl status $UNIT_NAME
Controller: http://localhost:8000/controller
Diagnostics:http://localhost:8000/diagnostics
Tray icon:  starts automatically at the next desktop login

Start the tray now with:
  $ROOT/scripts/start-tray-linux.sh
OUT
