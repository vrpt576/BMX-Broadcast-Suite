# The Setup Wizard

`/setup` is the page BBS wants you to land on right after installing it.
It exists so a track that has never used BBS before can get RaceManager
connected without installing anything by hand or writing any SQL
themselves -- and so a track that prefers to do those things by hand still
can, with BBS showing exactly what it would have run.

Open it from the Windows tray ("Open Setup"), from a link on
`/diagnostics`, or directly at `http://127.0.0.1:8000/setup`.

**It only ever works from the BBS computer itself** -- not from another
computer on your network, even with a remote-admin token configured. It
creates database accounts and installs software; that's deliberately never
something a token can authorize remotely. See
[Configuration and security](../CLAUDE.md) if you're not sure why.

## What it checks

One page, four things, each with a way to fix it if something's wrong:

- **ODBC driver** -- the piece of software that lets BBS talk to SQL
  Server at all.
- **Database connection** -- can BBS actually log in.
- **RaceManager data** -- once connected, can BBS read a real event.
- **Sqorz live timing** -- optional; see
  [Sqorz Live Timing](sqorz-live-timing.md) if your track uses it.

## Step 1: the ODBC driver

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

## Step 2: the read-only RaceManager account

This creates a SQL Server login named `bbs_connector` with exactly one
permission -- read-only access to the `RACE` database (`db_datareader`).
It can never write to RaceManager, and BBS never asks for more than that.

**The first thing the page asks is whether BBS is installed on the same
computer as RaceManager's SQL Server.** That answer decides which of two
different setup paths you'll use -- it isn't a formality:

- BBS's Windows Service runs as `LocalSystem` by default, not as whichever
  operator is logged in. When BBS and RaceManager share a computer, that's
  usually still enough to connect with your own administrator rights
  behind the scenes. When BBS reaches RaceManager's SQL Server over a
  network -- a dedicated broadcast PC, a laptop on Tailscale, anything not
  physically the RaceManager machine -- the connection authenticates as
  the *computer account* instead, which essentially never has SQL Server
  admin rights.
- A dedicated broadcast PC is the setup these docs themselves recommend
  (see [Prepare the RaceManager PC](racemanager-pc-setup.md)), so **the
  "different computer" path below is not an edge case** -- for many
  tracks it's the normal one.

### Path A: BBS is on the same computer as RaceManager

1. Choose **"Yes, same computer"** on the Setup page.
2. **Enter the SQL Server host and instance.** Leave the host as
   `localhost` -- BBS looks up the real instance name for you (usually
   `USABMX`) and pre-fills it.
3. **Click "Check connection automatically."** BBS attempts to connect
   using its own Windows identity. If it works, it reports, in plain
   language, anything that would still block creating the account:
   - **Mixed-mode authentication is off.** A SQL login can't be created
     until this is turned on, which needs a SQL Server restart -- BBS
     will tell you this and will not do it for you, because restarting
     SQL Server while racing is happening is exactly the kind of thing
     that shouldn't happen automatically. Fix it (SSMS: right-click the
     server -> Properties -> Security -> "SQL Server and Windows
     Authentication mode"), restart SQL Server during a break in racing,
     then come back.
   - **BBS can't reach it over the network.** Also reported, also not
     fixed automatically -- see
     [Prepare the RaceManager PC](racemanager-pc-setup.md) for enabling
     TCP/IP and opening a firewall rule.
4. **If it can't connect automatically, that's not a failure to recover
   from.** It just means BBS's service identity doesn't have SQL Server
   admin rights on this machine either -- the page falls through to the
   same "Generate the SQL" flow as Path B, described below.
5. **If it does connect**, review the exact SQL BBS is about to run --
   `CREATE LOGIN`, `CREATE USER`, `ALTER ROLE db_datareader` -- with a
   real, randomly generated password already filled in. Nothing has run
   yet. Then either:
   - **"Run it for me"** -- BBS runs exactly the SQL you just reviewed,
     then reconnects *as the new account* and reads a real row from
     RaceManager to prove the account actually works (not just that the
     `CREATE` statements didn't error), then saves the credentials into
     BBS's own configuration.
   - **Copy it and run it yourself** in SSMS or `sqlcmd`, then paste the
     password back (see "Verifying and saving," below).

### Path B: BBS is on a different computer than RaceManager

1. Choose **"No, a different computer"** on the Setup page.
2. **Enter the SQL Server's hostname or IP** -- the RaceManager machine's
   address, not BBS's own (the page clears the `localhost` default and
   prompts for this once you pick this path, since `localhost` here would
   point BBS at itself).
3. **Click "Generate the SQL."** BBS does not attempt to connect -- there
   is nothing to check, since it doesn't expect to have rights here. It
   produces a script that safely creates `bbs_connector` only if it
   doesn't already exist (guarded with `IF NOT EXISTS`, so running it
   against an account that's already there changes nothing). If you
   already know the login exists and want to rotate its password instead,
   check **"This login already exists -- generate a password reset
   instead"** first.
4. **Copy the SQL** and hand it to whoever administers that SQL Server --
   yourself in SSMS or `sqlcmd`, or your track's own DBA. There is no
   "Run it for me" for this path; BBS genuinely cannot reach that server
   with enough privilege to run it, so review-and-copy is the only option,
   not a lesser one.
5. Once it's been run, paste the password back (see "Verifying and
   saving," below).

### Verifying and saving (both paths)

Whether the SQL ran automatically or you pasted the password back
yourself, BBS handles it identically:

- It reconnects **as `bbs_connector`** and reads a real row from
  RaceManager before ever saving anything -- it never just trusts "the
  SQL didn't error" or "I ran it."
- The password is never logged, never echoed back to the page in any
  response, and never shown in Diagnostics. BBS's request logging records
  only the method, path, status code, and timing of each request -- never
  a request body -- so a pasted password never ends up in a log file
  either way.
- On success, it's written into BBS's own configuration (the same `.env`
  file every other BBS secret -- the control token, the admin token --
  already lives in, protected the same way: by filesystem permissions on
  that file, not by encryption).
- **BBS then switches to using `bbs_connector` for all normal operation.**
  Saving new credentials clears BBS's cached database connection, so the
  very next time BBS needs to talk to RaceManager, it does so as the
  read-only login the wizard just created or verified -- not as
  `LocalSystem`, and not with whatever rights your own Windows account
  happened to have during setup.

If `bbs_connector` already exists (re-running the wizard, a previous
setup, or Path B's guarded script finding it already there), BBS detects
that and offers a password reset instead of failing or creating a
duplicate account.

### If BBS's own connection turns out to be a SQL Server admin

When Path A's automatic connection succeeds, the page also reports
whether the account BBS connected as has `sysadmin` rights on that SQL
Server. This is purely informational -- it's your SQL Server's own
configuration, not a BBS setting, and BBS doesn't change it. But it's
worth knowing: it means that SQL Server currently trusts BBS's service
account more broadly than it needs to, at least until this wizard
finishes and switches BBS over to the read-only `bbs_connector` login (see
above). If your SQL Server administrator wants to tighten that, it's a
change made outside BBS entirely.

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
  be seen and exercised on a machine that already has Driver 18. The
  *installed drivers* list shown is still the real one; only whether it's
  treated as acceptable is forced. If you go on to click an install
  button, it still runs the real installer for real -- against a machine
  that already has the driver, that's a harmless repair/reinstall, not a
  no-op fake.
- **A custom `login_name`** -- every SQL wizard endpoint
  (`/api/setup/sql/plan`, `/api/setup/sql/generate`,
  `/api/setup/sql/apply`, `/api/setup/sql/verify-and-store`,
  `/api/setup/sql/cleanup`) accepts an optional `login_name` field,
  defaulting to `bbs_connector`. Passing a different name (for example,
  `bbs_connector_test`) lets you exercise the actual "create a login that
  doesn't exist yet" path and the cleanup path -- both untestable against
  a real track's SQL Server, where `bbs_connector` typically already
  exists once the wizard has been run once. This is an API-level option
  (there is no field for it on the page itself) so it's easy to reach for
  a manual test but hard to stumble into by accident. Since it flows
  directly into bracket-quoted SQL identifiers (`CREATE LOGIN [name]`,
  etc.), every endpoint validates it against a strict allowlist -- letters,
  digits, and underscores only, up to 128 characters -- and rejects
  anything else with a 400 before it ever reaches a generated script or
  connection string.
