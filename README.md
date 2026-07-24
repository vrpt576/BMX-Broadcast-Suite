# BMX Broadcast Suite

[![Build Status](https://img.shields.io/badge/build-v0.1-informational)](https://github.com/vrpt576/BMX-Broadcast-Suite)
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

## Installation

See [connector/README.md](connector/README.md) for local, Windows, and Docker setup instructions.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned phases and development priorities.

## Contributing

Contributions are welcome from BMX organizers, broadcasters, and developers. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening issues or pull requests.

## License

BMX Broadcast Suite is released under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgements

Thank you to the BMX community and live production contributors for inspiring this project.
