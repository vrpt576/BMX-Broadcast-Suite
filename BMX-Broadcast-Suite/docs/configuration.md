# Track Configuration Guide

Configuration is stored locally in `.env`; it should never be committed to Git.

## Identity and web server

- `BBS_TRACK_NAME`: public track name
- `BBS_DEFAULT_THEME`: theme folder slug
- `BBS_APP_HOST`: listen address, usually `0.0.0.0`
- `BBS_APP_PORT`: HTTP port, normally `8000`
- `BBS_PUBLIC_BASE_URL`: address other computers use
- `BBS_CORS_ORIGINS`: comma-separated allowed origins, or `*`

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

The configuration API never returns the SQL password. Leaving the password blank in the form preserves the existing value.
