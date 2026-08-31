# Sqorz Live Timing

This page is for whoever runs BBS at a track — no programming knowledge needed.
(If you're working on BBS's code, skip to [For BBS developers](#for-bbs-developers)
at the bottom.)

## What this does

If your track uses [Sqorz](https://our.sqorz.com) for timing, BBS can show riders'
live times (and finish positions, once a moto is done) right on your broadcast
overlays — the same lineup graphic your viewers already see, with a time column
added, or a standalone timing graphic (`/overlay/sqorz-timing`) if you don't run
RaceManager at all.

It's entirely optional and off by default. If you don't set it up, or if Sqorz is
briefly unreachable, everything else in BBS keeps working exactly as before —
overlays just show no times, never a wrong one.

**Don't run RaceManager at all, and want BBS's full Race Director — not just
an overlay — to work directly from Sqorz?** See [Sqorz-Only
Mode](sqorz-only-mode.md) instead; everything on this page assumes RaceManager
is present.

**Two important limits, by design:**
- BBS only ever shows a time when it's *confident* it belongs to the right rider.
  A class that "isn't lining up" (see [When the time column is
  blank](#when-the-time-column-is-blank)) is BBS refusing to guess, not a bug.
- Sqorz supplies times and finish positions only. Round names, gate/lane
  assignments, and your official results always come from RaceManager, never
  from Sqorz.

## Setting it up

Everything below is in **`/configuration`**, under the **"Sqorz live timing"**
card — no file editing needed for normal use.

### Step 1 — Turn it on

Check **"Enable Sqorz live timing"**. Nothing below matters until this is checked.

### Step 2 — Pick a mode

Set **Mode** to one of:

| Mode | Use this when... |
|---|---|
| **Internet** | Default choice for most tracks. Needs internet, not your Sqorz computer's own network. |
| **LAN (track scoring computer)** | You're on the same network as the Sqorz scoring computer and want the fastest possible updates. |
| **File (replay a saved payload, no network)** | You have no usable network at all, but captured a file earlier while you did. Mainly a fallback for events with unreliable venue connectivity. |

See [The three modes, in detail](#the-three-modes-in-detail) below for exactly
what each one needs.

### Step 3 — Fill in that mode's fields

Only the fields for the mode you picked matter — the rest can stay blank.

- **Internet**: fill in **Event ID**. See [Finding your event
  ID](#finding-your-event-id-internet-mode) below if you don't know it.
- **LAN**: fill in **LAN host** (and **LAN port** if it's not the default
  `4343`). See [Finding your scoring computer's
  IP](#finding-your-scoring-computers-ip-lan-mode) below.
- **File**: fill in **Replay file path** — the full path to a file saved with
  the capture tool (ask your BBS provider for this if you don't have one).

Leave **Poll interval** and **Timeout** blank unless something below tells you
otherwise — the defaults are already tuned per mode.

### Step 4 — Check it worked

Open **`/sqorz-status`** in a browser tab and leave it open. It shows, in plain
terms, whether Sqorz is reachable, how many classes and riders it found, and how
well things are matching up. See [Checking it worked](#checking-it-worked)
below for what the page means.

## The three modes, in detail

### Internet mode

Reads directly from Sqorz's own website — the same data your event's public
results page shows. Needs a working internet connection (venue WiFi, phone
hotspot, whatever you have), but does **not** need to be on the same network as
the scoring computer.

Updates roughly every 30 seconds (that's how often Sqorz's own site refreshes;
BBS can't get it faster than that here).

**You need:** your event's **Event ID** — see below.

### LAN (track scoring computer) mode

Talks directly to the Sqorz software running on the scoring computer, over your
local WiFi/network. This is the fastest option (can update every couple of
seconds) but only works if your device is on the same network as that computer.

**You need:** the scoring computer's **IP address** — see below.

**A caveat, in plain terms:** Sqorz has never published exactly what this local
connection sends back, so BBS reads it as best it can and is built to fail
safely rather than show something wrong — but it's possible some responses
won't be understood yet. If the time column is blank in LAN mode when you
expect data, check `/sqorz-status` first (it will say so plainly if this is
what's happening) before assuming something else is wrong.

### File (replay) mode

Reads a file saved earlier, instead of talking to anything live. Nothing
updates — it's frozen at whatever moment the file was captured. This exists
purely as a "something is definitely better than nothing" fallback for a venue
with no usable network at all, so a demo or broadcast can still show *real*
data rather than a blank overlay.

**You need:** a saved file (created with a small capture tool, run once ahead
of time while a working connection was available — ask whoever set up BBS for
your track if you need one made).

## Every setting, explained

These are the same fields shown in `/configuration`'s Sqorz card. The `BBS_...`
names are only needed if you're editing the configuration file directly instead
of using the web page.

| Field in `/configuration` | `.env` name | What it's for | Default |
|---|---|---|---|
| Enable Sqorz live timing | `BBS_SQORZ_ENABLED` | Master on/off switch. | Off |
| Mode | `BBS_SQORZ_MODE` | Internet / LAN / File — see above. | Internet |
| Event ID (internet mode) | `BBS_SQORZ_EVENT_ID` | Which Sqorz event to read. Internet mode only. | *(blank)* |
| Org code (optional) | `BBS_SQORZ_ORG_CODE` | Helps look up your event ID (see below). Never required. | *(blank)* |
| LAN host (LAN mode) | `BBS_SQORZ_HOST` | The scoring computer's IP address. LAN mode only. | *(blank)* |
| LAN port | `BBS_SQORZ_PORT` | Only change this if told to by whoever runs your Sqorz. | `4343` |
| Replay file path (file mode) | `BBS_SQORZ_FILE_PATH` | Full path to a saved file. File mode only. | *(blank)* |
| Poll interval (seconds) | `BBS_SQORZ_POLL_SECONDS` | How often to check for updates. Leave blank — Internet and LAN modes each already default to a sensible speed. | *(mode-aware: 10s internet, 2s LAN)* |
| Timeout (seconds) | `BBS_SQORZ_TIMEOUT_SECONDS` | How long to wait for a response before giving up on that one check. Leave as-is unless your connection is unusually slow. | `2` |

Two more exist only for advanced setups (not in `/configuration` — file-editing
only): where class-alias settings are saved
(`BBS_SQORZ_CLASS_ALIAS_FILE`, see [Class aliases](#class-aliases-when-your-class-names-dont-match-sqorzs)
below) and where a LAN response gets saved when it can't be understood
(`BBS_SQORZ_LAN_RAW_RESPONSE_FILE`, see [When the time column is
blank](#when-the-time-column-is-blank)). You will not normally need to touch
either.

## Finding your event ID (internet mode)

The simplest way: ask whoever manages your Sqorz account — they'll have it
handy, or can look it up in Sqorz's own event list.

If you want to find it yourself and know your **org code** (a short code
Sqorz uses for your organization — USA BMX districts and clubs typically
already have one; ask around if you're not sure), open this in a browser,
replacing `<yourorgcode>`:

```
https://our.sqorz.com/json/org/<yourorgcode>
```

It'll show a page of raw text — don't worry about reading all of it. Look for
your event's name and, near it, `"eventId"` followed by a long code in quotes.
That code is your Event ID.

## Finding your scoring computer's IP (LAN mode)

Easiest: ask whoever runs Sqorz at your event — they can usually tell you
directly, or check it on the scoring computer itself.

If you'd rather find it yourself, there's a small tool for exactly this:
`scripts/sqorz_probe.py` (also available as a standalone "probe kit" if you
were sent one directly — double-click "Run Sqorz Probe.bat" inside it). Run it
on the same network as the scoring computer; if you don't already know the IP,
it offers to search the network for you automatically.

## Checking it worked

Open **`/sqorz-status`** and leave it open — it's meant to stay up on a second
screen throughout the event. It shows:

- Whether Sqorz is **reachable** right now, and which mode you're in.
- How **old** the latest data is (a big number here usually means Sqorz stopped
  responding — check your connection).
- How many **classes** and **competitors** it actually found.
- How many riders are matching **confidently** vs. not — this is the number to
  watch if times aren't showing up. See below.
- Any **ambiguous plate numbers** it noticed (two riders sharing a number in
  the same class — normal, and handled safely; see below).
- A button to **set a class alias**, for when class names don't line up (see
  next section).
- In LAN mode, a way to see the **raw response** Sqorz sent, for troubleshooting.

## When the time column is blank

This is almost always one of three things, roughly in order of how often each
one comes up:

**1. Sqorz and RaceManager don't agree on the class name.**
RaceManager might call a class "11-12 Open" while Sqorz calls it something else
entirely, or just uses an internal code. When this happens, BBS can't safely
tell which Sqorz class corresponds to your RaceManager class, so it shows
nothing rather than guessing. **Fix:** see [Class
aliases](#class-aliases-when-your-class-names-dont-match-sqorzs) below — it's a
two-minute fix, no restart needed.

**2. The rider genuinely isn't confidently matched yet.**
BBS only shows a time when it's sure — matching on both plate number and name.
If Sqorz hasn't recorded a time for that rider in that round yet, there's
nothing to show. This is normal early in a round and resolves itself as riders
finish.

**3. Sqorz itself isn't reachable, or (LAN mode only) sent something BBS
couldn't read.**
Check `/sqorz-status` first — it will tell you plainly which of these it is,
including (in LAN mode) if it received *something* from Sqorz but couldn't
recognize the shape of it. That's a real gap worth reporting (see [Getting
help](#getting-help)), not something to work around yourself.

## Class aliases: when your class names don't match Sqorz's

If `/sqorz-status` shows your class using the class-name fallback and it isn't
lining up, you can tell BBS directly which Sqorz class corresponds to your
RaceManager class:

1. Open `/sqorz-status` (or `/sqorz-match-report`).
2. Under **"Set a class alias"**, pick the correct Sqorz class from the
   dropdown.
3. Click **Save alias for current class**.

That's it — it takes effect on the very next check, no restart. It only ever
affects how BBS *looks up* the class; it never changes anything in Sqorz or
RaceManager themselves. Clear it the same way if you ever need to.

## Getting help

If something still isn't working after checking `/sqorz-status`, the most
useful things to send whoever supports your BBS setup are:

- A screenshot of `/sqorz-status`.
- Which mode you're using.
- In LAN mode, the raw response from the "raw" link on that page, if one is
  available.

---

## For BBS developers

The rest of this page is implementation detail for people working on BBS's
code, not something a track operator needs to read.

### Matching, not guessing

Sqorz identifies a competitor by plate/name; RaceManager identifies a rider by
bike number/name. BBS matches them with a confidence tier, and **only "exact"
and "strong" matches ever show a time** — a "weak" match or no match shows
blank. Never a wrong time. See `connector/services/sqorz_matching.py` for the
exact rules, and `/sqorz-status` (or `GET /api/sqorz/status`) for a live
match-report summary.

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
compare is reported on `/sqorz-status` as **Gate agreement**.

### Class aliases (implementation)

`PUT /api/sqorz/aliases` (called by the form on `/sqorz-status` and
`/sqorz-match-report`) maps a RaceManager class name to a Sqorz `className` or
`classCode`. An alias always wins over automatic name matching, is at least as
trusted as a normal class-name match for the "strong" tier, and takes effect
on the very next poll — no restart, because `SqorzClassAliasStore` re-reads
its file (`BBS_SQORZ_CLASS_ALIAS_FILE`, default `data/sqorz_class_aliases.json`)
on every lookup. Never written back to RaceManager or Sqorz.

### The status page and the match report

`/sqorz-status` is the consolidated one-page view: mode, reachability, last
fetch age, parsed class/competitor counts, match-report summary (counts by
confidence tier, unmatched names on each side, ambiguous-plate collisions,
which resolution path was used — `class_name` / `alias` / `plate_only` /
`no_sqorz_data`), gate agreement, and (LAN mode) a link to the last raw
response. `GET /api/sqorz/status` is the same data as JSON.

`/sqorz-match-report` predates the status page and still works (counts,
unmatched names, ambiguous plates, and the alias form, but without mode/
reachability/raw-response) — kept for anyone already using it, not the
primary page going forward.

Both only ever reflect the most recently viewed class (the report is computed
as a side effect of a lineup poll, not a standing cross-event audit) — open
the lineup or Director for the class you care about first if either page says
"(none yet -- open the lineup or Director once)".

### Three backends, one interface

- **Internet API** (`BBS_SQORZ_MODE=internet`): `GET https://our.sqorz.com/json/event/{id}`,
  public, no auth, refreshed by Sqorz roughly every 30 seconds. This is what the fixtures
  and automated tests exercise.
- **LAN API** (`BBS_SQORZ_MODE=lan`): `POST http://{host}:{port}/api?func=...` on the
  scoring computer at the track. Sqorz does not publish the LAN response shapes, so that
  path is written defensively (tolerates unknown/missing fields, never raises) and is
  **unverified** until confirmed on site with `scripts/sqorz_probe.py`.

  Parsing tries a shape guessed from the verified internet API first
  (`parse_lan_phase_rank_detail`); when that matches nothing,
  `parse_lan_by_searching_the_tree` is a resilience fallback that searches the
  whole response for the same known field vocabulary regardless of nesting —
  **this is resilience, not verification**. When neither finds anything usable
  in a non-empty response, the raw response is saved to
  `BBS_SQORZ_LAN_RAW_RESPONSE_FILE` and `SqorzService.last_lan_parse_warning`
  is set (surfaced on `/sqorz-status`) — never a silently blank overlay with no
  explanation. `SqorzService.last_raw_lan_response` also always holds the most
  recent raw response in memory, success or failure, for `/sqorz-status`'s raw
  view.

  `scripts/sqorz_lan_mock.py` is a throwaway local stand-in for this backend (stdlib only,
  not shipped in the installer) that answers `POST /api?func=...` with the real Hoosier
  fixture reshaped into a **guessed** response per function. Run it
  (`python scripts/sqorz_lan_mock.py --port 4343`), point BBS at
  `BBS_SQORZ_MODE=lan` / `BBS_SQORZ_HOST=127.0.0.1` / `BBS_SQORZ_PORT=4343`, and it proves
  BBS forms a correct request, parses *a* plausible response, enforces its own timeout, and
  falls back to last-known-good (flagged stale) when the mock is killed mid-poll —
  `tests/test_sqorz_lan_end_to_end.py` automates exactly this. **It does not verify the real
  LAN contract** — the response shapes are guesses, not any real track's actual data. Only
  `scripts/sqorz_probe.py` against a real scoring computer does that.

  `scripts/sqorz_probe.py` doubles as the emailable kit for an unfamiliar track: it's a
  single self-contained file (stdlib only, no repo imports), prompts interactively for the
  scoring computer's IP or offers to scan the local network for it, writes every raw
  response to a timestamped folder, zips it, and prints what it found in plain language.
  `scripts/build_sqorz_probe_kit.py` bundles it with a `.bat` double-click launcher and a
  non-technical `README.txt` into one `.zip` (see `scripts/sqorz_probe_kit/`).
- **File replay** (`BBS_SQORZ_MODE=file`, `BBS_SQORZ_FILE_PATH=...`): reads a payload saved
  with `scripts/sqorz_capture.py` from disk, through the *exact same* `parse_event_payload()`
  the internet backend uses -- only the fetch differs, so it's a genuine demo of real data
  with no network involved at all. Capture an event while you have internet, carry the file
  with you, and point BBS at it if neither the venue's LAN nor internet is available.

### Standalone Sqorz-only overlay

`/overlay/sqorz-timing` reads only the Sqorz feed — no RaceManager dependency
at all (it never touches `MotoboardService`, `CurrentMotoService`, or the race
slot catalog). Use it when RaceManager isn't reachable from BBS: it shows one
class/phase's plate, rider, time, and (when plausible) finish position, with
Sqorz's own phase wording displayed (e.g. "Moto 1", "Main") — unlike the
lineup overlay's timing column, there is no BBS phase_label to protect here,
since this overlay presents Sqorz's own view of the event, not BBS's
RaceManager-derived race program.

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
genuine per-block timestamp — unverified, confirm on site.

There's no Director UI for switching class/phase yet — bookmark or hand-type
the URL with query parameters in OBS's Browser Source settings.

### Fixture provenance

`tests/fixtures/sqorz/hoosier_day3_event.json` and `tests/fixtures/sqorz/usabmx_org.json`
are trimmed, real payloads from a public USA BMX national event (Hoosier — Day 3,
2026-08-16, `https://our.sqorz.com/json/event/6a8198e2d91badc23cb0c54f` and
`https://our.sqorz.com/json/org/usabmx`), used because a track's own Sqorz feed was not
reachable at build time. The event fixture is trimmed to 6 classes (kept in full field
shape) and includes at least one class where some riders have a recorded time for a phase
and others do not, matching real-world data — Sqorz omits the `time` key entirely for a
phase a rider hasn't run yet or has no recorded time for.
