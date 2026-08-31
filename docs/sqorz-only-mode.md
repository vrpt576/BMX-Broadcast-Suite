# Sqorz-Only Mode

This page is for whoever runs BBS at a track — no programming knowledge needed.

## What this is

Everything else in this manual assumes your track runs RaceManager and BBS
reads race data from it, with Sqorz (if you use it) only adding a time column
on top. **Sqorz-only mode is different: it's for a track that doesn't run
RaceManager at all.** If you use [Sqorz](https://our.sqorz.com) for scoring
and nothing else, BBS can run its Race Director, on-air graphics, and rider
lineup directly from Sqorz's own data — no RaceManager database, no SQL
Server, nothing to connect to but Sqorz.

This is not the same feature as [Sqorz Live Timing](sqorz-live-timing.md).
That page's feature adds a time column to a RaceManager lineup you already
have. This page's feature replaces RaceManager entirely.

## How BBS decides which mode to run

You never pick a mode yourself — BBS looks at what's actually working and
decides:

1. If RaceManager is reachable, BBS uses it. This is true even if Sqorz is
   *also* configured — a working RaceManager connection is never
   second-guessed.
2. If RaceManager isn't configured or isn't reachable, and Sqorz is enabled
   (see [Sqorz Live Timing](sqorz-live-timing.md) for how to turn it on),
   BBS runs Sqorz-only.
3. If neither is usable, BBS says so plainly and points you at `/setup`.

Both **`/director`** and **`/setup`** show a banner naming the current mode
and why BBS picked it, for example:

> Mode: **Sqorz-only** — RaceManager is not configured or not reachable, and
> Sqorz is configured, so BBS is running Sqorz-only.

**BBS does not re-check this on its own while running.** If RaceManager comes
back online mid-event (or you fix a typo in its connection settings), the
mode banner keeps showing whatever was true when BBS last checked, until you
press the **Re-check** button next to it. That's deliberate: a brief network
blip must never silently swap your entire Director layout out from under you
mid-broadcast. Re-check shows what the mode was and what it became, so you
can see whether anything actually changed.

## Turning it on

You don't need to do anything special if your track genuinely has no
RaceManager — just enable Sqorz in **`/configuration`** (see [Sqorz Live
Timing](sqorz-live-timing.md) for the three modes and how to fill them in)
and leave the RaceManager SQL settings blank. BBS will detect this on its own
and switch to Sqorz-only automatically.

**`/setup`** also has a shortcut: under Status, **"I don't use RaceManager at
this track? Skip straight to Sqorz live timing"** de-emphasizes the SQL Server
driver and RaceManager connection sections (they're genuinely not needed) and
takes you straight to the Sqorz card.

**If your track has both RaceManager and Sqorz configured, and reachable, but
you want BBS to run Sqorz-only anyway** — check **"Force Sqorz-only mode even
when RaceManager is also reachable"** in `/configuration`'s Sqorz section.
Leave this unchecked for every other setup; automatic detection already
does the right thing without it.

## The Race Director in Sqorz-only mode

Most of `/director` looks and works the same. What's different:

| Control | In Sqorz-only mode |
|---|---|
| Previous / Next Moto | Steps through races from Sqorz instead of RaceManager motos — see [Navigating races](#navigating-races-lan-vs-internet-and-file) below for exactly what "next" means in each Sqorz mode. |
| RaceManager event picker | Replaced by a Sqorz event picker (internet mode only — see below). |
| Main-program boundary, jump-to-moto, race-round select, class-name field | Hidden — these are all specific to RaceManager's own scheduling, which doesn't exist here. |
| "Show current results" | Grayed out. Official results always come from RaceManager; there's nothing for this button to show. |
| Results Roll | Hidden entirely, for the same reason. |
| On-air graphic buttons (Lineup, Current Moto, break graphics, Hide All) | Unchanged — these work exactly the same regardless of mode. |
| Remote control token, navigation confirmation | Unchanged. |
| Rider lineup overlay | Shows real riders and times straight from Sqorz, same graphic your viewers already see. |

The round name shown (e.g. "Moto 1", "Semi Final", "Main") is whatever Sqorz
itself calls that race — there's no RaceManager finalization logic to
consult, so BBS shows Sqorz's own name as-is rather than guessing.

## Navigating races: LAN vs. internet and file

This is the one place the three Sqorz modes genuinely behave differently in
Sqorz-only mode, because they don't all give BBS the same information to work
with.

**LAN mode** (the track's own scoring computer) is the only one of the three
that tells BBS a real running order for the whole event, across every class.
Previous/Next Moto steps through that order directly — there's no separate
class picker to use first.

**Internet and file mode** have no such running order — Sqorz's public data
doesn't expose one, and BBS won't invent a guess and present it as fact.
Instead, you get:

- A **class picker**, to choose which class you're working with.
- **Previous/Next Moto**, which then steps forward and backward through that
  one class's races only (never jumping into a different class).
- A **"Jump to Most Recent Activity"** button, which skips straight to the
  furthest-along race in the selected class that actually has a recorded
  time — useful for catching up to where scoring already is instead of
  clicking through every earlier race by hand.

## The Sqorz event picker (internet mode only)

If you've set an **Org code** in `/configuration`'s Sqorz section, `/director`
shows a dropdown of that organization's events (pulled from Sqorz, most
recent first) so you can switch which one BBS is following without leaving
the Director page. This only appears in internet mode — LAN mode has no
equivalent event list, and file mode always replays one fixed saved file.

## Known limits

- **No official results.** Results Roll and "Show current results" need
  RaceManager's own results pipeline, which doesn't run in this mode at all.
- **LAN mode's race ordering is unverified.** Sqorz has never published the
  exact shape of the data BBS uses to build LAN mode's running order, so BBS
  parses it defensively and falls back to a reasonable guess when it doesn't
  recognise the response — see [Sqorz Live
  Timing](sqorz-live-timing.md#the-three-modes-in-detail) for the same
  caveat as it applies to LAN mode generally.
- **No Main-program boundary or multi-event RaceManager scheduling.** Those
  are RaceManager concepts with no Sqorz equivalent.

## Troubleshooting

**Mode is stuck on "Unavailable."** Neither RaceManager nor Sqorz is usable
yet. Open `/setup` to fix RaceManager, or `/configuration` to enable Sqorz,
then press **Re-check**.

**I fixed RaceManager, but BBS is still showing Sqorz-only.** Press
**Re-check** on `/director` or `/setup` — BBS only re-evaluates when asked,
on purpose (see [How BBS decides which mode to
run](#how-bbs-decides-which-mode-to-run) above).

**The class picker is empty.** BBS only lists classes it has actually
received rider data for from Sqorz this poll. If nothing has been scored yet,
or Sqorz is unreachable, the list will be empty until it has something to
show.

**"Jump to Most Recent Activity" did nothing.** Select a class first — it
jumps within whichever class is currently selected, not across the whole
event (see [Navigating races](#navigating-races-lan-vs-internet-and-file)
above for why there's no cross-class equivalent in internet/file mode).
