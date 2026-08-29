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

1. **Enter the SQL Server host and instance.** If BBS is running on the
   same computer as RaceManager (the common case), leave the host as
   `localhost` -- BBS looks up the real instance name for you (usually
   `USABMX`) and pre-fills it.
2. **Click "Check connection."** BBS connects using *your own Windows
   login* (you need to already be an administrator on this SQL Server for
   this to work -- if you can open SQL Server Management Studio and see
   the databases, you're set). It reports, in plain language, anything
   that would block creating the account:
   - **Mixed-mode authentication is off.** A SQL login can't be created
     until this is turned on, which needs a SQL Server restart -- BBS
     will tell you this and will not do it for you, because restarting
     SQL Server while racing is happening is exactly the kind of thing
     that shouldn't happen automatically. Fix it (SSMS: right-click the
     server → Properties → Security → "SQL Server and Windows
     Authentication mode"), restart SQL Server during a break in racing,
     then come back.
   - **BBS can't reach it over the network.** Also reported, also not
     fixed automatically -- see
     [Prepare the RaceManager PC](racemanager-pc-setup.md) for enabling
     TCP/IP and opening a firewall rule, if BBS runs on a different
     computer than RaceManager.
3. **Review the exact SQL.** Once nothing is blocking, BBS shows you
   precisely what it's about to run -- `CREATE LOGIN`, `CREATE USER`,
   `ALTER ROLE db_datareader` -- with a real, randomly generated password
   already filled in. Nothing has run yet. A **Copy SQL** button is right
   there if you'd rather hand this to your own DBA, or run it yourself in
   SSMS or `sqlcmd`.
4. **Either let BBS run it, or run it yourself:**
   - **"Run it for me"** -- BBS runs exactly the SQL you just reviewed,
     then reconnects *as the new account* and reads a real row from
     RaceManager to prove the account actually works (not just that the
     `CREATE` statements didn't error), then saves the credentials into
     BBS's own configuration. You'll never see the password again after
     this succeeds -- it's not logged, not echoed back to the page, and
     never shown in Diagnostics.
   - **Ran it yourself instead?** Paste the password back into the
     "Verify and save" box further down the page. BBS does the exact same
     verification (reconnect, read a real row) before saving it -- it
     never just trusts that you ran it correctly.

If `bbs_connector` already exists (re-running the wizard, or a previous
setup), BBS detects that and offers to reset its password instead of
failing or creating a duplicate account.

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
