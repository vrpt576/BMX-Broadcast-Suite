# Sqorz Live Timing

BBS can optionally read rider times from [Sqorz](https://our.sqorz.com) live timing and
show them as an extra column in the lineup overlay. This is purely additive: RaceManager
remains the only source for round/phase labels, rider identity, gate assignment, and
official results (see `CLAUDE.md`). Sqorz supplies **times only**, and only for riders
BBS can match with high confidence.

## Disabled by default

Sqorz integration is off unless explicitly configured (`BBS_SQORZ_ENABLED=true`). When
disabled, unconfigured, unreachable, slow, or returning unexpected data, the lineup
endpoint still returns `200` with riders and no times — the same rule BBS already
applies to the optional RaceManager `Nickname` column. See `connector/.env.example`
for the full settings list, or `/configuration` for the in-app editor.

## Configuration

| Setting | Default | Notes |
|---|---|---|
| `BBS_SQORZ_ENABLED` | `false` | Off unless explicitly turned on. |
| `BBS_SQORZ_MODE` | `internet` | `internet` or `lan`. |
| `BBS_SQORZ_EVENT_ID` | *(blank)* | Internet mode only. |
| `BBS_SQORZ_ORG_CODE` | *(blank)* | Internet mode only, optional (event listing). |
| `BBS_SQORZ_HOST` | *(blank)* | LAN mode only — the scoring computer's IP. |
| `BBS_SQORZ_PORT` | `4343` | LAN mode only. |
| `BBS_SQORZ_POLL_SECONDS` | *mode-aware* | Left blank, defaults to **10s in internet mode, 2s in LAN mode** (`Settings.sqorz_effective_poll_seconds`). An explicit value always wins over the mode-aware default. |
| `BBS_SQORZ_TIMEOUT_SECONDS` | `2` | Per-request timeout, either backend. |

The mode-aware poll default exists because the two backends have very different
natural refresh rates: Sqorz's own internet API only updates roughly every 30
seconds, so polling faster than ~10s just re-fetches the same data, while the LAN
API sits on the scoring computer at the track and can be polled much more
aggressively (2s) for snappier updates.

## Three backends, one interface

- **Internet API** (`BBS_SQORZ_MODE=internet`): `GET https://our.sqorz.com/json/event/{id}`,
  public, no auth, refreshed by Sqorz roughly every 30 seconds. This is what the fixtures
  and automated tests exercise.
- **LAN API** (`BBS_SQORZ_MODE=lan`): `POST http://{host}:{port}/api?func=...` on the
  scoring computer at the track. Sqorz does not publish the LAN response shapes, so that
  path is written defensively (tolerates unknown/missing fields, never raises) and is
  **unverified** until confirmed on site with `scripts/sqorz_probe.py`.
- **File replay** (`BBS_SQORZ_MODE=file`, `BBS_SQORZ_FILE_PATH=...`): reads a payload saved
  with `scripts/sqorz_capture.py` from disk, through the *exact same* `parse_event_payload()`
  the internet backend uses -- only the fetch differs, so it's a genuine demo of real data
  with no network involved at all. Capture an event while you have internet, carry the file
  with you, and point BBS at it if neither the venue's LAN nor internet is available.

## Matching, not guessing

Sqorz identifies a competitor by plate/name; RaceManager identifies a rider by
bike number/name. BBS matches them with a confidence tier, and **only "exact" and
"strong" matches ever show a time** — a "weak" match or no match shows blank. Never a
wrong time. See `connector/services/sqorz_matching.py` for the exact rules, and the
`sqorz` section of `GET /api/diagnostics` for a live match-report summary (counts by
confidence, and which names on each side didn't match) — that's the first thing to check
if a class isn't lining up at the track.

A bare plate-number match ("strong") is only trusted when it's scoped to the
rider's actual class (a handful of riders — a collision there is implausible).
When RaceManager's and Sqorz's class names don't line up textually, matching
falls back to searching every competitor in the whole event by plate alone
(`match_report.class_match_path == "plate_only"`) — and confirmed against a
real 829-rider national field during testing, a bare plate number **will**
coincidentally collide across unrelated classes at that scale. A plate-only
match found via that whole-event fallback is therefore capped at "weak"
(recorded, never displayed), never promoted to "strong".

Plate is also not unique *within* one class — confirmed live: Hoosier's
"11-12 Open" has both Dylan Dobelle and Wade Hinderlider on plate 9 (both USA
BMX district plates). A plate appearing more than once in the resolved class
(on either the Sqorz side or the RaceManager side) is excluded from the
"strong" tier entirely — it can still reach "exact" if the last name also
matches, since that disambiguates on its own, otherwise it falls to "weak".
The collision is recorded in `match_report.ambiguous_plates`.

### Finish position and the gate cross-check

Alongside the time, BBS can show Sqorz's own finish position for the round
(e.g. "P2"), marked "LIVE" to distinguish it from RaceManager's own official
result (`ResultRider.finish`, a completely separate pipeline this feature
never touches). It's read from Sqorz's `result` field and gated by the same
confidence rule as the time — only "exact"/"strong" matches show it — plus
one more: `result` carries internal status codes for anything other than a
placed finish (`100400` and `103000` both confirmed live on
withdrawn/no-show riders), and only a plausible 1-8 is ever displayed;
anything else renders exactly like a missing time, never an invented
DNF/DNS/DQ label.

When BBS knows which round is showing, matching also cross-checks Sqorz's
own `racePosition` (starting gate) against the gate RaceManager assigned the
rider. Agreement can *rescue* an ambiguous plate collision straight to
"strong" — confirmed live: Hoosier's "11-12 Open" has Dylan Dobelle and Wade
Hinderlider both on plate 9, but they started from different gates (8 and 7),
so if exactly one of them agrees with the gate BBS already knows, that's as
disambiguating as a matching last name. Disagreement does the opposite: it
demotes an otherwise-displayable match so nothing shows — a real mismatch is
more likely than a coincidence, and this project never prefers a guess over
silence. The agreement rate across all riders where both sides had a gate to
compare is reported on `/sqorz-match-report` as **Gate agreement**.

### Class aliases

RaceManager and Sqorz name classes independently, and often won't line up
textually (RaceManager "11-12 Open" vs. a Sqorz `classCode` like `2204`).
When that happens, every rider in the class silently drops to "weak" (blank
column) via the whole-event plate-only fallback above. Fix it with an
operator-set alias: `PUT /api/sqorz/aliases` (or the **Set a class alias**
form on `/sqorz-match-report`) maps a RaceManager class name to a Sqorz
`className` or `classCode`. An alias always wins over automatic name
matching, is at least as trusted as a normal class-name match for the
"strong" tier, and takes effect on the very next poll — no restart, because
`SqorzClassAliasStore` re-reads its file (`BBS_SQORZ_CLASS_ALIAS_FILE`,
default `data/sqorz_class_aliases.json`) on every lookup. Never written back
to RaceManager or Sqorz.

### The match report

`/sqorz-match-report` is the on-site diagnosis tool: shows the live match
state for whichever class the lineup overlay is currently displaying —
counts by confidence tier, unmatched names on each side, any ambiguous-plate
collisions, which resolution path was used (`class_name` / `alias` /
`plate_only` / `no_sqorz_data`), and the gate agreement rate (see above) —
plus the alias-setting form above. The same
data is available as JSON at `GET /api/sqorz/match-report` if you'd rather
script against it. It only ever reflects the most recently viewed class (the
report is computed as a side effect of a lineup poll, not a standing
cross-event audit) — open the lineup or Director for the class you care about
first if the page says "(none yet -- open the lineup or Director once)".

## Standalone Sqorz-only overlay

`/overlay/sqorz-timing` reads only the Sqorz feed — no RaceManager dependency
at all (it never touches `MotoboardService`, `CurrentMotoService`, or the race
slot catalog). Use it when RaceManager isn't reachable from BBS: it shows one
class/phase's plate, rider, time, and (when plausible) finish position, with
Sqorz's own phase wording displayed
(e.g. "Moto 1", "Main") — unlike the lineup overlay's timing column, there is
no BBS phase_label to protect here, since this overlay presents Sqorz's own
view of the event, not BBS's RaceManager-derived race program.

Select the race with query parameters, e.g.:

```
/overlay/sqorz-timing?class=11-12+Open&phase=M1
```

`class` matches Sqorz's `className` (its own wording, not RaceManager's).
`phase` is a Sqorz `phaseCode`: `M1`, `M2`, `M3`, or `1F` (Main). Omit either
or both and it picks a default: the class with the most recently updated
Sqorz class-level timestamp, using that class's own current ranking phase.
This is a deliberately simple heuristic — **confirmed against the live
internet API that every class in one payload shares one identical timestamp**
(it's a payload-generation time, not per-class), so in internet mode it
resolves to whichever class comes first in Sqorz's own ordering. It should be
more meaningful in LAN mode if `getPhaseBlockSummaries` turns out to carry a
genuine per-block timestamp — unverified, confirm on site. Refine this once
you've seen it against real LAN data.

There's no Director UI for switching class/phase yet — bookmark or hand-type
the URL with query parameters in OBS's Browser Source settings. That's an
explicit scope cut for this trip (see `docs/sqorz-on-site-runbook.md`).

## Fixture provenance

`tests/fixtures/sqorz/hoosier_day3_event.json` and `tests/fixtures/sqorz/usabmx_org.json`
are trimmed, real payloads from a public USA BMX national event (Hoosier — Day 3,
2026-08-16, `https://our.sqorz.com/json/event/6a8198e2d91badc23cb0c54f` and
`https://our.sqorz.com/json/org/usabmx`), used because the Smith Rock BMX track's own
Sqorz feed was not reachable at build time. The event fixture is trimmed to 6 classes
(kept in full field shape) and includes at least one class where some riders have a
recorded time for a phase and others do not, matching real-world data — Sqorz omits the
`time` key entirely for a phase a rider hasn't run yet or has no recorded time for.
