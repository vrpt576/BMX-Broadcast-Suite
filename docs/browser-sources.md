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

Without a `theme` parameter, BBS uses `BBS_DEFAULT_THEME`. All overlays receive WebSocket updates from `/ws/broadcast` and retain HTTP polling as fallback.
