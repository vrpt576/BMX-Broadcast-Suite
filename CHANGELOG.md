# Changelog

## 1.2.16 - 2026-08-23

- Fixed race phase labels showing "Round 1"/"Round 2"/"Round 3" for
  qualifying motos, including a mislabeled "Round 3" for the third moto of a
  3-moto Total Points class. RaceManager's own data model has no "Round N"
  concept (`Ref.Rounds` names qualifying "Moto" regardless of how many motos
  a class runs, and Main/Semi/Qtr/LCQ/8th/16th/32nd are separate rounds) —
  labels are now read from `Ref.Rounds`/`MB.Rider_Advance` via a new
  `RoundLabelResolver` instead of being inferred from which `Lane_N`/
  `Finish_N` columns happen to be populated. Qualifying motos now display as
  "Moto 1"/"Moto 2"/"Moto 3".

## 1.2.15 - 2026-08-23

- Fixed a bug where a custom overlay theme (e.g. a track's saved theme) only
  rendered on the BBS host itself (`127.0.0.1`) and silently fell back to the
  bundled default colors for every other client on the LAN, including OBS on
  another computer. `GET /api/themes` and `GET /api/themes/{slug}` were
  incorrectly gated behind the remote-admin token, same as theme *edits* —
  they're now public read-only broadcast data, consistent with
  lineup/current/results. Only theme save/reset remain admin-gated.
- Added an "Open Theme Manager" link to the Windows tray flyout menu.
- Made the tray's Start/Stop/Restart BBS controls confirm the Windows service
  actually reached the expected state instead of trusting `ShellExecuteW`'s
  return code, which reports a false success if the UAC prompt is cancelled
  or `sc.exe` fails once elevated. Restart now waits for a confirmed stop
  before issuing start (instead of a fixed 1-second delay), and the menu
  disables these actions while one is already running.

## 1.2.14 - 2026-08-19

- Pooled RaceManager SQL connections instead of opening and closing a new
  connection for every query, reducing per-request latency for Director
  polling and the overlay/lineup/results endpoints.
- Replaced the deprecated FastAPI `on_event` startup/shutdown hooks with a
  `lifespan` context manager; no behavior change.
- Added CI (ruff and pytest on every push and pull request against main).
- Documented the `/themes` Theme Manager workflow and removed stale
  "visual theme editor is planned" language now that it has shipped.

## 1.2.13 - 2026-08-18

- Added optional RaceManager racing age and home-track subtitles to lineup and
  results graphics, omitting absent values cleanly.
- Added protected in-app theme management with supported-setting validation,
  active-theme selection, default restoration, and preservation of unrecognized
  legacy custom-theme properties.

## 1.2.12 - 2026-08-04

- Fixed the Race Director's Jump to moto field so background status polling
  cannot overwrite focused or pending operator input, spinner changes, failed
  submissions, or a successful race-position apply.

## 1.2.11 - 2026-08-01

- Separated physical program segments, competition stages, scoring methods,
  and finalization methods; Total Points classifications no longer appear as
  an operator-facing Overall round.
- Rebuilt navigation around physical race slots so combined motos appear once,
  Next and Previous are symmetric, and Transfer Main events and final Total
  Points motos remain interleaved in scheduled Main-program order.
- Fixed direct Go to Moto selection, actionable unavailable-moto feedback,
  stale-response protection, and class-aware transitions between rounds.
- Added per-event race-position confirmation preferences with an explicit
  reset control.
- Preserved and expanded Results Roll combined-moto ordering, official finish
  order, playback controls, and break-graphic coordination.
- Added safe race-program structure export for anonymized schema diagnostics
  and regression fixtures.
- Added a persistent, resettable Main-program start per Motoboard for events
  whose RaceManager records do not expose an explicit running-order boundary;
  Transfer finals are retained as low-confidence suggestions only.
- Hardened network administration with localhost binding by default,
  configured CORS origins, explicit remote administration, mutation tokens,
  and credential redaction.
- Replaced the Defender-flagged IExpress/hidden-script installer architecture
  with a native WiX Toolset v4 MSI and pinned WinSW Windows service.
- Added offline hash-locked Windows dependencies, build-input validation,
  Authenticode signing support, artifact manifest, CycloneDX SBOM, SHA-256,
  and an exact-artifact Microsoft Defender release gate.

## 1.2.10 - 2026-07-31

- Fixed historic-event Director navigation so Main stepping renders the server
  response immediately, resists stale polling updates, skips incompatible
  classifications, and keeps the selected event pinned.
- Enlarged the visible Windows notification-area artwork with a tightly cropped
  source asset and validated multi-resolution icon generation.
- Completed the official Main-results graphic and server-owned Results Roll,
  including historic-event pinning, a configurable ten-second interval,
  pause/resume, manual previous/next, and stop-at-last behavior.
- Limited automatic results playback to completed RaceManager final Main-branch
  classifications while excluding qualifier, quarterfinal, and semifinal
  entries.
- Added theme-aware Round 1 Break and Main Break graphics that preserve race
  position and pause an active Results Roll before taking air.

## 1.2.9 - 2026-07-31

- Improved historic-event loading in the Race Director by allowing slower
  RaceManager event-list responses and repaired corrupted Director UI
  characters.
- Fixed Main and Overall moto progression so stepping stays within the selected
  finals phase, skips incompatible classifications, and remains at the end when
  no later compatible final exists.
- Added Windows Apps & Features registration with interactive and quiet uninstall commands.
- Added a scoped Windows uninstaller that removes only BBS-owned tasks, processes, services, shortcuts, files, and registry entries.
- Preserved configuration, credentials, logs, themes, and local race state under `%ProgramData%` by default.
- Added automatic restoration of preserved operator data during reinstall.
- Added a controlled Windows uninstall/reinstall validation script and packaging regression checks.
- Started the Windows background task during setup and waited for API readiness before opening Configuration.
- Fixed Windows startup-task registration to use the installed private `python.exe`
  with an explicit module, working directory, task verification, and actionable
  startup diagnostics.
- Moved installed runtime configuration, logs, state, caches, and custom themes
  to `%ProgramData%\BMX Broadcast Suite\UserData`; Program Files is now treated
  as read-only after installation.
- Made the Windows EXE payload deterministic and self-contained from tracked
  Git content, including validation that every wizard-referenced script is
  packaged.
- Kept the IExpress bootstrap hidden through `wscript.exe` so setup and normal
  operation do not leave console windows open.

## 1.2.8

- Added round-aware RaceManager stage resolution using `Motogroup_DBID`, class, round type, round, and lane/finish index instead of treating `Moto_Number` as globally unique.
- Added dynamic phase programs so the Director exposes only phases actually present for the selected class and qualifier group.
- Mapped `Round_Type_ID 123` to qualifier progression and `Round_Type_ID 1` to exact final classification.
- Added evidence-based Main versus Overall classification for transfer and total-points formats.
- Normalized RaceManager `X` finish values as transfer markers rather than numeric placements.
- Added phase-aware Next/Previous Moto behavior that stays in the qualifier or final branch currently on air.
- Added stable motogroup lookup APIs and exact stage metadata to current, lineup, and results payloads.
- Fixed pyodbc 5.2 Windows compatibility by applying supported connection-level query timeout behavior instead of assigning `Cursor.timeout`.
- Added regression tests for duplicate moto numbers, split qualifier groups, transfer markers, total-points Overall stages, unavailable semifinals, phase-aware moto movement, and Windows timeout compatibility.

## 1.2.7

- Added historical RaceManager event listing and persistent motoboard selection in the Race Director.
- Added event-aware lineup and results retrieval for previously completed races.
- Reduced default SQL connection and query timeouts for faster offline recovery.

## 1.2.6

- Bundled the Microsoft ODBC Driver 18 x64 MSI for offline Windows installation.
- Added SHA-256 and Microsoft Authenticode verification for the bundled ODBC installer.
- Fixed the IExpress launcher path bug that caused the setup wizard to exit immediately.
- Fixed administrator relaunch handling so temporary installer files remain available during elevation.
- Fixed the Windows Scheduled Task to use `python.exe` instead of `pythonw.exe`.
- Updated application, tray, documentation, installer, and test version references to 1.2.6.

## 1.2.5

- Added a graphical Windows setup wizard with prerequisite checks, installation-folder selection, and optional machine-startup configuration.
- Added a Windows EXE installer build pipeline using the built-in IExpress packaging tool.
- Added guided installation documentation and SmartScreen guidance for the currently unsigned installer.
- Preserved the PowerShell installer for development and advanced deployments.
- Added independent control over starting the tray application during background-service installation.

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
