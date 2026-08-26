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

## Two backends, one interface

- **Internet API** (`BBS_SQORZ_MODE=internet`): `GET https://our.sqorz.com/json/event/{id}`,
  public, no auth, refreshed by Sqorz roughly every 30 seconds. This is what the fixtures
  and automated tests exercise.
- **LAN API** (`BBS_SQORZ_MODE=lan`): `POST http://{host}:{port}/api?func=...` on the
  scoring computer at the track. Sqorz does not publish the LAN response shapes, so that
  path is written defensively (tolerates unknown/missing fields, never raises) and is
  **unverified** until confirmed on site with `scripts/sqorz_probe.py`.

## Matching, not guessing

Sqorz identifies a competitor by plate/name; RaceManager identifies a rider by
bike number/name. BBS matches them with a confidence tier, and **only "exact" and
"strong" matches ever show a time** — a "weak" match or no match shows blank. Never a
wrong time. See `connector/services/sqorz_matching.py` for the exact rules, and the
`sqorz` section of `GET /api/diagnostics` for a live match-report summary (counts by
confidence, and which names on each side didn't match) — that's the first thing to check
if a class isn't lining up at the track.

## Fixture provenance

`tests/fixtures/sqorz/hoosier_day3_event.json` and `tests/fixtures/sqorz/usabmx_org.json`
are trimmed, real payloads from a public USA BMX national event (Hoosier — Day 3,
2026-08-16, `https://our.sqorz.com/json/event/6a8198e2d91badc23cb0c54f` and
`https://our.sqorz.com/json/org/usabmx`), used because the Smith Rock BMX track's own
Sqorz feed was not reachable at build time. The event fixture is trimmed to 6 classes
(kept in full field shape) and includes at least one class where some riders have a
recorded time for a phase and others do not, matching real-world data — Sqorz omits the
`time` key entirely for a phase a rider hasn't run yet or has no recorded time for.
