# First Run Guide

1. Start BBS and open `/setup`. It checks (and can fix) the ODBC driver and
   the read-only RaceManager account guided -- see
   [The Setup wizard](setup-wizard.md). If you'd rather configure SQL by
   hand, skip to step 3.
2. Open `/configuration`.
3. Set track name and default theme.
4. If you didn't use `/setup`: enter SQL host, instance or port, database, login, password, and ODBC driver.
5. Save settings. Restart BBS after changing host, port, or CORS settings.
6. Open `/diagnostics`; resolve every red check before racing.
7. Open `/director` and verify Demo Mode first.
8. Open `/overlay/current`, `/overlay/lineup`, `/overlay/results`, and `/overlay/break` in a browser.
9. Add the required Browser Sources to OBS.
10. Switch from demo data to live data and compare the displayed moto and riders with RaceManager.
11. Keep `/diagnostics` and `/logs` open during the first event.

Before putting results on air, compare at least one classification with the
official RaceManager report. Use the Director Results Roll controls to show the
selected Main result or play available Mains in ascending moto order.
See [Results Roll](results-roll.md).
