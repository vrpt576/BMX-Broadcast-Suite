# BMX Broadcast Suite (BBS)

Reads live USA BMX RaceManager SQL Server data (read-only) and serves a browser-based Race
Director plus transparent OBS Browser Source overlays (current moto, lineup, results, breaks).
Python / FastAPI / pyodbc. Full historical rationale, lessons learned, and the original
database-discovery audit live in the project handoff doc (kept outside this repo); this file
distills the parts a future session needs without re-reading that whole document.

## Production philosophy

1. **RaceManager is always read-only.** BBS never writes RaceManager tables — only its own
   local JSON state under `%ProgramData%\BMX Broadcast Suite\UserData` (Windows) / the
   configured state dir (Linux).
2. **Stable database identities over display numbers.** `Moto_Number` is a displayed running
   order, not a unique identity — it's reused across qualifier and final branches and across
   classes. Never key navigation or caching off it alone (see "Round/stage model" below).
3. **Don't invent phase mappings that haven't been proven from real data.** Quarterfinal/
   semifinal storage is a documented open item — BBS deliberately does not guess at it.
4. **Operator control is authoritative for broadcast navigation.** Automation (e.g. an inferred
   Main-program boundary) is advisory only; the operator's saved choice always wins.
5. **Race-day reliability beats cleverness.** Last-known-good caching, stale-data indication,
   and graceful degradation matter more than fancy automation.
6. **Track branding and mutable state stay outside core application files** (themes are
   packages under `themes/`, not hardcoded; runtime state is outside `Program Files`).
7. **Public installers must be traceable to an exact source commit and exact validation** —
   see Release process below.

## Configuration and security model

Configuration lives in a local `.env` (never committed; `.env.example` is the template).

- Safe default bind is `127.0.0.1`. Remote read-only overlays can be served on a trusted LAN
  by binding to the LAN address or `0.0.0.0`.
- Remote **mutation/control** and remote **administration** are separate opt-ins, each gated by
  its own token: `BBS_REMOTE_CONTROL_ENABLED` / `BBS_CONTROL_TOKEN` and
  `BBS_REMOTE_ADMIN_ENABLED` / `BBS_ADMIN_TOKEN`. Tokens travel via `X-BBS-Control-Token` /
  `X-BBS-Admin-Token` or Bearer auth.
- The configuration API never returns SQL passwords or tokens; leaving a secret field blank in
  the UI preserves its current value.
- BBS uses the socket peer address for loopback decisions — it does not trust forwarded-IP
  headers by default.
- No wildcard CORS — list exact trusted origins (`BBS_CORS_ORIGINS`) only when cross-origin
  access is actually needed.
- **SQL instance vs. port trap:** BBS gives a named SQL instance precedence over a TCP port.
  When configuring host + TCP port, leave the SQL instance field blank, or a correct port can
  appear broken.
- SQL Server must never be exposed through public internet port forwarding; the dedicated
  `bbs_connector` login should hold `db_datareader` only on the `RACE` database — nothing more.

## Database schema and rider join path

- Database `RACE`, primary schema `MB`. Access is `SELECT`-only.
- Confirmed rider join path for lineup/results:
  `Motogroup_Riders → Racegroup_Riders → Race_Riders`, scoped by `Age_Classes.Motoboard_ID`.
- Rider age: `MB.Race_Riders.Age_Race` (not `Age_Calendar` — intentionally unused, and **never**
  derive age by parsing a combined class name; RaceManager can combine ages/classes locally, so
  a rider's real age can legitimately differ from the label).
- Home track: `MB.Race_Riders.Home_Track`, rendered verbatim (data quality is RaceManager's).
- Optional columns (e.g. `Nickname`) must be detected via `COL_LENGTH` before querying — some
  RaceManager schema versions don't have them. Never let an optional vendor column 503 an
  endpoint; return `null` for it instead. (`connector/services/motoboard_service.py` memoizes
  this detection per instance — don't re-probe per request.)
- `X` in a qualifier finish field is a transfer-to-main marker, not a numeric place. Normalize
  to `finish: null, transferred: true, status: "Transfer"` before any numeric validation/sort.

## Round/stage/results model

A resolved exact stage = `motoboard_id + class_id + round_type_id + round_id + motogroup_id +
round_index` (`moto_number` is display-only).

- `Round_Type_ID 123` = qualifier/moto progression (`Round 1→Lane_1/Finish_1`,
  `Round 2→Lane_2/Finish_2`, `Round 3→Lane_3/Finish_3`). The third round is
  *displayed* as "Moto 3", or as "Main" when the class ends on that moto —
  "Round 3" is never put on air, and a class is never announced as Main twice.
- `Round_Type_ID 1` = final-classification branch. This can be either a **separately raced
  final** or an **accumulated Total Points classification** — the type alone never tells you
  which. Don't auto-label a type-1 record "Main" or "Overall" just because it's type 1.
- Four concepts stay separate and must not collapse into each other: **program segment**
  (Round 1/2/3, Main), **competition stage** (qualifier, Main Event, Total Points final moto),
  **scoring method** (Transfer, Transfer LST, Total Points), **finalization method** (separately
  raced vs. accumulated). "Overall" is a placing, not a navigable phase — never create a
  Director round for it.
- Total Points: the physical final moto can be `program_segment=main` +
  `competition_stage=total_points_final_moto` while the type-1 accumulated record is the
  official results source; the accumulated record does **not** create a second physical race
  slot. Director stays in Main; results show the accumulated placing.
- **No reliable event-wide "Main starts here" field exists in RaceManager.** Rejected
  candidates (all examined and found insufficient): `Has_Mains`, `Round_Type_ID` alone,
  `Moto_Number_First/Last`, `Motogroup_Count`, `Moto_Number`, `Moto_Key`/`Sub_Moto`,
  `Run_Order_Custom`/`Moto_Format_ID`/`Transfer_Format_ID`/`Advance_Type_ID`, maintenance
  timestamps. Resolution: an **operator-confirmed** `main_program_start_moto`, stored locally
  per Motoboard ID (`race_phase_overrides.json`). The first independently-classified Transfer
  final is advisory/low-confidence only and must never silently change navigation.
- Navigation unit is a **race slot**: one physical scheduled occurrence in one program segment
  on one Motoboard, keyed `motoboard-id:program-segment:displayed-moto`. Combined classes
  sharing a displayed moto appear once. Next/Previous are symmetric over slots, not raw
  Moto_Number.
- Results: BBS reads RaceManager's official finishes only — it never infers order from gate/
  lane/lineup, never fabricates times or points, and excludes qualifier/transfer data from
  automatic official-results playback. A Main with no numeric finish is skipped, not guessed.

## Windows packaging / antivirus lessons

- Current architecture (since v1.2.11): **WiX Toolset v4 MSI** + pinned **WinSW** service
  wrapper, service name `BMXBroadcastSuite`, installs to `C:\Program Files\BMX Broadcast
  Suite` (read-only after install); all mutable state lives under
  `%ProgramData%\BMX Broadcast Suite\UserData`.
- Do not reintroduce IExpress/WEXTRACT, hidden VBScript/PowerShell bootstrapping, execution-
  policy bypass, SYSTEM Scheduled Tasks for startup, or a self-deleting uninstall worker.
  That exact combination (v1.2.9/v1.2.10) triggered a Windows Defender
  `Trojan:Win32/Wacatac.B!ml` detection on the compiled installer — not because the code was
  malicious, but because the *pattern* matches malware installer heuristics. Source-level
  review cannot prove a compiled artifact clean; only the WiX/MSI-owned lifecycle avoids the
  pattern entirely.
- **Never disable Defender or add an exclusion to force an installer through.** If Defender
  flags the exact final release artifact: do not upload it, submit that exact file to
  Microsoft Security Intelligence, and keep the release source-only/draft until resolved.
- Migration from the legacy EXE (v1.2.10 and earlier) to MSI is not an in-place WiX upgrade:
  uninstall the old app first (this preserves `ProgramData`), then install the MSI.
- Known upgrade gotchas: a post-install hashing step can fail merely because the running
  service holds `connector/logs/*` open (exclude live logs from hashing, don't treat this as a
  real failure); the tray process is not auto-replaced on upgrade — restart it explicitly (or
  tell the operator to sign out/in) after every install/upgrade.

## Release process

**"Merged" is not "released."** Follow this sequence exactly (see `scripts/` for the actual
tooling):

1. Confirm clean `main` at the intended commit; confirm version markers/release notes
   (`CHANGELOG.md`) already reflect the real version and date.
2. Full source validation: `pytest`, `python -m compileall`, `ruff check .`,
   `git diff --check`.
3. Build the MSI from a **clean worktree at that exact commit**:
   `.\scripts\build-windows-installer.ps1 -CertificateThumbprint THUMBPRINT` (or that script's
   unsigned option for local validation). Record whether the build is signed or unsigned —
   unsigned must be called out explicitly, not silently shipped.
4. Generate SHA-256, the build manifest, and a CycloneDX SBOM for the artifact.
5. Run the exact-artifact Microsoft Defender scan **before uploading anywhere**. Any detection
   on the exact final artifact blocks release (see antivirus lessons above).
6. Back up installed `UserData`, then install that exact MSI as an in-place upgrade on the
   test machine; verify service, tray (restart it), diagnostics, DB connection, themes, state
   preservation, APIs, and overlays.
7. Tag the exact accepted source commit. Publish a **non-draft, non-prerelease** GitHub release
   with the MSI, checksum, manifest, and SBOM attached.
8. Download the published MSI and re-verify its hash matches before telling anyone to install
   it. Keep the previous release available until the next live event completes successfully.

Do not rebuild after installed-artifact acceptance and upload a different, untested binary —
the uploaded MSI must be byte-for-byte the one that was accepted in step 6.
