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
applies to the optional RaceManager `Nickname` column. See `docs/README.md` for the
full settings list.

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
