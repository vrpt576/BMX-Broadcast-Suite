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

The connector ships with neutral placeholders. Each track configures its own SQL host, optional instance or TCP port, database, read-only login, password, and ODBC driver through `.env` or `/configuration`.

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

## Rider lineup lower third

- Live API: `GET /api/lineup/current`
- Demo API: `GET /api/lineup/current?demo=true`
- Live OBS overlay: `/overlay/lineup`
- Demo OBS overlay: `/overlay/lineup?demo=true`

The overlay follows the current moto selected at `/controller`, so the existing
keyboard, mouse, and direct-jump controls advance both graphics together. Round
1, 2, and 3 use RaceManager's verified `Lane_1`, `Lane_2`, and `Lane_3` fields.
Quarterfinal, semifinal, and main lane storage still requires track-side
validation; until then BBS uses the first available lane rather than leaving the
lower third blank.

## Race Director

Open `http://localhost:8000/director` for the unified live control surface. At
the track use the connector hostname, for example
`http://bmxServer01:8000/director`.

Hotkeys:

- `Space` or Right Arrow: next moto
- `Backspace` or Left Arrow: previous moto
- `[` / `]`: previous or next race round
- `L`: put the rider lineup on air
- `M`: put the current-moto bug on air
- `R`: show official results for the selected moto
- `H`: hide all BBS graphics

The selected on-air graphic is persisted in `data/current_moto.json`. Both OBS
browser sources can remain enabled in the scene; the Race Director decides
which source renders visibly. Use `/director?demo=true` away from the track to
preview the bundled historic lineup.

While positioning an overlay in OBS, append `?preview=true` to force it visible:

```text
/overlay/current?preview=true&theme=default
/overlay/lineup?preview=true&theme=default
/overlay/results?preview=true&theme=default
```

## Diagnostics

Open `/diagnostics` to check Python, pyodbc, the configured SQL Server ODBC driver, `.env`, network reachability, database authentication, and current event discovery. The same data is available as JSON at `/api/diagnostics`.

## Assisted installation

- Windows: `scripts/install-windows.ps1`
- Linux: `scripts/install-linux.sh`
- Linux service template: `scripts/bbs-connector.service.example`

### Resilient broadcast endpoints

- `GET /api/lineup/current` — live lineup or matching last-known-good cache
- `GET /api/results/current` — current official Results Roll item
- `GET /api/results/status` — server-owned Results Roll state
- `POST /api/results/start|pause|resume|previous|next|stop` — Results Roll controls
- `POST /api/breaks/show/{round_1|main}` — pause results and show a broadcast break
- `WS /ws/broadcast` — changed broadcast snapshots
- `/overlay/results` — official Round 1–3 and Main/Overall results graphic
- `/overlay/break` — shared Round 1 Break/Main Break graphic

Cached responses include `is_stale: true`, `source: "cache"`, and a warning for the operator. The OBS lineup remains visible instead of going blank.
