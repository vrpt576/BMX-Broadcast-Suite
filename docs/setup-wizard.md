# The Setup Wizard

`/setup` is the page BBS wants you to land on right after installing it.
It exists so a track that has never used BBS before can get RaceManager
connected without anyone needing to know what SQL Server is, let alone
write any of it.

Open it from the Windows tray ("Open Setup"), from a link on
`/diagnostics`, or directly at `http://127.0.0.1:8000/setup`.

**Before you get here:** running the BBS installer shows Windows'
"Windows protected your PC" screen first. This build isn't signed with a
paid code-signing certificate, so SmartScreen doesn't recognize the
publisher yet -- click **More info**, then **Run anyway** to continue. It
isn't a sign anything is wrong with the file.

**It only ever works from the BBS computer itself** -- not from another
computer on your network, even with a remote-admin token configured. It
creates database accounts and installs software; that's deliberately never
something a token can authorize remotely. See
[Configuration and security](../CLAUDE.md) if you're not sure why.

## What it checks

One page, four things, each with a way to fix it if something's wrong:

- **SQL Server driver** -- the piece of software that lets BBS talk to
  RaceManager's database at all.
- **Database connection** -- can BBS actually log in.
- **RaceManager data** -- once connected, can BBS read a real event.
- **Sqorz live timing** -- optional; see
  [Sqorz Live Timing](sqorz-live-timing.md) if your track uses it.

## Step 1: the SQL Server driver

If BBS reports the driver missing, the page offers two ways to install it,
both requiring you to check a box confirming you've reviewed
[Microsoft's license terms](https://aka.ms/odbc18eularedist) (linked
directly from the page) first:

- **Install bundled copy** -- the driver ships inside BBS's own installer,
  so this works with no internet connection at all. This is the one to use
  at a track with unreliable WiFi.
- **Download latest from Microsoft** -- fetches the current installer
  directly from Microsoft instead. Use this if you specifically want the
  newest version rather than the one BBS shipped with.

Either way, BBS runs the real Microsoft installer silently in the
background and re-checks itself afterward.

## Step 2: connect BBS to RaceManager

This creates a login named `bbs_connector` that can only *read*
RaceManager's data -- it can never change anything. Once it's set up, BBS
uses it, not an administrator account, for everything it does day to day.

**If BBS is already connected and reading RaceManager**, the page says so
plainly and collapses this whole section to "already set up, nothing to
do here," with a **Change this** link if you need to redo it. It doesn't
walk you through creating an account you already have.

Otherwise, there are four ways to finish, in the order the page tries
them -- least typing first. BBS detects what it can and only asks you for
something once it actually needs it from you; it doesn't ask a question
up front to decide which path to use.

### Set it up automatically (try this first)

One button, no fields. Click **Set it up automatically** and BBS tries
using its own Windows identity to connect to a SQL Server on this same
computer. On a single-PC track -- one computer running RaceManager and
everything else, the most common small-track setup -- this often just
works, because the local SQL Server installation frequently already
trusts that identity as an administrator. If it works, you're done and
never typed anything.

**If it doesn't work, that's normal, not an error.** The page says so
calmly and reveals the next option below -- it commonly just means BBS is
on a different computer than RaceManager's SQL Server, or this computer's
identity isn't a SQL Server administrator here. Nothing is wrong, and
nothing you need to fix before continuing.

### Enter administrator credentials

Shown once "Set it up automatically" doesn't pan out. Enter:

- **Which computer runs RaceManager's database** -- leave this as
  `localhost` if BBS is installed on the same computer as RaceManager;
  otherwise enter that computer's name or address. If you don't know the
  exact instance name or port, click **Find it for me** next to the
  field once you've entered the address -- it asks that computer's SQL
  Server Browser service (the same thing SQL Server Management Studio
  uses to list instances) rather than making you go find it yourself,
  and fills in the "Advanced" instance/port fields on success. If the
  Browser service is turned off there (common), it says so plainly and
  checks the one standard SQL Server port instead of guessing.
- **A SQL Server administrator's username and password.** This is not
  `bbs_connector`, and it is not your own Windows login -- it's whichever
  account your RaceManager software (or whoever set it up) uses to
  administer the database itself. If you don't know it, whoever installed
  RaceManager likely does.

Click **Set it up**. BBS connects as that administrator account over the
network -- this works whether BBS and RaceManager's SQL Server share a
computer or not, since signing in with a username and password doesn't
care where the two computers are, only that it can reach the server over
the network. It checks the account is actually able to create or manage
logins (if not, it says so in plain language rather than surfacing a raw
SQL Server error), creates `bbs_connector` (or resets its password if
it's already there), verifies the result by reading a real row of race
data, and saves it. **The administrator username and password are used
once, for this one action, and then forgotten** -- never saved to disk,
never written to a log, never shown back to you or anyone else.

**If "Enter administrator credentials" fails:**

- *Couldn't connect* -- the address, username, or password was wrong.
  Double-check them (the exact technical error is shown underneath, in
  case you need to relay it to whoever manages the SQL Server).
- *This SQL Server only accepts Windows logins* -- some SQL Servers are
  configured to refuse a username-and-password sign-in entirely, no
  matter what's typed in. BBS checks for this specifically (a real check
  against the server, not a guess) and says so plainly if that's the
  case, pointing at what does work instead: installing BBS on the same
  computer as RaceManager's SQL Server (so "Set it up automatically" can
  sign in with Windows instead), or "Prefer to have someone else run
  this?" below, run by a Windows-authenticated administrator.
- *Connected, but doesn't have permission* -- the account you used isn't
  a SQL Server administrator. Ask whoever administers it to grant that
  account "ALTER ANY LOGIN" (or make it a full administrator/"sysadmin"),
  or use one of the other options instead.

### Already have a working login for BBS to use?

If `bbs_connector` already exists and you know its password, there's
nothing to create -- enter the SQL Server address and that password, and
BBS verifies it by reading a real row of race data and starts using it.
No SQL runs at all.

### Prefer to have someone else run this?

Some tracks have a database administrator (DBA) or IT support who'd
rather do this themselves. This generates the exact script to hand them
-- click **Generate the script**, then **Copy**.

**Whoever runs this needs to be a SQL Server administrator** (a
"sysadmin", or a login with "ALTER ANY LOGIN" permission). Signing in as
`bbs_connector` itself will not work -- it can only read race data, not
create or change logins. This is stated on the page itself, next to the
script, because it's the single most common way this goes wrong: someone
runs it while connected as `bbs_connector`, not as an administrator.

If it fails, the page includes troubleshooting for the errors that
actually happen:

| What you'll see | What it means |
|---|---|
| `Msg 15151 ... Cannot alter the login ... you do not have permission` | The account that ran this isn't a SQL Server administrator. Reconnect as an administrator account (not `bbs_connector`) and try again. |
| `Msg 15025 ... The server principal already exists` | This login already exists. Generate a password-reset script instead (the checkbox above "Generate the script"), or use "Set it up automatically" -- it handles this by itself. |
| `Login failed for user '...'` | The username or password used to connect was wrong. |
| `A network-related or instance-specific error has occurred` / `Cannot connect to server` | Couldn't reach the SQL Server at all. Double-check the server name and instance, and that it accepts remote connections if it's on a different computer. |

Once it's been run, come back to "Already have a working login for BBS to
use?" above to finish.

This is deliberately just a T-SQL script, not a downloadable program.
BBS does not generate a PowerShell (`.ps1`) script for this: a downloaded
`.ps1` opens in Notepad instead of running for most people, and getting
it to actually execute would mean either fighting Windows' Mark-of-the-
Web protection or telling someone to pass `-ExecutionPolicy Bypass` --
reintroducing exactly the kind of thing that got an earlier BBS release
flagged as malware (see "Why this runs after install," below).

### BBS's day-to-day connection is always the read-only login

Independent of all four options above: if `/api/setup/status` or
`/diagnostics` shows BBS's *current* database connection succeeding, that
connection is always `bbs_connector` -- read-only, by design, regardless
of which option set it up. There's no ongoing administrator connection to
worry about either way: "Set it up automatically"'s one-time use of BBS's
own Windows identity, and "Enter administrator credentials"'s one-time
use of whatever account was typed in, both end the moment the login is
created or reset and verified.

### Undoing this

Every wizard page has an "Undo this later" section with the exact SQL to
remove the account (`DROP USER` / `DROP LOGIN`) -- a track can remove it
without contacting anyone.

## Why this runs after install, not during

BBS deliberately does not use a single bootstrapper `.exe` that chains an
ODBC driver install with BBS's own -- that pattern (an unsigned executable
that extracts payloads and launches other installers) is exactly what
triggered a false Windows Defender malware detection on an earlier BBS
release. Installation stays a plain WiX-owned MSI; this wizard runs
*inside* already-installed, already-running BBS instead, as an ordinary
web page. See `CLAUDE.md`'s "Windows packaging / antivirus lessons" for the
full history.

## Testing aids

Two things exist purely to make this wizard testable on a machine that
doesn't naturally hit every code path -- **neither is meant for a track
operator, and neither appears in the wizard's normal UI:**

- **`BBS_SETUP_FORCE_ODBC_MISSING`** -- set this environment variable
  (to anything truthy) before starting BBS and Step 1 reports the driver
  as not acceptable regardless of what's actually installed, so the
  "driver missing" screen (the license checkbox, the install buttons) can
  be seen and exercised on a machine that already has the driver. The
  *installed drivers* list shown is still the real one; only whether it's
  treated as acceptable is forced. If you go on to click an install
  button, it still runs the real installer for real -- against a machine
  that already has the driver, that's a harmless repair/reinstall, not a
  no-op fake. On a Windows Service specifically (not a dev shell): this
  has to be set as an environment variable on the *service process*, not
  a terminal -- add an `<env name="BBS_SETUP_FORCE_ODBC_MISSING"
  value="1" />` line to the installed `BBSService.xml`, then restart the
  service (WinSW re-reads its config on every start/restart; no reboot
  needed).
- **A custom `login_name`** -- every SQL wizard endpoint
  (`/api/setup/sql/auto-setup`, `/api/setup/sql/admin-setup`,
  `/api/setup/sql/generate`, `/api/setup/sql/verify-and-store`,
  `/api/setup/sql/cleanup`) accepts an
  optional `login_name` field, defaulting to `bbs_connector`. Passing a
  different name (for example, `bbs_connector_test`) lets you exercise
  the "create a login that doesn't exist yet" path and the cleanup path
  -- both untestable against a real track's SQL Server, where
  `bbs_connector` typically already exists once the wizard has been run
  once. This is an API-level option (there is no field for it on the
  page itself) so it's easy to reach for a manual test but hard to
  stumble into by accident.
