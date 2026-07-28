#!/usr/bin/env bash
set -euo pipefail
UNIT_NAME="bbs-connector.service"
INSTALL_USER="${SUDO_USER:-$USER}"
USER_HOME="$(getent passwd "$INSTALL_USER" | cut -d: -f6)"

if [[ $EUID -eq 0 ]]; then SUDO=""; else SUDO="sudo"; fi

$SUDO systemctl disable --now "$UNIT_NAME" 2>/dev/null || true
$SUDO rm -f "/etc/systemd/system/$UNIT_NAME"
$SUDO systemctl daemon-reload
$SUDO systemctl reset-failed
rm -f "$USER_HOME/.local/share/applications/bbs-tray.desktop"
rm -f "$USER_HOME/.config/autostart/bbs-tray.desktop"
rm -f "$USER_HOME/Desktop/BMX Broadcast Suite.desktop"

echo "BBS service and launchers removed. Project files and configuration were preserved."
