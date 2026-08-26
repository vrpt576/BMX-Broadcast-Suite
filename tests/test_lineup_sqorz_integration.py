"""Wiring: the /api/lineup/current endpoint with Sqorz on, off, and broken."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from connector.dependencies import get_current_lineup_service
from connector.main import app
from connector.models import CurrentMotoUpdate, RacePhase
from connector.services.current_lineup_service import DEMO_MOTO, CurrentLineupService
from connector.services.current_moto_service import CurrentMotoService
from connector.services.sqorz_service import SqorzRiderTime, SqorzService


class NoDatabaseEvents:
    def current(self):  # pragma: no cover -- demo mode never calls this
        raise AssertionError("demo mode should not query RaceManager")


class NoDatabaseMotos:
    def get_moto(self, *_args, **_kwargs):  # pragma: no cover
        raise AssertionError("demo mode should not query RaceManager")


def build_service(tmp_path: Path, *, sqorz: SqorzService | None) -> CurrentLineupService:
    current = CurrentMotoService(tmp_path / "current.json")
    return CurrentLineupService(
        current,
        NoDatabaseEvents(),
        NoDatabaseMotos(),
        tmp_path / "lineup_cache.json",
        sqorz=sqorz,
    )


def test_sqorz_disabled_returns_200_with_no_times(tmp_path: Path) -> None:
    service = build_service(tmp_path, sqorz=SqorzService(enabled=False))
    app.dependency_overrides[get_current_lineup_service] = lambda: service

    response = TestClient(app).get("/api/lineup/current?demo=true")

    assert response.status_code == 200
    body = response.json()
    assert body["riders"]
    assert all(rider["time_seconds"] is None for rider in body["riders"])
    app.dependency_overrides.clear()


def test_sqorz_unreachable_returns_200_with_no_times(tmp_path: Path) -> None:
    sqorz = SqorzService(enabled=True, mode="internet", event_id="unreachable")

    def boom(url: str) -> dict:
        raise OSError("no route to host")

    sqorz._get_json = boom
    service = build_service(tmp_path, sqorz=sqorz)
    app.dependency_overrides[get_current_lineup_service] = lambda: service

    response = TestClient(app).get("/api/lineup/current?demo=true")

    assert response.status_code == 200
    body = response.json()
    assert body["riders"]
    assert all(rider["time_seconds"] is None for rider in body["riders"])
    app.dependency_overrides.clear()


def test_sqorz_confidently_matched_rider_gets_a_time(tmp_path: Path) -> None:
    # DEMO_MOTO's first rider is Nova Archer, bike 17, class "7 Intermediate".
    nova = DEMO_MOTO.riders[0]
    assert nova.first_name == "Nova" and nova.last_name == "Archer" and nova.bike_number == 17

    payload = {
        "classRanks": [
            {
                "classCode": "C1",
                "className": "7 Intermediate",
                "competitorRankSummaries": [
                    {
                        "plate": "17",
                        "firstName": "Nova",
                        "lastName": "Archer",
                        "competitorRankDetails": [
                            {"phaseCode": "M1", "phaseName": "Moto 1", "time": "41.234"}
                        ],
                    }
                ],
            }
        ]
    }
    sqorz = SqorzService(enabled=True, mode="internet", event_id="demo-event")
    sqorz._get_json = lambda url: payload

    current = CurrentMotoService(tmp_path / "current.json")
    current.set(CurrentMotoUpdate(moto_number=1, race_phase=RacePhase.ROUND_1))
    service = CurrentLineupService(
        current, NoDatabaseEvents(), NoDatabaseMotos(), tmp_path / "cache.json", sqorz=sqorz
    )
    app.dependency_overrides[get_current_lineup_service] = lambda: service

    response = TestClient(app).get("/api/lineup/current?demo=true")

    assert response.status_code == 200
    body = response.json()
    nova_row = next(r for r in body["riders"] if r["last_name"] == "Archer")
    assert nova_row["time_seconds"] == 41.234
    # Every other rider has no Sqorz data -- blank, not a guess.
    others = [r for r in body["riders"] if r["last_name"] != "Archer"]
    assert all(r["time_seconds"] is None for r in others)
    app.dependency_overrides.clear()


def test_no_sqorz_phase_name_can_ever_reach_a_phase_label_or_stage_label(tmp_path: Path) -> None:
    """Sqorz never sets round labels -- RaceManager's finalization method does."""
    row = SqorzRiderTime(
        class_code="C1",
        class_name="7 Intermediate",
        plate="17",
        first_name="Nova",
        last_name="Archer",
        transponder=None,
        phase_code="M1",
        phase_name="SQORZ-BOGUS-PHASE-NAME-SHOULD-NEVER-APPEAR",
        time_seconds=41.234,
        time_raw="41.234",
        race_position=None,
        rank=None,
    )
    sqorz = SqorzService(enabled=True, mode="internet", event_id="demo-event")
    sqorz._get_json = lambda url: {
        "classRanks": [
            {
                "classCode": row.class_code,
                "className": row.class_name,
                "competitorRankSummaries": [
                    {
                        "plate": row.plate,
                        "firstName": row.first_name,
                        "lastName": row.last_name,
                        "competitorRankDetails": [
                            {
                                "phaseCode": row.phase_code,
                                "phaseName": row.phase_name,
                                "time": row.time_raw,
                            }
                        ],
                    }
                ],
            }
        ]
    }

    current_without_sqorz = CurrentMotoService(tmp_path / "current_a.json")
    current_without_sqorz.set(CurrentMotoUpdate(moto_number=1, race_phase=RacePhase.ROUND_1))
    baseline = CurrentLineupService(
        current_without_sqorz, NoDatabaseEvents(), NoDatabaseMotos(), tmp_path / "cache_a.json", sqorz=None
    ).get(demo=True)

    current_with_sqorz = CurrentMotoService(tmp_path / "current_b.json")
    current_with_sqorz.set(CurrentMotoUpdate(moto_number=1, race_phase=RacePhase.ROUND_1))
    augmented = CurrentLineupService(
        current_with_sqorz, NoDatabaseEvents(), NoDatabaseMotos(), tmp_path / "cache_b.json", sqorz=sqorz
    ).get(demo=True)

    assert augmented.phase_label == baseline.phase_label
    assert augmented.race_phase == baseline.race_phase
    # The one confidently-matched rider does get a time from this payload...
    nova = next(r for r in augmented.riders if r.last_name == "Archer")
    assert nova.time_seconds == 41.234
    # ...but Sqorz's phase name must never leak into the response anywhere.
    dumped = augmented.model_dump_json()
    assert row.phase_name not in dumped
