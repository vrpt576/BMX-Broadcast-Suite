# Linux Installation Guide

BBS 1.2.0 is supported on current Ubuntu and Debian-family systems. The verified production setup uses native OBS Studio, Python 3.11 or newer, Microsoft ODBC Driver 18, and wired access to the RaceManager SQL Server host.

## Prerequisites

- 64-bit Ubuntu or Debian-family Linux
- Python 3.11 or newer with the `venv` module
- Git
- unixODBC development libraries
- Microsoft ODBC Driver 18 for SQL Server
- Network access to the RaceManager SQL Server host and port
- OBS Studio with Browser Source support for broadcast graphics

Install the base packages:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv unixodbc unixodbc-dev curl ca-certificates
```

Install **Microsoft ODBC Driver 18 for SQL Server** using Microsoft's package instructions for your exact distribution. Confirm that it is visible before continuing:

```bash
odbcinst -q -d | grep "ODBC Driver 18 for SQL Server"
```

## Install native OBS Studio

The Snap build is not recommended for BBS production because Browser Source/plugin availability can differ from the native package. On Ubuntu, install OBS from the official OBS Studio PPA:

```bash
sudo add-apt-repository ppa:obsproject/obs-studio
sudo apt update
sudo apt install -y obs-studio
```

Confirm the native executable and version:

```bash
command -v obs
obs --version
```

## Install BBS

```bash
git clone https://github.com/vrpt576/BMX-Broadcast-Suite.git
cd BMX-Broadcast-Suite
chmod +x scripts/install-linux.sh
./scripts/install-linux.sh
./.venv/bin/python -m connector.run
```

Open these pages from the BBS computer or another computer on the same network:

- Configuration: `http://SERVER-IP:8000/configuration`
- Diagnostics: `http://SERVER-IP:8000/diagnostics`
- Controller: `http://SERVER-IP:8000/controller`

Do not commit `.env`; it contains local settings and may contain the SQL password.

## Validation

The diagnostics page should confirm:

- Python and application health
- ODBC Driver 18 availability
- SQL Server network reachability
- successful SQL login
- the `RACE` database
- a current RaceManager event and motoboard

BBS 1.2.0 automatically detects whether the RaceManager `MB.Race_Riders` table includes the optional `Nickname` column. Older schemas return `nickname: null` and continue serving lineups.

## systemd

Copy and edit `scripts/bbs-connector.service.example`, then:

```bash
sudo cp scripts/bbs-connector.service.example /etc/systemd/system/bbs-connector.service
sudo systemctl daemon-reload
sudo systemctl enable --now bbs-connector
sudo systemctl status bbs-connector
```

Use `journalctl -u bbs-connector -f` and the BBS `/logs` page for troubleshooting.

## Run BBS as a background service

BBS 1.2.9 can start automatically at machine boot and run without a terminal window. It also includes a desktop and system-tray controller using `logo.png`.

Install the desktop integration packages and service after completing the normal installation:

```bash
sudo apt install -y python3-gi gir1.2-ayatanaappindicator3-0.1 policykit-1 libnotify-bin
./scripts/install-service-linux.sh
```

See [Linux Background Service and Tray Icon](service-linux.md) for operation, logs, upgrades, and removal.
