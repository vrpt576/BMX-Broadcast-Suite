# Backup and Restore Configuration

## Back up

Stop BBS and copy:

- `.env`
- custom folders under `themes/`
- `data/current_moto.json`
- `data/last_known_lineup.json`
- logs when needed for incident review

Do not publish the backup because `.env` contains the SQL password.

## Restore to another computer

1. Install the same or newer BBS release.
2. Copy `.env` to the repository root.
3. Copy custom themes and optional state files.
4. Confirm the new computer has the configured ODBC driver.
5. Update host-specific values such as `BBS_PUBLIC_BASE_URL` and application port.
6. Start BBS and run `/diagnostics` before opening OBS.

A clean restore can omit cache and log files; BBS will recreate them.
