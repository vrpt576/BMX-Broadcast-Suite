# BMX Broadcast Suite

[![Build Status](https://img.shields.io/badge/build-v1.2.1-informational)](https://github.com/vrpt576/BMX-Broadcast-Suite)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen)](CONTRIBUTING.md)

## Project description

BMX Broadcast Suite is an open-source platform for live BMX race production. It is designed to connect USABMX RaceManager data with OBS Studio to support professional graphics, rider information, and event overlays during live broadcasts.

## Project philosophy

We aim to make BMX event streaming accessible, flexible, and community-driven. The project focuses on:

- modular integration with existing race management tools
- transparent and maintainable live broadcast workflows
- theme-driven visuals and reliable data delivery
- open collaboration across BMX race organizers, broadcasters, and developers

## Current status

The first BBS Connector implementation is now available. It provides a read-only FastAPI service over the validated USABMX RaceManager SQL Server relationships, including events, staged motos, rider lineups, lane assignments, and entered results.

## Features

### Implemented

- Read-only SQL Server integration with the USABMX RaceManager `RACE` database
- FastAPI connector with health, current-event, moto-list, and single-moto endpoints
- Normalized rider lineups, lane assignments, results, and moto scoring state
- Environment-based configuration and Docker support
- Unit tests that run without a RaceManager installation
- Theme package scaffolding for Bend BMX operations

### Planned

- Broader RaceManager round, transfer, and main-event coverage
- Live race data export and broadcast-state pipeline
- OBS browser-source overlays for live graphics
- Broadcaster controller UI and hotkey support
- Event theme management and multi-track support
- Timing and ProStart integration

## Architecture overview

The project is organized into the following top-level areas:

- `database/` — validated RaceManager SQL queries and read-only database client
- `connector/` — FastAPI JSON service and normalized broadcast models
- `exporter/` — Data export and bridge logic for overlays
- `overlay/` — Browser-source overlay templates, layouts, and assets for OBS
- `controller/` — Broadcast control interface and hotkey management
- `themes/` — Theme packages, branding, and track-specific visuals
- `docs/` — Project documentation, setup instructions, and architecture references

## Screenshots

> Screenshots coming soon.

## Version 1.2.1 highlights

- Runs as a machine-wide systemd service that starts automatically at boot.
- Adds a desktop and system-tray launcher using `logo.png`, with service and RaceManager status.
- Provides tray shortcuts and authenticated start, stop, and restart controls.
- Retains automatic support for RaceManager databases with or without the optional rider `Nickname` column.

## Installation

Start with the [documentation index](docs/README.md), including Windows/Linux installation, first run, OBS setup, troubleshooting, upgrading, and backup/restore.

Operational logs are available at `/logs`; the JSON API is `/api/logs`, and the current file can be downloaded from `/api/logs/download`.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned phases and development priorities.

## Contributing

Contributions are welcome from BMX organizers, broadcasters, and developers. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening issues or pull requests.

## License

BMX Broadcast Suite is released under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgements

Thank you to the BMX community and live production contributors for inspiring this project.


### Overlay themes

BBS overlays are track-agnostic. Select a theme in the browser-source URL, such as `?theme=default` or `?theme=bend-bmx`. Custom themes live in `themes/<slug>/theme.json`; no Python changes are required.

## Broadcast resilience

BBS stores the latest valid rider lineup in `data/last_known_lineup.json`. If SQL Server becomes temporarily unavailable, the selected moto continues to display from that cache and the Race Director shows an offline warning. A cache is never reused for a different moto or race phase.

Live overlay updates are delivered through `/ws/broadcast`, with slow HTTP refreshes retained as a fallback.

An experimental results overlay is available at `/overlay/results`. Round 1–3 finish fields are implemented from the known RaceManager schema; elimination and main result selection must still be validated at a live event.

## Track configuration

BBS contains no track-specific network address or credentials. Open `/configuration` after installation to set the track name, default theme, connector host/port, and all RaceManager SQL settings. These values are saved in the local `.env` file, which is excluded from Git. The SQL password is never returned by the configuration API.
