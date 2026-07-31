# Results Roll

The Race Director can show official RaceManager Main results for the selected
moto or play completed Mains in ascending moto order. The
timer belongs to the BBS server, so reloading or closing the Director page does
not interrupt playback.

## Director controls

- **Show Results for Current Moto** displays the official result associated
  with the pinned event and selected Main. BBS rejects this action when another
  phase is selected.
- **Start Results Roll** starts at either the first available result or the
  selected moto. If the selected moto has no result, BBS starts at the next
  available result, or the last available result when there is no later one.
- **Pause** and **Resume** control the timer without changing the selected race
  position.
- **Previous Result** and **Next Result** work while playback is paused.
- **Stop Results Roll** leaves the current result visible and cancels further
  automatic changes.
- The interval defaults to 10 seconds and accepts values from 2 through 300
  seconds.

Playback stops on the final available result and never wraps. Selecting another
graphic, including **Hide All Graphics**, pauses an active roll so a hidden
timer cannot unexpectedly replace the operator's next graphic.

Selecting **Round 1 Break** or **Main Break** also pauses the roll before the
break becomes active, so timed results cannot replace the break unexpectedly.

## Official-data policy

BBS reads final classifications from `Round_Type_ID 1`, uses qualifier transfer
data to distinguish true Mains from total-points Overall classifications, and
includes only Mains in the Results Roll. It uses only finish values supplied by
RaceManager and never creates an order from gate, lane, or lineup order.

- A fully populated classification is labeled **Official Results**.
- A classification containing at least one numeric finish and at least one
  pending rider is labeled **Incomplete Results**.
- Round 1–3 and Overall classifications are excluded. A Main with no numeric
  official finish is logged and skipped by automatic playback.
- RaceManager-provided rider statuses are shown when present. BBS does not
  invent time or points data.

Completed result catalogs are cached for the selected motoboard, avoiding a
new full-event query at every interval. If the database becomes temporarily
unavailable, a valid result already on air remains visible. Current-result disk
cache data is only reused when its motoboard matches the pinned historic event.

## API

- `GET /api/results/current`
- `GET /api/results/status`
- `POST /api/results/show-current`
- `POST /api/results/start`
- `POST /api/results/pause`
- `POST /api/results/resume`
- `POST /api/results/previous`
- `POST /api/results/next`
- `POST /api/results/stop`

Start request example:

```json
{
  "start_from": "first",
  "interval_seconds": 10
}
```

Use `/overlay/results?preview=true` to position the graphic in OBS. Remove
`preview=true` for normal Director-controlled visibility.
