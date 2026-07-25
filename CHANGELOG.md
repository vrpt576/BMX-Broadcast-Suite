# Changelog

## Unreleased

- Initial repository scaffolding created.

## Unreleased

### Added
- File-backed manual current-moto state that works without RaceManager.
- Keyboard operator page at `/controller`.
- OBS-ready current-moto browser overlay at `/overlay/current`.
- REST controls for reading, setting, advancing, and reversing the current moto.

### Added
- Manual race-phase control for Round 1, Round 2, Round 3, Quarterfinals, Semifinals, and Mains.
- Keyboard shortcuts `[` and `]` to move backward and forward through race phases.
- Race phase displayed on the controller and OBS current-moto overlay.

### Added
- Manual class-name control stored with the current moto and race phase.
- Class name displayed in both the race controller and OBS overlay.
- Backward-compatible loading of existing v0.3 state files.

## 0.5.0

- Added a current rider/gate assignment API.
- Added an OBS-ready rider lineup lower-third overlay.
- Added bundled verified demo data from the 2026-07-23 Thursday Night Racing moto.
- Connected the lineup overlay to the existing keyboard/mouse current-moto controller.
