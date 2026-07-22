# BMX Broadcast Suite

[![Build Status](https://img.shields.io/badge/build-pending-lightgrey)](https://github.com/your-org/bmx-broadcast-suite/actions)
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

This repository currently provides the project scaffold and initial documentation for BMX broadcast tooling. Core implementation components are planned and are being developed in stages.

## Features

### Implemented

- Repository structure with clear modules for database, exporter, overlay, controller, and themes
- Theme package scaffolding for Bend BMX operations
- Documentation and example folder placeholders
- Example configuration template for future integration

### Planned

- SQL Server integration with USABMX RaceManager
- Live race and moto data export pipeline
- OBS browser-source overlays for live graphics
- Broadcaster controller UI and hotkey support
- Event theme management and multi-track support
- Timing and ProStart integration

## Architecture overview

The project is organized into the following top-level areas:

- `database/` — RaceManager schema notes, SQL connector scaffolding, and sample data
- `exporter/` — Data export and bridge logic for overlays
- `overlay/` — Browser-source overlay templates, layouts, and assets for OBS
- `controller/` — Broadcast control interface and hotkey management
- `themes/` — Theme packages, branding, and track-specific visuals
- `docs/` — Project documentation, setup instructions, and architecture references

## Screenshots

> Screenshots coming soon.

## Installation

Coming soon.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned phases and development priorities.

## Contributing

Contributions are welcome from BMX organizers, broadcasters, and developers. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening issues or pull requests.

## License

BMX Broadcast Suite is released under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgements

Thank you to the BMX community and live production contributors for inspiring this project.
