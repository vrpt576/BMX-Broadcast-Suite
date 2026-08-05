# Track Configuration Guide

Configuration is stored locally in `.env`; it should never be committed to Git.

## Identity and web server

- `BBS_TRACK_NAME`: public track name
- `BBS_DEFAULT_THEME`: theme folder slug
- `BBS_APP_HOST`: listen address; the safe default is `127.0.0.1`
- `BBS_APP_PORT`: HTTP port, normally `8000`
- `BBS_PUBLIC_BASE_URL`: address other computers use
- `BBS_CORS_ORIGINS`: comma-separated trusted browser origins. Blank allows
  localhost on the configured port. A legacy `*` is deliberately narrowed to
  the localhost defaults.
- `BBS_REMOTE_CONTROL_ENABLED`: explicitly permit authenticated operator
  mutations from non-loopback clients
- `BBS_CONTROL_TOKEN`: secret sent as `X-BBS-Control-Token` or a Bearer token
- `BBS_REMOTE_ADMIN_ENABLED`: separately permit authenticated configuration,
  diagnostics, and log access from non-loopback clients
- `BBS_ADMIN_TOKEN`: separate admin secret sent as `X-BBS-Admin-Token` or a
  Bearer token; an admin token may also authorize operator mutations

## Local and remote access

BBS listens only on `127.0.0.1` by default. This is appropriate when OBS and
Director run on the BBS computer. Local Director and Configuration requests do
not require a token.

To serve read-only browser graphics to OBS on another trusted LAN computer,
set `BBS_APP_HOST` to the BBS server's LAN address (or `0.0.0.0`) and restart.
Read-only overlay data remains available, but remote controls, configuration,
diagnostics, and logs stay blocked. Same-origin OBS Browser Sources do not need
CORS. If a separate browser origin needs API access, list that exact origin in
`BBS_CORS_ORIGINS`; do not use a wildcard.

Remote control and remote administration are independent opt-ins. Generate
long random tokens, store them only in the protected BBS `.env`, and send them
in the appropriate request header. For example:

```powershell
$Headers = @{ "X-BBS-Control-Token" = "PASTE-LONG-RANDOM-CONTROL-TOKEN" }
Invoke-RestMethod -Method Post `
  -Uri "http://bbs-server:8000/api/current/next" `
  -Headers $Headers
```

```powershell
$Headers = @{ "X-BBS-Admin-Token" = "PASTE-LONG-RANDOM-ADMIN-TOKEN" }
Invoke-RestMethod -Uri "http://bbs-server:8000/api/diagnostics" -Headers $Headers
```

Tokens are not returned by the configuration API or the public overlay
configuration endpoint. BBS uses the socket peer address for its loopback
decision and does not trust forwarded-IP headers by default.

## SQL Server

- `BBS_SQL_HOST`: RaceManager SQL host or IP
- `BBS_SQL_INSTANCE`: named instance; leave blank when using a TCP port
- `BBS_SQL_PORT`: commonly 1433
- `BBS_SQL_DATABASE`: normally `RACE`
- `BBS_SQL_USER` and `BBS_SQL_PASSWORD`: read-only credentials
- `BBS_SQL_DRIVER`: installed ODBC driver name
- encryption, certificate trust, connect timeout, and query timeout settings

A named instance takes precedence over the port. Examples:

```env
BBS_SQL_HOST=192.168.1.50
BBS_SQL_INSTANCE=RACEMANAGER
BBS_SQL_PORT=
```

```env
BBS_SQL_HOST=192.168.1.50
BBS_SQL_INSTANCE=
BBS_SQL_PORT=1433
```

## Logging and state

- `BBS_LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, or `ERROR`
- `BBS_LOG_DIR`: log directory
- `BBS_LOG_RETENTION_DAYS`: rotated file retention
- current moto and lineup cache paths

The configuration API never returns the SQL password or access tokens. Leaving
a secret field blank in the form preserves the existing value.
