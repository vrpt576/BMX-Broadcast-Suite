# Changelog

## 1.2.4

- Added Windows 10/11 background operation through a machine startup Scheduled Task running as `SYSTEM`.
- Added automatic restart after failure and start-at-boot behavior without an open terminal.
- Added a Windows notification-area controller with live service, API, RaceManager, moto, and class status.
- Added Start, Stop, and Restart controls with Windows elevation prompts.
- Added desktop, Start Menu, and login-start tray shortcuts using an ICO generated from `logo.png`.
- Added Windows background installation, removal, and tray-launch scripts.
- Preserved the existing Ubuntu `systemd` service and AppIndicator tray implementation.
- Added Windows service/tray documentation and platform status tests.

## 1.2.3

- Reworked the main README to reflect the current production status, known limitations, and verified Ubuntu workflow.
- Replaced the original phase roadmap with shipped, near-term, mid-term, and platform-expansion priorities.
- Expanded theme colors for secondary accents, headers, alternate panels, odd/even rows, lane cells, plate numbers, dividers, shadows, and warning banners.
- Applied theme customization consistently to current-moto, lineup, and results overlays.
- Added a complete theme customization guide and updated bundled theme packages.

## 1.2.1

- Added an Ubuntu/Linux machine-wide systemd service that starts BBS at boot and restarts it after failures.
- Added a desktop and system-tray launcher using `logo.png`.
- Added live service, connector API, RaceManager, current-moto, and class status in the tray menu.
- Added tray shortcuts for Controller, Configuration, Diagnostics, Logs, and lineup preview.
- Added authenticated start, stop, and restart controls for the machine service.
- Added service installation and removal scripts plus Linux service documentation.

## 1.2.0

- Added automatic RaceManager schema detection for the optional `MB.Race_Riders.Nickname` column.
- Preserved the `nickname` API field as `null` on older RaceManager databases instead of failing lineup queries.
- Updated Ubuntu/Debian prerequisites and installer checks for Python virtual environments and Microsoft ODBC Driver 18.
- Documented native OBS Studio installation, Browser Source requirements, overlay URLs, preview mode, diagnostics, and the verified troubleshooting workflow.
- Updated application and diagnostics version reporting to 1.2.0.

## 1.1.0

- Added centralized console and daily rotating file logging.
- Added `/logs`, `/api/logs`, and log download support.
- Added request timing, startup, exception, and database error logging.
- Added configurable log directory, level, and retention.
- Added complete Windows/Linux installation, first-run, configuration, OBS, browser-source, troubleshooting, FAQ, shortcut, upgrading, and backup/restore guides.


## 0.9.0

- Added last-known-good lineup cache and stale-data metadata.
- Preserves the last valid lineup through temporary SQL Server outages.
- Added automatic class-name synchronization from RaceManager.
- Added a WebSocket broadcast snapshot feed and overlay WebSocket clients.
- Added experimental results API and OBS results overlay.
- Added Race Director results controls and backward-move confirmations.
- Added resilience and results unit tests.

## 0.8.0

- Added installation scripts and diagnostics dashboard.

## 1.0.0
- Removed Bend-specific SQL defaults from application code.
- Added `/configuration` setup screen and `/api/configuration` API.
- Made track name, theme, application host/port, SQL host/instance/port/database/login/password/driver, timeouts, CORS, and state paths configurable through `.env`.
- Added config-aware Windows, Linux, Docker, and systemd launch commands.
- Password values are write-only in the configuration UI and never returned by the API.
