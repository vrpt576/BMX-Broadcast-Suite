# Browser Source Reference

## Current Moto

`/overlay/current`

Displays moto, class, and race phase.

## Rider Lineup

`/overlay/lineup`

Displays gate, plate, and rider name. During a temporary SQL outage, a matching last-known-good lineup may be shown and marked stale.

## Official Results

`/overlay/results`

Displays official RaceManager Round 1–3 and final/overall placements selected
by the server-owned Results Roll. The graphic supports eight riders, includes
event/class/phase context and progress, and marks incomplete or cached data.
See [Results Roll](results-roll.md) for operation and data-handling rules.

## Broadcast Break

`/overlay/break`

One shared source displays either **ROUND 1 BREAK** or **MAIN BREAK**, selected
from the Race Director. For setup, use
`/overlay/break?preview=true&preset=round_1` or
`/overlay/break?preview=true&preset=main`.

## Query parameters

- `theme=default` selects a theme for that source
- `demo=true` uses demo data where supported
- `preview=true` forces an overlay visible while building a scene

Without a `theme` parameter, BBS uses `BBS_DEFAULT_THEME`. All overlays receive WebSocket updates from `/ws/broadcast` and retain HTTP polling as fallback.

## Theme colors

Version 1.2.3 supports per-element colors for headers, panels, alternating rows, lane cells, plate numbers, dividers, shadows, and warning banners. See [Theme Customization](themes.md).
