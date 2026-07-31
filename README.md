# BMX Broadcast Suite

[![Build Status](https://img.shields.io/badge/build-v1.2.10-informational)](https://github.com/vrpt576/BMX-Broadcast-Suite)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen)](CONTRIBUTING.md)

BMX Broadcast Suite (BBS) connects USABMX RaceManager data to OBS Studio for live race graphics. It provides a read-only FastAPI connector, a race-director controller, browser-source overlays, configurable track themes, diagnostics, resilient last-known data, historical event selection, and background operation with desktop/system-tray controls on Ubuntu and Windows.

## Current status — v1.2.10

BBS can select live or historical RaceManager events, resolve exact qualifier and final stages, and display current-moto, lineup, official Main-results, and break graphics in OBS. Version 1.2.10 adds reliable historic-finals navigation, a server-owned Results Roll, Round 1/Main break graphics, and improved Windows tray-icon sizing while retaining the production-ready Windows installation, startup, and removal flow.

Validated RaceManager behavior in this release:

- `Round_Type_ID 123` contains qualifier or moto progression.
- `Round_Type_ID 1` contains final classification.
- `Moto_Number` is not globally unique; exact stages use `Motogroup_DBID` and round identity.
- `X` finish values are transfer-to-main markers, not numeric placements.
- Small total-points classes expose an **Overall** stage; transfer formats expose a **Main** stage.
- Quarterfinal and semifinal controls are shown only when a future validated mapping proves those stages exist in the selected RaceManager data.

### Available now

- Read-only Microsoft SQL Server integration with the RaceManager `RACE` database
- Automatic compatibility with RaceManager schemas with or without `MB.Race_Riders.Nickname`
- Live and historical event selection with persistent `motoboard_id`
- Round-aware class programs with dynamic qualifier and final-stage controls
- Stable motogroup identities even when qualifier and final branches reuse moto numbers
- Current event, moto, class, exact stage, rider lineup, gate, plate, transfer, and entered-result APIs
- Phase-aware Next/Previous Moto movement within the branch currently on air
- OBS browser sources for current moto, lineup, Main results, and broadcast breaks
- Server-owned Results Roll with pause/resume, manual navigation, and stop-at-last behavior
- WebSocket updates with HTTP polling fallback
- Last-known-good lineup resilience with stale-data indication
- Track configuration UI, diagnostics dashboard, logs, and downloadable log files
- Machine-wide Ubuntu `systemd` service and Windows startup/tray integrations
- Theme packages with expanded per-element color customization

### Known limitations

- Actual quarterfinal and semifinal storage has not yet been validated against a sufficiently large historical RaceManager class, so BBS does not invent those mappings.
- Main versus Overall is inferred from transfer markers and rider-set differences discovered in real RaceManager data.
- Timing gate, ProStart, rider photos, rankings, and automatic graphic sequencing are not yet integrated.
- Themes are edited as JSON files; a visual theme editor is planned.

## Quick start

Use the [documentation index](docs/README.md) for installation and setup. On Ubuntu, begin with [Linux Installation](docs/installation-linux.md) and [Linux Service and Tray](docs/service-linux.md). On Windows, use [Windows Installation](docs/installation-windows.md), the [Windows Setup Wizard](docs/wizard-installer-windows.md), and the Windows background/tray documentation included with the installer. See [RaceManager Round Model](docs/racemanager-round-model.md) for the v1.2.8 architecture.

Common pages:

- Configuration: `http://localhost:8000/configuration`
- Diagnostics: `http://localhost:8000/diagnostics`
- Race Director: `http://localhost:8000/director`
- Controller: `http://localhost:8000/controller`
- Current overlay: `http://localhost:8000/overlay/current`
- Lineup overlay: `http://localhost:8000/overlay/lineup`
- Results overlay: `http://localhost:8000/overlay/results`
- Shared Round/Main break overlay: `http://localhost:8000/overlay/break`

Add `?preview=true` when building or testing an OBS scene. Remove it for live controller-driven operation.

## Round-aware API highlights

- `GET /api/event` — recent live and historical RaceManager events
- `GET /api/current/program` — phases actually available for the selected class/group
- `POST /api/current/phase/select/{phase}` — select an exact available phase
- `GET /api/motos?all_rounds=true` — inspect qualifier and final branches without collapsing duplicate moto numbers
- `GET /api/motos/group/{motogroup_id}` — retrieve one exact motogroup
- `GET /api/lineup/current` — exact-stage gates and riders
- `GET /api/results/current` — numeric placements plus separate transfer status
- `GET /api/results/status` — persistent server-owned Results Roll state
- `POST /api/results/start|pause|resume|previous|next|stop` — timed and manual results playback
- `POST /api/breaks/show/{round_1|main}` — show a validated broadcast-break preset

## Themes

Select a theme with `?theme=default` or set `BBS_DEFAULT_THEME`. Theme packages live in `themes/<slug>/theme.json`. See [Theme Customization](docs/themes.md).

## Project layout

- `database/` — RaceManager SQL queries and read-only database client
- `connector/` — FastAPI application, stage resolvers, platform tray applications, and APIs
- `overlay/` — overlay guidance and future reusable front-end assets
- `controller/` — broadcast controller guidance
- `themes/` — track-specific theme packages
- `packaging/` and `scripts/` — Linux and Windows background, tray, and installation tooling
- `docs/` — setup, operation, troubleshooting, and architecture documentation
- `tests/` — unit, resilience, event-selection, and round-model regression tests

## Roadmap

The near-term race-data priority is validating genuine quarterfinal and semifinal structures from a class large enough to generate them. Other priorities include a visual theme editor, automatic graphic sequencing, timing/ProStart integration, rider media, rankings, and multi-track deployment. See [ROADMAP.md](ROADMAP.md).

## Contributing

Contributions from BMX organizers, broadcasters, designers, and developers are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request. Never commit `.env`, SQL passwords, logs, virtual environments, or local runtime state.

## License

BMX Broadcast Suite is released under the MIT License. See [LICENSE](LICENSE).
