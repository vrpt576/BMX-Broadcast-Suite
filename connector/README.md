# BBS Connector

The BBS Connector is a read-only FastAPI service that translates USABMX
RaceManager's SQL Server schema into stable JSON for the broadcast engine and
OBS overlays.

## API

- `GET /health`
- `GET /api/event/current`
- `GET /api/motos`
- `GET /api/motos/{moto_number}`

Interactive API documentation is available at `/docs` while the service runs.

## Local development

Python 3.11+ and Microsoft ODBC Driver 18 for SQL Server are required.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r connector\requirements-dev.txt
Copy-Item connector\.env.example .env
# Edit .env and provide BBS_SQL_PASSWORD.
uvicorn connector.main:app --reload
```

The connector defaults to the known RaceManager layout:

- SQL host `192.168.2.52`
- instance `USABMX`
- database `RACE`
- read-only login `bbs_connector`

Credentials are never committed. The `.env` file is ignored by Git.

## Moto state

The API reads the `Round_Type_ID = 123` branch, which RaceManager uses for
staging/lane assignments and clipboard-entered results. Moto state is derived as:

- `staged`: no rider has `Finish_1`
- `scoring`: some riders have `Finish_1`
- `scored`: every rider has `Finish_1`

The maximum rider `Date_Maintenance` value is exposed as the moto update time,
so clients can detect first entry and later corrections.

## Tests

```powershell
pytest
```

Unit tests use a fake database and do not require RaceManager or SQL Server.

## Docker

From the repository root:

```bash
docker build -f connector/Dockerfile -t bbs-connector .
docker run --rm -p 8000:8000 --env-file .env bbs-connector
```
