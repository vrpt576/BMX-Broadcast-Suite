# Changelog

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
