# Sqorz On-Site Runbook — Smith Rock

Short and printable. Run the probe first, then set config, then check the one-liner.

## 1. Probe first

If Smith Rock already ran the emailed probe kit and sent back a results
`.zip`, skip straight to using its raw responses instead of re-probing on
site -- it's the same data. Otherwise: before touching BBS config, confirm
the LAN scoring API is actually reachable. On your laptop, on the track's
WiFi/LAN:

```powershell
python scripts\sqorz_probe.py --scan 192.168.1.0/24
```

(Use whatever subnet the venue WiFi actually hands out — check with `ipconfig`
if `192.168.1.0/24` isn't it. `--scan` takes 10-20 seconds.)

**A good result** looks like:

```
Found 1 host(s) with port 4343 open: 192.168.1.50
Probing Sqorz LAN API at 192.168.1.50:4343 ...
[OK] getEventSummary
[OK] getPhaseBlockSummaries
...
Reached 5/5 functions.
Raw responses saved to: .../sqorz-probe-20260827T...Z
```

If you already know the scoring computer's IP, skip the scan:
`python scripts\sqorz_probe.py --host 192.168.1.50`

**Send me the saved raw-response folder** as soon as you have it — that's what
lets me finish `connector/services/sqorz_service.py`'s LAN parsing against the
real shape instead of the current best-effort guess.

## 2. Config values

Set these in `/configuration` (Sqorz card) or directly in `.env`, then restart
BBS. All optional, all off unless `BBS_SQORZ_ENABLED=true`. Three modes; try
them in this order on arrival: **LAN first** (best data, needs their scoring
computer reachable), **internet second** (needs working internet, gets
Sqorz's own event if LAN is locked down), **file third** (always works, no
network at all, but only as current as your last capture).

| Setting | LAN mode | Internet mode | File mode |
|---|---|---|---|
| `BBS_SQORZ_ENABLED` | `true` | `true` | `true` |
| `BBS_SQORZ_MODE` | `lan` | `internet` | `file` |
| `BBS_SQORZ_HOST` | IP the probe found | — | — |
| `BBS_SQORZ_PORT` | `4343` unless probe says otherwise | — | — |
| `BBS_SQORZ_EVENT_ID` | — | the live event's id | — |
| `BBS_SQORZ_FILE_PATH` | — | — | absolute path to the captured `.json` |
| `BBS_SQORZ_POLL_SECONDS` | blank (2s default) | blank (10s default) | blank (10s default -- irrelevant, it's a static file) |
| `BBS_SQORZ_TIMEOUT_SECONDS` | `2` | `2` | irrelevant, no network |

## 3. Switching modes

Just flip `BBS_SQORZ_MODE` and save via `/configuration` (restarts the Sqorz
client automatically — no full BBS restart needed for this one setting), or
edit `.env` and restart BBS. No other value needs to change except whichever
of `BBS_SQORZ_HOST`/`BBS_SQORZ_EVENT_ID`/`BBS_SQORZ_FILE_PATH` that mode
actually uses.

## 4. Three most likely failure modes

**A. The probe finds nothing / times out.**
The scoring computer isn't reachable from your laptop's network — wrong
subnet, different WiFi VLAN for spectators vs. scoring, or a firewall. Ask
whoever runs Sqorz which network the scoring computer is actually on; you may
need to be on the same wired/WiFi segment they use. This is a network
problem, not a BBS problem — nothing to configure differently in BBS until
the probe itself succeeds.

**B. `reachable: true` in diagnostics, but every rider shows blank / no
riders in the standalone overlay.**
The LAN response came back but didn't match the shape
`sqorz_service.py`/`sqorz_overlay_service.py` expect (this is the
"UNVERIFIED" part of the LAN backend). Open `/sqorz-status` first -- it
tolerantly searches the whole response for recognisable fields regardless of
nesting, so this may already be resolved on its own; if not, it says so
plainly ("no rider data could be recognised in the response shape") and the
raw response is both saved to disk and viewable right there via "View raw
response" -- no terminal needed. Compare what you see there to
`parse_lan_phase_rank_detail()`'s and `parse_lan_by_searching_the_tree()`'s
candidate field names in `sqorz_service.py` -- send me the raw response
either way.

**C. Reachable, riders present, but they're all "weak" or unmatched in the
lineup column (check `sqorz.match_report.class_match_path` in diagnostics).**
If it says `"plate_only"`, the RaceManager class name and Sqorz's class name
didn't line up textually, so matching fell back to searching every
competitor in the event by plate number alone — and a bare plate match in
that wide a pool is capped at "weak" (never displayed) on purpose, since a
plate number can coincidentally collide across unrelated classes (confirmed
against a real 829-rider field during the dress rehearsal). This is
class-naming friction, not a bug: it means Sqorz's `className` for that class
doesn't match RaceManager's. There's no config fix for this today; it needs
either Sqorz's class names to be edited to match RaceManager's, or a future
class-code mapping table (out of scope for this trip).

**D. A rider you expect to be "exact"/"strong" is blank, and
`match_report.gate_checks` shows a disagree.**
BBS cross-checks Sqorz's own starting gate (`racePosition`) against the gate
RaceManager assigned the rider for the round showing, and demotes the match
(shows nothing) when they disagree — more likely a real mismatch (wrong
round selected, stale gate assignment) than a coincidence. Check you're on
the round you think you're on; if `gate_checks` shows mostly disagreement
across the whole class, the round selection itself is probably off.

## 5. Fallback: demo real timing without their LAN

Two fallbacks, in order of how little they need to go right.

**File mode — works with zero network, always.** Before you leave, capture a
real event while you have internet:

```powershell
python scripts\sqorz_capture.py --event-id 6a8198e2d91badc23cb0c54f --out demo-event.json
```

Then at the venue, regardless of what their network does:

```
BBS_SQORZ_ENABLED=true
BBS_SQORZ_MODE=file
BBS_SQORZ_FILE_PATH=<absolute path to demo-event.json>
```

This replays through the exact same parsing/matching/overlay pipeline as
live data — it just doesn't update, since it's a snapshot from whenever you
captured it.

**Internet mode against a different live event — if you have internet but
not their LAN.** Real, currently-updating data, just not Smith Rock's own:

```
BBS_SQORZ_ENABLED=true
BBS_SQORZ_MODE=internet
BBS_SQORZ_EVENT_ID=<a currently-running public event's Sqorz event id>
```

Find a live event id from `https://our.sqorz.com/json/org/<orgCode>`
(`BBS_SQORZ_ORG_CODE`, e.g. `usabmx`) — look for an event with a recent
`eventDate` in its `events` list, and use its `eventId`.

Either way, point the **standalone Sqorz overlay** (`/overlay/sqorz-timing`)
at it — it needs no RaceManager and will show real riders/times immediately.

## 6. Is it working?

**With a browser**: open `/sqorz-status` and leave it open on a second
monitor -- mode, reachable yes/no, payload age, parsed class/competitor
counts, match report, ambiguous plates, gate agreement, and (LAN mode) the
raw response link, all in one place, auto-refreshing.

**No browser needed**:

```powershell
(Invoke-RestMethod http://localhost:8000/api/diagnostics).sqorz
```

Look for `enabled: True`, `reachable: True`, a small `last_fetch_age_seconds`,
and (once you've selected a class in the Director / hit the standalone
overlay at least once) a populated `match_report`. If `reachable` is `False`,
check `last_error` in the same output — it's the actual exception message.
