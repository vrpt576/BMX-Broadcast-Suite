# Linux Installation Guide

Tested workflow for Ubuntu and Debian-family systems.

## Packages

```bash
sudo apt update
sudo apt install -y git python3 python3-venv unixodbc unixodbc-dev
```

Install Microsoft ODBC Driver 18 using Microsoft's instructions for your distribution.

## Install BBS

```bash
git clone https://github.com/vrpt576/BMX-Broadcast-Suite.git
cd BMX-Broadcast-Suite
chmod +x scripts/install-linux.sh
./scripts/install-linux.sh
./.venv/bin/python -m connector.run
```

Open `http://SERVER-IP:8000/configuration`.

## systemd

Copy and edit `scripts/bbs-connector.service.example`, then:

```bash
sudo cp scripts/bbs-connector.service.example /etc/systemd/system/bbs-connector.service
sudo systemctl daemon-reload
sudo systemctl enable --now bbs-connector
sudo systemctl status bbs-connector
```

Use `journalctl -u bbs-connector -f` and the BBS `/logs` page for troubleshooting.
