# Browser Source Reference

## Current Moto

`/overlay/current`

Displays moto, class, and race phase.

## Rider Lineup

`/overlay/lineup`

Displays gate, plate, and rider name. During a temporary SQL outage, a matching last-known-good lineup may be shown and marked stale.

## Results — experimental

`/overlay/results`

Round 1–3 finish fields are implemented. Elimination and main selection still requires live validation.

## Query parameters

- `theme=default` selects a theme for that source
- `demo=true` uses demo data where supported
- `preview=true` forces an overlay visible while building a scene

Without a `theme` parameter, BBS uses `BBS_DEFAULT_THEME`. All overlays receive WebSocket updates from `/ws/broadcast` and retain HTTP polling as fallback.

## Theme colors

Version 1.2.3 supports per-element colors for headers, panels, alternating rows, lane cells, plate numbers, dividers, shadows, and warning banners. See [Theme Customization](themes.md).
