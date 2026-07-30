# BMX Broadcast Suite

[![Build Status](https://img.shields.io/badge/build-v1.2.6-informational)](https://github.com/vrpt576/BMX-Broadcast-Suite)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen)](CONTRIBUTING.md)

BMX Broadcast Suite (BBS) connects USABMX RaceManager data to OBS Studio for live race graphics. It provides a read-only FastAPI connector, a race-director controller, browser-source overlays, configurable track themes, diagnostics, resilient last-known data, and background operation with desktop/system-tray controls on Ubuntu and Windows.

## Current status â€” v1.2.6

BBS is usable for live production on Ubuntu/Linux and can also run on Windows 10/11. The verified workflow can maintain a RaceManager connection, select and step through motos, display current-moto and rider-lineup graphics in OBS, and continue showing the last valid matching lineup during a temporary SQL interruption. Results support is available but remains experimental outside the validated RaceManager round fields.

Windows users can install BBS through the new graphical setup EXE. The wizard checks prerequisites, installs the application, and offers boot-time background operation and desktop/tray controls. See [Windows Setup Wizard](docs/wizard-installer-windows.md).

### Available now

- Read-only Microsoft SQL Server integration with the RaceManager `RACE` database
- Automatic compatibility with RaceManager schemas with or without `MB.Race_Riders.Nickname`
- Current event, moto, class, rider lineup, gate, plate, and entered result APIs
- Race Director controls for moto/phase movement and active graphic selection
- OBS browser sources for current moto, lineup, and experimental results
- WebSocket updates with HTTP polling fallback
- Last-known-good lineup resilience with stale-data indication
- Track configuration UI, diagnostics dashboard, logs, and downloadable log files
- Machine-wide Ubuntu `systemd` service, start-at-boot, desktop launcher, and tray status/control
- Windows machine startup task, automatic restart, desktop/Start Menu launcher, and notification-area status/control
- Theme packages with expanded per-element color customization

### Known limitations

- Elimination, semifinal, and main-event result selection still needs broader live-event validation
- Timing gate, ProStart, rider photos, rankings, and automatic graphic sequencing are not yet integrated
- Themes are edited as JSON files; a visual theme editor is planned

## Quick start

Use the [documentation index](docs/README.md) for installation and setup. On Ubuntu, begin with [Linux Installation](docs/installation-linux.md) and [Linux Service and Tray](docs/service-linux.md). On Windows, use [Windows Installation](docs/installation-windows.md) and [Windows Background Operation and Tray](docs/service-windows.md).

Common pages:

- Configuration: `http://localhost:8000/configuration`
- Diagnostics: `http://localhost:8000/diagnostics`
- Controller: `http://localhost:8000/controller`
- Current overlay: `http://localhost:8000/overlay/current`
- Lineup overlay: `http://localhost:8000/overlay/lineup`
- Results overlay: `http://localhost:8000/overlay/results`

Add `?preview=true` when building or testing an OBS scene. Remove it for live controller-driven operation.

## Themes

Select a theme with `?theme=default` or set `BBS_DEFAULT_THEME`. Theme packages live in `themes/<slug>/theme.json`. Version 1.2.3 adds independent colors for primary and secondary accents, header panels, alternate panels, odd/even rows, lane cells, plate numbers, dividers, shadows, and warning banners. See [Theme Customization](docs/themes.md).

## Project layout

- `database/` â€” RaceManager SQL queries and read-only database client
- `connector/` â€” FastAPI application, services, platform tray applications, and APIs
- `overlay/` â€” overlay guidance and future reusable front-end assets
- `controller/` â€” broadcast controller guidance
- `themes/` â€” track-specific theme packages
- `packaging/` and `scripts/` â€” Linux and Windows background, tray, and installation tooling
- `docs/` â€” setup, operation, troubleshooting, and architecture documentation
- `tests/` â€” unit and resilience tests that do not require RaceManager

## Roadmap

The roadmap is organized by release goals rather than the original foundation phases. Near-term priorities are a visual theme editor, automatic graphic sequencing, stronger results validation, and signed installer packaging. Later goals include timing/ProStart data, rider media, rankings, and multi-track deployment. See [ROADMAP.md](ROADMAP.md).

## Contributing

Contributions from BMX organizers, broadcasters, designers, and developers are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request. Never commit `.env`, SQL passwords, logs, virtual environments, or local runtime state.

## License

BMX Broadcast Suite is released under the MIT License. See [LICENSE](LICENSE).
