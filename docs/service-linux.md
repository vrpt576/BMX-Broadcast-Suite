# Linux Background Service and Tray Icon

BBS 1.2.8 can run as a machine-wide systemd service on Ubuntu/Linux. The connector starts during boot, does not need an open terminal, and automatically restarts after a failure.

The service runs as the user who installs it, so it retains access to that user's BBS project, `.env`, data, themes, and logs. It is still machine-wide and starts before desktop login.

## Prerequisites

Install BBS normally first, including its virtual environment and `.env` configuration. For the desktop tray icon, install the Ubuntu desktop integration packages:

```bash
sudo apt update
sudo apt install -y python3-gi gir1.2-ayatanaappindicator3-0.1 policykit-1 libnotify-bin
```

`logo.png` in the project root is used for the tray and desktop launcher.

## Install and start at boot

From the BBS project root:

```bash
chmod +x scripts/install-service-linux.sh scripts/start-tray-linux.sh
./scripts/install-service-linux.sh
```

The installer:

- creates `/etc/systemd/system/bbs-connector.service`
- enables and starts the connector immediately
- enables automatic startup at machine boot
- installs an application-menu launcher
- installs a desktop shortcut when a Desktop directory exists
- starts the tray automatically at the next graphical login

Start the tray immediately without logging out:

```bash
./scripts/start-tray-linux.sh
```

## Tray status and controls

Open the BBS icon in the system tray to see:

- system service state
- connector API availability
- RaceManager connection state
- current moto and class when available

The menu also provides links to Controller, Configuration, Diagnostics, Logs, and lineup preview, along with Start, Stop, and Restart controls.

Because BBS is a machine service, changing its state requires administrative authorization. Ubuntu displays a PolicyKit authentication prompt when Start, Stop, or Restart is selected. Exiting the tray icon does not stop the connector service.

GNOME and AppIndicator do not provide a portable custom hover flyout. BBS therefore presents the live status in the tray menu, which is the reliable behavior across supported Ubuntu desktop versions.

## Service commands

```bash
sudo systemctl status bbs-connector
sudo systemctl restart bbs-connector
sudo systemctl stop bbs-connector
sudo systemctl start bbs-connector
sudo systemctl disable bbs-connector
sudo systemctl enable bbs-connector
```

Follow the machine-service log:

```bash
journalctl -u bbs-connector -f
```

Application logs remain available through `http://localhost:8000/logs` and in `connector/logs`.

## Upgrade

After replacing project files with a newer release, reinstall Python requirements if they changed, then restart:

```bash
./.venv/bin/python -m pip install -r connector/requirements.txt
sudo systemctl restart bbs-connector
```

Re-run `./scripts/install-service-linux.sh` when the service template or launchers change.

## Remove the service

```bash
./scripts/uninstall-service-linux.sh
```

This removes the systemd unit and desktop launchers but preserves the BBS project, `.env`, data, themes, and logs.

## Status API

Desktop integrations can read the compact connector status endpoint:

```text
http://localhost:8000/api/status
```

It reports the BBS version, connector state, RaceManager connection, track, current moto, race phase, and class. The tray combines this response with the machine service state reported by systemd.
