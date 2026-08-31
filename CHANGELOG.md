# Changelog

**Versioning note:** starting with 1.3.0, the 1.3.x line carries both new
features and fixes -- unlike 1.2.x, which was fixes and hardening only
after 1.2.0 shipped its own features. This project isn't following
strict semver's "features only bump the minor version" convention;
minor-version bumps here track *releases*, not a promise about what
kind of change is inside one. Check each release's own notes for what
actually changed, not the version number alone.

## Unreleased

## 1.3.2 - 2026-08-31

**Verification status, plainly:** internet and file mode are tested against
real captured Sqorz data throughout (`tests/fixtures/sqorz/`), including a
real bug caught and fixed this way -- a class running a Semi Final before
its Main sorted backwards until the ordering table was corrected against
what the real payload actually contained. **LAN mode's race ordering
(`getPhaseSummaries`) remains unverified** -- no real payload has ever been
captured for it, the same status LAN mode's rider-time parsing has carried
since 1.3.0. It is built the same defensive way (a guessed shape with a
tree-search fallback, degrading to "no verified ordering" rather than
raising) and flagged as such in code and docs; treat it as experimental
until a real LAN payload is captured on site.

- Added **Sqorz-only mode**: for a track running no RaceManager at all, BBS
  can now run its full Race Director, on-air graphics, and rider lineup
  directly from Sqorz -- not just a time column added to a RaceManager
  lineup (that feature, Sqorz Live Timing, is unchanged). See
  [docs/sqorz-only-mode.md](docs/sqorz-only-mode.md).
  - **Automatic mode detection**, never an operator prompt: a reachable
    RaceManager always wins; otherwise, an enabled Sqorz falls through to
    Sqorz-only; otherwise BBS says plainly that neither is usable yet. An
    explicit override (`BBS_FORCE_SQORZ_ONLY_MODE`, a checkbox in
    `/configuration`) is available for a track with both configured that
    wants Sqorz-only anyway.
  - Mode is **cached, not re-evaluated per request** -- a transient
    RaceManager network blip mid-event can't silently swap the operator's
    navigation model out from under them. Both `/director` and `/setup`
    show the current mode and reason, with an explicit, operator-triggered
    **Re-check** button (never a timer) that reports the decision before
    and after.
  - **Navigation** is genuinely different by Sqorz mode, not one model with
    a flag threaded through it: LAN mode gets a full-event catalog ordered
    by Sqorz's own documented running-order source; internet and file mode
    have no such source, so they get a class picker, Previous/Next scoped
    to the selected class only, and a "jump to most recent activity" action
    instead of inventing a cross-class order that can't be defended.
  - An **internet-mode event picker** (Change 3) lists events from
    `/json/org/{orgCode}` when an org code is configured; hidden in LAN and
    file mode, which have no equivalent list.
  - **Full Director control mapping**: Previous/Next Moto repurposed to
    Sqorz navigation; the RaceManager event picker, main-program boundary,
    round buttons, jump-to-moto, and class-name field hidden (not
    applicable); "Show current results" disabled with a reason; the entire
    Results Roll cluster hidden (results always come from RaceManager, and
    there is no Sqorz-only results feature); on-air graphic buttons, break
    buttons, remote control token, and the navigation-confirm modal
    unchanged, since none of them depend on RaceManager.
  - Sqorz's own phase name (e.g. "Moto 1", "Semi Final", "Main") is shown
    as the round label directly in this mode -- there is no RaceManager
    finalization method to defer to, unlike mixed mode, where Sqorz still
    never sets a round label.
  - **Provably isolated from RaceManager**: a dedicated end-to-end test
    exercises a full operator session (check mode, list classes, select
    one, jump to recent activity, step through races, read the lineup)
    against the real production dependency graph wired to RaceManager
    services that raise if ever called, proving the whole path never
    touches RaceManagerDatabase. The one deliberate exception, the lineup
    endpoint (OBS points at a single fixed overlay URL regardless of mode),
    is a single named, reviewed dispatcher function.
  - **An existing RaceManager-only install sees no behavior change** --
    pinned by a dedicated test loading configuration shaped exactly like a
    real pre-1.3.2 install (mentioning none of the new settings at all).

## 1.3.1 - 2026-08-31

*Shipped as part of the 1.3.2 release above, not tagged separately -- 1.3.2 was
gate-tested and published before 1.3.1 reached its own release, so both sets
of changes went out together under the v1.3.2 tag.*

- Added an in-app manual (`/manual`, linked from the tray) so BBS's own
  documentation lives inside the product -- anyone who reaches BBS
  through a link, not a GitHub clone, never sees `docs/` otherwise.
  Browsable with a sidebar index across eight sections (Quick start,
  Installation, Setting up RaceManager access, Sqorz live timing, User
  guide, System administration, Troubleshooting/FAQ, Best practices for
  race day) and a cheap client-side search. Mirrors this project's
  existing docs/*.md content -- structure and an index, not a rewrite --
  with one new page filling a real gap (race-day best practices) that
  didn't already exist as a doc. Rendered by a small, purpose-built
  Markdown-to-HTML converter scoped to what these docs actually use
  (headers, tables, fenced code, lists, links), rather than adding a new
  dependency to the offline, hash-locked wheel pipeline for something
  this project's own docs corpus doesn't need. Fully offline like the
  overlays -- no CDN, no external fonts. `docs/` is now copied into the
  MSI payload (it wasn't before) so this content actually ships.
- Added SQL Server instance/port discovery via the SQL Server Browser
  service (UDP 1434, the same protocol SSMS and RaceManager's own
  installer use) -- a "Find it for me" button beside the Setup wizard's
  host fields fills in the instance name and port automatically.
  Deliberately not a port scan: a single UDP query to the one port that
  exists specifically to answer this question, which doesn't get slower
  the more instances or ports there might be and doesn't look like
  reconnaissance to a firewall or IDS watching someone else's track
  network. Verified live against this project's own reference
  deployment (correctly discovered instance `USABMX` on its real,
  non-default port). Falls back to checking the one universally
  standard SQL Server port (1433, still not a scan) when the Browser
  service doesn't answer -- it's frequently disabled -- and says so
  plainly either way rather than silently guessing.

## 1.3.0 - 2026-08-30

**Verification status, plainly:** the internet-mode Sqorz backend has been
tested extensively against real, live Sqorz data (a real 2026-08-16 USA BMX
national event) and is considered solid. **The LAN Sqorz backend has never
connected to a real Sqorz installation.** Its request handling, timeout
behavior, and fallback-when-disconnected behavior are verified against a
local mock server with *guessed* response shapes (see "resilience, not
verification" below) -- not against any real track's actual scoring
computer; treat it as experimental until it has. This status is unchanged
by the rest of this section: this release has been installed and
gate-tested on a real machine, including the Setup wizard's full command
surface (the forced-driver-missing flow, a throwaway-login
create/verify/drop cycle, the `login_name` injection rejection, and
loopback-only enforcement against a non-loopback request) -- see
"Release process" in `CLAUDE.md`. The LAN Sqorz backend was not part of
that gate and remains experimental.

**Install path tested:** 1.3.0 was validated as a clean install -- no
prior BBS version present on the machine. **The in-place upgrade path
from 1.2.17 was not exercised for this release.** If you're upgrading an
existing 1.2.17 install rather than installing fresh, that specific path
has not been verified for 1.3.0; a clean install (remove the old
version, then install 1.3.0) is the tested path and is also what most
new tracks setting up BBS for the first time will do anyway.

- Added optional Sqorz live-timing integration: the lineup overlay can show
  each rider's time for the currently selected round, read from Sqorz's
  public internet API, its LAN scoring API, or a saved file replay. Off by
  default (`BBS_SQORZ_ENABLED=false`); when disabled, unconfigured,
  unreachable, or a rider can't be confidently matched, the lineup endpoint
  is unchanged -- no time is shown, same as the existing optional-column
  pattern. RaceManager remains the only source for round labels, rider
  identity, gate assignment, and official results; Sqorz supplies times and
  finish positions only, and only for an "exact" or "strong" confidence
  plate/name match -- see `docs/sqorz-live-timing.md`.
- Added a standalone Sqorz-only overlay (`/overlay/sqorz-timing`) with no
  RaceManager dependency at all, for tracks where BBS can read Sqorz but not
  RaceManager. Shows one class/phase's plate, rider, time, and finish
  position; selectable via `?class=`/`?phase=` query parameters, defaulting
  to a simple "most recently updated class" heuristic. Unlike the lineup
  overlay's timing column, Sqorz's own phase wording is deliberately
  displayed here, since this overlay presents Sqorz's own view of the event,
  not BBS's race program.
- Hardened Sqorz matching in three ways, all confirmed against real live
  data: (1) a bare plate-number match is only trusted as "strong" (displayed)
  when scoped to the rider's actual class -- when class names don't line up
  and matching falls back to searching the whole event by plate alone, that
  match is capped at "weak" (never displayed), confirmed against a real
  829-rider national field where a bare plate number can otherwise
  coincidentally collide across unrelated classes; (2) a plate that collides
  *within* one class (confirmed live: two riders on plate 9 in the same
  class) is excluded from "strong" on either side of the match, and can only
  reach "exact" if the last name also disambiguates; (3) a demo/sample
  lineup is now structurally incapable of ever receiving a real Sqorz time,
  enforced as a boundary check before any matching runs at all, not left to
  the confidence tiers to reject.
- Added a gate cross-check: Sqorz's own starting-gate value is compared
  against the gate RaceManager assigned the rider for the round showing.
  Agreement can rescue an otherwise-unresolved ambiguous plate collision
  straight to "strong" (confirmed against the real plate-9 collision above);
  disagreement demotes an otherwise-displayable match so nothing shows,
  since a real mismatch is more likely than a coincidence. The agreement
  rate is visible on the new status page (see below).
- Sqorz's own phase/round wording is now guaranteed to never appear in the
  lineup overlay's round header (always BBS's own RaceManager-derived text)
  -- it's shown only in the time column's own caption, e.g. "Time (M1)".
- Added operator-editable class aliases, for when RaceManager's and Sqorz's
  class names don't textually match: point a RaceManager class at the
  correct Sqorz class from a web page, no file editing or restart needed.
- Added a third Sqorz mode, file replay (`BBS_SQORZ_MODE=file`): replays a
  payload captured ahead of time (`scripts/sqorz_capture.py`) through the
  identical parsing/matching/overlay pipeline as the live internet backend --
  real data with no network at all, for a venue with no usable connectivity.
- Added a consolidated Sqorz status page (`/sqorz-status`), meant to be left
  open throughout an event: mode, reachability, payload age, parsed
  class/competitor counts, match confidence breakdown, ambiguous plates,
  gate-agreement rate, class-alias editing, and (LAN mode) a link to the last
  raw response received, all on one auto-refreshing page.
- Hardened the LAN backend's parsing: when Sqorz's LAN response doesn't match
  the shape guessed from the verified internet API, a fallback searches the
  whole response for the same known field names regardless of nesting. When
  neither approach finds anything usable in a non-empty response, the raw
  response is saved to disk and a clear message says so on the status page --
  never a silently blank overlay with no explanation. This is resilience
  against an unknown shape, not verification that the shape is understood --
  see "Verification status" above.
- Added `scripts/sqorz_probe.py` / a bundled probe kit: a single
  self-contained tool (no BBS installation required) that a non-technical
  person at an unfamiliar track's scoring table can run to test LAN
  reachability and capture real response shapes to send back, closing the
  loop on the LAN backend's unverified status above.
- Fixed a startup crash: a blank `BBS_SQORZ_POLL_SECONDS` value (exactly what
  the shipped `.env.example` ships, and what the configuration UI writes when
  the field is cleared) crashed BBS at import time, before the web server
  even started. Extended the same fix to every other Sqorz setting, and to
  `BBS_SQL_PORT` specifically (required blank for a named SQL-instance
  connection -- see `CLAUDE.md`'s SQL instance/port note) plus the remaining
  pre-existing numeric/boolean settings added around this release -- none of
  them can crash startup on a blank or mistyped value now; a mistyped value
  degrades just that setting's feature and prints a clear warning, instead of
  taking down RaceManager, the Director, and the existing overlays.
- Fixed the lineup overlay's and standalone overlay's time columns clipping
  at 1920x1080: the column was too narrow for a bold six-character time,
  overflowing past the panel's edge. Caught during a dress rehearsal against
  live Sqorz data before deploying on site. Also: a blank time now renders as
  an en dash instead of empty space, and rider metadata (age/home track)
  clamps to one line with an ellipsis instead of overflowing.
- Added a guided Setup wizard (`/setup`, linked from the tray and
  `/diagnostics`) so a non-technical track operator can get RaceManager
  connected without installing anything by hand or writing SQL themselves.
  Runs *inside* already-installed BBS as an ordinary page, not a bundled
  installer chain -- see "Windows packaging / antivirus lessons" in
  `CLAUDE.md` for why that distinction matters. Loopback-only always,
  regardless of any remote-admin token, since it creates database accounts
  and installs software -- see `docs/setup-wizard.md`.
  - Detects whether a usable SQL Server ODBC driver is installed and, if
    not, offers to install Microsoft ODBC Driver 18 either from a bundled
    copy (works with no internet at the track) or a fresh download.
    Redistribution of the bundled copy is confirmed by the driver's own
    EULA and REDIST list ("The entire package may be redistributed."),
    verified 2026-08-29 -- see `packaging/windows/dependencies/ODBC-Driver-LICENSE.rtf`.
  - Guides creating the read-only `bbs_connector` SQL login. Written for
    a track operator, not a DBA: a T-SQL script is not a reasonable thing
    to hand someone whose job is running a BMX track. If BBS is already
    connected and reading RaceManager, the page says so plainly and
    collapses to "nothing to do here" instead of walking through account
    creation regardless. Otherwise there are four ways to finish, tried
    in this order -- least typing first, and each one only asks for
    something the previous one couldn't get for free:
    1. **Set it up automatically** -- one click, no fields. Tries BBS's
       own Windows service identity against `localhost`; on a single-PC
       track (one computer running RaceManager and everything else, the
       most common small-track setup) the local SQL Server frequently
       already trusts that identity as an administrator, so this alone
       finishes the job with nothing typed. If it can't connect, or
       connects but can't manage logins, the page says so calmly and
       falls through to the next option -- that's a normal, expected
       outcome for many setups (most trackside broadcast PCs are a
       separate computer from RaceManager), not an error.
    2. **Enter administrator credentials** -- shown once option 1 doesn't
       pan out. The operator types a SQL Server *administrator* account's
       username and password (SQL authentication only; there's no way
       for pyodbc to authenticate as an arbitrary Windows account from
       typed credentials). BBS connects as that account over the network
       and does the rest itself: checks it can actually manage logins (a
       plain-language refusal if not, never a raw SQL Server permission
       error), creates the login or resets its password if one already
       exists, verifies it by reading a real row from RaceManager, saves
       it, and forgets the admin credentials -- never persisted, logged,
       or echoed back. Works whether BBS and RaceManager's SQL Server
       share a computer or not. If even this connection fails, a
       lightweight diagnostic reconnect using BBS's own Windows identity
       checks whether the SQL Server accepts SQL logins at all, and says
       so plainly if not -- retyping different credentials there would
       never work no matter what.
    3. **Already have a working login** -- for when the login already
       exists and works and nothing needs to change; verifies it by
       reading a real row and saves it, with no SQL run at all.
    4. **Hand it to someone else** -- generates a reviewable,
       `IF NOT EXISTS`-guarded script for a track's own DBA or IT
       support, with the required permission stated up front (a SQL
       Server administrator; signing in as `bbs_connector` itself will
       not work) and plain-language troubleshooting for the errors that
       actually happen running it as the wrong account or against an
       already-existing login.
    A pasted password gets identical handling to a generated one either
    way: never logged, never echoed back, never shown in Diagnostics. A
    ready-made cleanup script (`DROP USER`/`DROP LOGIN`) is shown on the
    same page so a track can remove the account without contacting
    anyone.
- Added a one-page installation/configuration status view (`/api/setup/status`,
  shown at the top of `/setup`): ODBC driver, database connection,
  RaceManager readability, and Sqorz configuration, each with a link to fix
  it when something's wrong.

## 1.2.17 - 2026-08-24

- Fixed a third qualifying moto being announced as "Main". v1.2.16 mapped the
  third round to "Main" for every class, so classes that run three qualifying
  motos and a separate final, as nine did at the 2026-08-01 Gold Cup, were
  labelled "Main" over a qualifier and then "Main" again over their real final
  — the same class shown as Main at two different motos. The third round is
  now displayed as "Moto 3" for a class that still has a final to race, and as
  "Main" only for a class that ends on that moto (accumulated points, no
  separately raced final).
- Fixed `/api/current/program` still returning "Round 3" for exactly those
  stages while navigation reported "Main". Both paths now agree, and the Race
  round menu no longer offers two entries both reading "Main"; the Director's
  static fallback option no longer reads "Round 3" either.
- After upgrading from v1.2.15 or earlier, an overlay could show "ROUND 3"
  until the operator's next navigation: the label persisted in `current.json`
  under `%ProgramData%` survives installs, and the overlay trusts a saved
  label ahead of its own map. This stale label is now detected on load and
  dropped so the next resolve re-derives it correctly.
- Hardening only, with no operator-visible symptom on the production path:
  the lineup service's legacy fallback for motoboard adapters without
  `resolve_state` now maps `round_3` to "Moto 3" through an explicit label
  map instead of title-casing the phase value into "Round 3".
- Added a full-program regression walkthrough over the historic 2026-08-01 Gold
  Cup / State Race motoboard (62 classes, 65 motos, 600 rider rows, exported
  without any rider personal data). It steps every moto of every round forwards
  and backwards, jumps to each directly, and asserts the wording the operator
  and the overlays see. `scripts/walk_race_program.py` prints the same
  walkthrough by hand.

## 1.2.16 - 2026-08-23

- Fixed the third qualifying moto of a 3-moto Total Points class being
  mislabeled "Round 3" — it's now correctly labeled "Main", matching how
  every other class's final is shown. Qualifying motos keep BBS's normal
  "Round 1"/"Round 2" wording; "Round 3" is no longer used anywhere. Added a
  `RoundLabelResolver` that reads bracket-round names (Main, Semi, Qtr, LCQ,
  8th, 16th, 32nd) from RaceManager's own `Ref.Rounds` table so those resolve
  correctly the first time a class advances past qualifying, instead of
  being inferred from which `Lane_N`/`Finish_N` columns happen to be
  populated.

## 1.2.15 - 2026-08-23

- Fixed a bug where a custom overlay theme (e.g. a track's saved theme) only
  rendered on the BBS host itself (`127.0.0.1`) and silently fell back to the
  bundled default colors for every other client on the LAN, including OBS on
  another computer. `GET /api/themes` and `GET /api/themes/{slug}` were
  incorrectly gated behind the remote-admin token, same as theme *edits* —
  they're now public read-only broadcast data, consistent with
  lineup/current/results. Only theme save/reset remain admin-gated.
- Added an "Open Theme Manager" link to the Windows tray flyout menu.
- Made the tray's Start/Stop/Restart BBS controls confirm the Windows service
  actually reached the expected state instead of trusting `ShellExecuteW`'s
  return code, which reports a false success if the UAC prompt is cancelled
  or `sc.exe` fails once elevated. Restart now waits for a confirmed stop
  before issuing start (instead of a fixed 1-second delay), and the menu
  disables these actions while one is already running.

## 1.2.14 - 2026-08-19

- Pooled RaceManager SQL connections instead of opening and closing a new
  connection for every query, reducing per-request latency for Director
  polling and the overlay/lineup/results endpoints.
- Replaced the deprecated FastAPI `on_event` startup/shutdown hooks with a
  `lifespan` context manager; no behavior change.
- Added CI (ruff and pytest on every push and pull request against main).
- Documented the `/themes` Theme Manager workflow and removed stale
  "visual theme editor is planned" language now that it has shipped.

## 1.2.13 - 2026-08-18

- Added optional RaceManager racing age and home-track subtitles to lineup and
  results graphics, omitting absent values cleanly.
- Added protected in-app theme management with supported-setting validation,
  active-theme selection, default restoration, and preservation of unrecognized
  legacy custom-theme properties.

## 1.2.12 - 2026-08-04

- Fixed the Race Director's Jump to moto field so background status polling
  cannot overwrite focused or pending operator input, spinner changes, failed
  submissions, or a successful race-position apply.

## 1.2.11 - 2026-08-01

- Separated physical program segments, competition stages, scoring methods,
  and finalization methods; Total Points classifications no longer appear as
  an operator-facing Overall round.
- Rebuilt navigation around physical race slots so combined motos appear once,
  Next and Previous are symmetric, and Transfer Main events and final Total
  Points motos remain interleaved in scheduled Main-program order.
- Fixed direct Go to Moto selection, actionable unavailable-moto feedback,
  stale-response protection, and class-aware transitions between rounds.
- Added per-event race-position confirmation preferences with an explicit
  reset control.
- Preserved and expanded Results Roll combined-moto ordering, official finish
  order, playback controls, and break-graphic coordination.
- Added safe race-program structure export for anonymized schema diagnostics
  and regression fixtures.
- Added a persistent, resettable Main-program start per Motoboard for events
  whose RaceManager records do not expose an explicit running-order boundary;
  Transfer finals are retained as low-confidence suggestions only.
- Hardened network administration with localhost binding by default,
  configured CORS origins, explicit remote administration, mutation tokens,
  and credential redaction.
- Replaced the Defender-flagged IExpress/hidden-script installer architecture
  with a native WiX Toolset v4 MSI and pinned WinSW Windows service.
- Added offline hash-locked Windows dependencies, build-input validation,
  Authenticode signing support, artifact manifest, CycloneDX SBOM, SHA-256,
  and an exact-artifact Microsoft Defender release gate.

## 1.2.10 - 2026-07-31

- Fixed historic-event Director navigation so Main stepping renders the server
  response immediately, resists stale polling updates, skips incompatible
  classifications, and keeps the selected event pinned.
- Enlarged the visible Windows notification-area artwork with a tightly cropped
  source asset and validated multi-resolution icon generation.
- Completed the official Main-results graphic and server-owned Results Roll,
  including historic-event pinning, a configurable ten-second interval,
  pause/resume, manual previous/next, and stop-at-last behavior.
- Limited automatic results playback to completed RaceManager final Main-branch
  classifications while excluding qualifier, quarterfinal, and semifinal
  entries.
- Added theme-aware Round 1 Break and Main Break graphics that preserve race
  position and pause an active Results Roll before taking air.

## 1.2.9 - 2026-07-31

- Improved historic-event loading in the Race Director by allowing slower
  RaceManager event-list responses and repaired corrupted Director UI
  characters.
- Fixed Main and Overall moto progression so stepping stays within the selected
  finals phase, skips incompatible classifications, and remains at the end when
  no later compatible final exists.
- Added Windows Apps & Features registration with interactive and quiet uninstall commands.
- Added a scoped Windows uninstaller that removes only BBS-owned tasks, processes, services, shortcuts, files, and registry entries.
- Preserved configuration, credentials, logs, themes, and local race state under `%ProgramData%` by default.
- Added automatic restoration of preserved operator data during reinstall.
- Added a controlled Windows uninstall/reinstall validation script and packaging regression checks.
- Started the Windows background task during setup and waited for API readiness before opening Configuration.
- Fixed Windows startup-task registration to use the installed private `python.exe`
  with an explicit module, working directory, task verification, and actionable
  startup diagnostics.
- Moved installed runtime configuration, logs, state, caches, and custom themes
  to `%ProgramData%\BMX Broadcast Suite\UserData`; Program Files is now treated
  as read-only after installation.
- Made the Windows EXE payload deterministic and self-contained from tracked
  Git content, including validation that every wizard-referenced script is
  packaged.
- Kept the IExpress bootstrap hidden through `wscript.exe` so setup and normal
  operation do not leave console windows open.

## 1.2.8

- Added round-aware RaceManager stage resolution using `Motogroup_DBID`, class, round type, round, and lane/finish index instead of treating `Moto_Number` as globally unique.
- Added dynamic phase programs so the Director exposes only phases actually present for the selected class and qualifier group.
- Mapped `Round_Type_ID 123` to qualifier progression and `Round_Type_ID 1` to exact final classification.
- Added evidence-based Main versus Overall classification for transfer and total-points formats.
- Normalized RaceManager `X` finish values as transfer markers rather than numeric placements.
- Added phase-aware Next/Previous Moto behavior that stays in the qualifier or final branch currently on air.
- Added stable motogroup lookup APIs and exact stage metadata to current, lineup, and results payloads.
- Fixed pyodbc 5.2 Windows compatibility by applying supported connection-level query timeout behavior instead of assigning `Cursor.timeout`.
- Added regression tests for duplicate moto numbers, split qualifier groups, transfer markers, total-points Overall stages, unavailable semifinals, phase-aware moto movement, and Windows timeout compatibility.

## 1.2.7

- Added historical RaceManager event listing and persistent motoboard selection in the Race Director.
- Added event-aware lineup and results retrieval for previously completed races.
- Reduced default SQL connection and query timeouts for faster offline recovery.

## 1.2.6

- Bundled the Microsoft ODBC Driver 18 x64 MSI for offline Windows installation.
- Added SHA-256 and Microsoft Authenticode verification for the bundled ODBC installer.
- Fixed the IExpress launcher path bug that caused the setup wizard to exit immediately.
- Fixed administrator relaunch handling so temporary installer files remain available during elevation.
- Fixed the Windows Scheduled Task to use `python.exe` instead of `pythonw.exe`.
- Updated application, tray, documentation, installer, and test version references to 1.2.6.

## 1.2.5

- Added a graphical Windows setup wizard with prerequisite checks, installation-folder selection, and optional machine-startup configuration.
- Added a Windows EXE installer build pipeline using the built-in IExpress packaging tool.
- Added guided installation documentation and SmartScreen guidance for the currently unsigned installer.
- Preserved the PowerShell installer for development and advanced deployments.
- Added independent control over starting the tray application during background-service installation.

## 1.2.4

- Added Windows 10/11 background operation through a machine startup Scheduled Task running as `SYSTEM`.
- Added automatic restart after failure and start-at-boot behavior without an open terminal.
- Added a Windows notification-area controller with live service, API, RaceManager, moto, and class status.
- Added Start, Stop, and Restart controls with Windows elevation prompts.
- Added desktop, Start Menu, and login-start tray shortcuts using an ICO generated from `logo.png`.
- Added Windows background installation, removal, and tray-launch scripts.
- Preserved the existing Ubuntu `systemd` service and AppIndicator tray implementation.
- Added Windows service/tray documentation and platform status tests.

## 1.2.3

- Reworked the main README to reflect the current production status, known limitations, and verified Ubuntu workflow.
- Replaced the original phase roadmap with shipped, near-term, mid-term, and platform-expansion priorities.
- Expanded theme colors for secondary accents, headers, alternate panels, odd/even rows, lane cells, plate numbers, dividers, shadows, and warning banners.
- Applied theme customization consistently to current-moto, lineup, and results overlays.
- Added a complete theme customization guide and updated bundled theme packages.

## 1.2.1

- Added an Ubuntu/Linux machine-wide systemd service that starts BBS at boot and restarts it after failures.
- Added a desktop and system-tray launcher using `logo.png`.
- Added live service, connector API, RaceManager, current-moto, and class status in the tray menu.
- Added tray shortcuts for Controller, Configuration, Diagnostics, Logs, and lineup preview.
- Added authenticated start, stop, and restart controls for the machine service.
- Added service installation and removal scripts plus Linux service documentation.

## 1.2.0

- Added automatic RaceManager schema detection for the optional `MB.Race_Riders.Nickname` column.
- Preserved the `nickname` API field as `null` on older RaceManager databases instead of failing lineup queries.
- Updated Ubuntu/Debian prerequisites and installer checks for Python virtual environments and Microsoft ODBC Driver 18.
- Documented native OBS Studio installation, Browser Source requirements, overlay URLs, preview mode, diagnostics, and the verified troubleshooting workflow.
- Updated application and diagnostics version reporting to 1.2.0.

## 1.1.0

- Added centralized console and daily rotating file logging.
- Added `/logs`, `/api/logs`, and log download support.
- Added request timing, startup, exception, and database error logging.
- Added configurable log directory, level, and retention.
- Added complete Windows/Linux installation, first-run, configuration, OBS, browser-source, troubleshooting, FAQ, shortcut, upgrading, and backup/restore guides.


## 0.9.0

- Added last-known-good lineup cache and stale-data metadata.
- Preserves the last valid lineup through temporary SQL Server outages.
- Added automatic class-name synchronization from RaceManager.
- Added a WebSocket broadcast snapshot feed and overlay WebSocket clients.
- Added experimental results API and OBS results overlay.
- Added Race Director results controls and backward-move confirmations.
- Added resilience and results unit tests.

## 0.8.0

- Added installation scripts and diagnostics dashboard.

## 1.0.0
- Removed Bend-specific SQL defaults from application code.
- Added `/configuration` setup screen and `/api/configuration` API.
- Made track name, theme, application host/port, SQL host/instance/port/database/login/password/driver, timeouts, CORS, and state paths configurable through `.env`.
- Added config-aware Windows, Linux, Docker, and systemd launch commands.
- Password values are write-only in the configuration UI and never returned by the API.
