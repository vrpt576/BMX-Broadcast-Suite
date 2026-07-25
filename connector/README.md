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

## Manual current-moto control

The current-moto feature is deliberately independent of RaceManager. It can be
used immediately, including while the SQL database is unavailable.

Start the connector, then open:

- Operator controller: `http://localhost:8000/controller`
- OBS browser overlay: `http://localhost:8000/overlay/current`
- JSON state: `http://localhost:8000/api/current`

Keyboard controls on the operator page:

- Right arrow, up arrow, space, or Page Down: next moto
- Left arrow, down arrow, or Page Up: previous moto
- Type a moto number and press Enter: jump directly
- Optionally enter the final moto to prevent advancing past it

The selection is saved to `data/current_moto.json`, so it survives service
restarts. The controller and overlay may be opened on different computers as
long as both can reach the connector.

Manual API endpoints:

- `GET /api/current`
- `PUT /api/current`
- `POST /api/current/next`
- `POST /api/current/previous`
- `POST /api/current/reset`

Example:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/current/next
```


## Race phases

The manual broadcast state includes Round 1, Round 2, Round 3, Quarterfinals, Semifinals, and Mains. Use `[` and `]` on the controller page to move between phases, or select a phase directly. The selected phase and moto number are persisted together and shown on the OBS overlay.

## Manual class name

The controller can attach a class name such as `17-20 Expert`, `5 & Under Novice`, or `51-55 Cruiser` to the current broadcast state. Enter the class name and select **Apply**. The value is saved alongside the moto and race phase and appears on `/overlay/current`. A future RaceManager integration can populate this field automatically while retaining manual override support.
