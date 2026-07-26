# Changelog

## 0.6.0

- Added track-agnostic JSON overlay themes selectable with `?theme=<slug>`.
- Added `/api/themes` and `/api/themes/{slug}` theme discovery endpoints.
- Added Lane, Plate Number, and Rider column labels to the lineup lower third.
- Added bundled `default` and `bend-bmx` theme examples.

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

## 0.7.0

- Added the unified Race Director control surface at `/director`.
- Added hotkeys for next/previous moto, round changes, lineup, current-moto bug, and hiding graphics.
- Added persistent on-air graphic state shared by OBS browser sources.
- Current-moto and lineup overlays now show only when selected by the Race Director.
- Added `?preview=true` to force an overlay visible while positioning it in OBS.
- Added `?demo=true` support to the Race Director for at-home lineup testing.
