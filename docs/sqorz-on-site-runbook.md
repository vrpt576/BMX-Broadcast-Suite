# Sqorz On-Site Runbook — Smith Rock

Short and printable. Run the probe first, then set config, then check the one-liner.

## 1. Probe first

Before touching BBS config, confirm the LAN scoring API is actually reachable.
On your laptop, on the track's WiFi/LAN:

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
BBS. All optional, all off unless `BBS_SQORZ_ENABLED=true`.

| Setting | What to put |
|---|---|
| `BBS_SQORZ_ENABLED` | `true` |
| `BBS_SQORZ_MODE` | `lan` (see switching below) |
| `BBS_SQORZ_HOST` | the IP the probe found, e.g. `192.168.1.50` |
| `BBS_SQORZ_PORT` | `4343` unless the probe found otherwise |
| `BBS_SQORZ_POLL_SECONDS` | leave blank (defaults to 2s in LAN mode) |
| `BBS_SQORZ_TIMEOUT_SECONDS` | `2` (default, probably fine) |

## 3. Switching internet ↔ LAN mode

Just flip `BBS_SQORZ_MODE` and restart BBS (or save via `/configuration`,
which restarts the Sqorz client automatically — no full BBS restart needed
for this one setting). No other value needs to change between modes except
whichever of `BBS_SQORZ_HOST`/`BBS_SQORZ_EVENT_ID` that mode actually uses.

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
"UNVERIFIED" part of the LAN backend). Check
`GET /api/diagnostics` → `sqorz.match_report` — if `unmatched_bbs` lists
every rider and `unmatched_sqorz` is empty or looks wrong, the parser likely
isn't finding rows at all. Re-run the probe, look at the saved JSON files
yourself for the actual field names, and compare to
`parse_lan_phase_rank_detail()`'s candidate keys — send me the files either
way.

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

## 5. Fallback: demo real timing without their LAN

If the venue's LAN is locked down and the probe can't reach anything, switch
to internet mode against a real, currently-live public event so you can still
show working, real timing (not fictional/demo data) — just not Smith Rock's
own:

```
BBS_SQORZ_ENABLED=true
BBS_SQORZ_MODE=internet
BBS_SQORZ_EVENT_ID=<a currently-running public event's Sqorz event id>
```

Find a live event id from `https://our.sqorz.com/json/org/<orgCode>`
(`BBS_SQORZ_ORG_CODE`, e.g. `usabmx`) — look for an event with a recent
`eventDate` in its `events` list, and use its `eventId`. Point the
**standalone Sqorz overlay** (`/overlay/sqorz-timing`) at it — it needs no
RaceManager and will show real riders/times from that event immediately.
This requires actual internet access, unlike the LAN path.

## 6. Is it working? (no browser needed)

```powershell
(Invoke-RestMethod http://localhost:8000/api/diagnostics).sqorz
```

Look for `enabled: True`, `reachable: True`, a small `last_fetch_age_seconds`,
and (once you've selected a class in the Director / hit the standalone
overlay at least once) a populated `match_report`. If `reachable` is `False`,
check `last_error` in the same output — it's the actual exception message.
