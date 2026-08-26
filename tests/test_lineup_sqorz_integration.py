"""Wiring: the /api/lineup/current endpoint with Sqorz on, off, and broken."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from connector.dependencies import get_current_lineup_service
from connector.main import app
from connector.models import CurrentLineup, CurrentMotoUpdate, LineupRider, RacePhase
from connector.services.current_lineup_service import CurrentLineupService
from connector.services.current_moto_service import CurrentMotoService
from connector.services.sqorz_class_alias_service import SqorzClassAliasStore
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


def _matching_nova_payload() -> dict:
    return {
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


def test_sqorz_confidently_matched_rider_gets_a_time_for_a_real_lineup(tmp_path: Path) -> None:
    """A non-demo (source="racemanager") lineup is exactly where a
    confidently-matched Sqorz time is supposed to show up."""
    sqorz = SqorzService(enabled=True, mode="internet", event_id="real-event")
    sqorz._get_json = lambda url: _matching_nova_payload()
    service = CurrentLineupService(
        CurrentMotoService(tmp_path / "current.json"),
        NoDatabaseEvents(),
        NoDatabaseMotos(),
        tmp_path / "cache.json",
        sqorz=sqorz,
    )

    lineup = CurrentLineup(
        moto_number=1,
        race_phase=RacePhase.ROUND_1,
        class_name="7 Intermediate",
        riders=[
            LineupRider(bike_number=17, first_name="Nova", last_name="Archer"),
            LineupRider(bike_number=99, first_name="Someone", last_name="Else"),
        ],
        source="racemanager",
    )

    result = service._augment_with_sqorz(lineup)

    nova_row = next(r for r in result.riders if r.last_name == "Archer")
    assert nova_row.time_seconds == 41.234
    # Every other rider has no Sqorz data -- blank, not a guess.
    others = [r for r in result.riders if r.last_name != "Archer"]
    assert all(r.time_seconds is None for r in others)


def test_demo_lineup_never_receives_a_sqorz_time_even_with_a_perfect_match(
    tmp_path: Path,
) -> None:
    """Structural boundary: a demo-sourced lineup must be incapable of a
    Sqorz time no matter how well it would match -- this is not left to the
    confidence tiers. Uses a payload engineered to match Nova Archer exactly
    (plate + last name + class), the strongest possible match, to prove the
    "demo" source check really is what's blocking it."""
    sqorz = SqorzService(enabled=True, mode="internet", event_id="demo-event")
    sqorz._get_json = lambda url: _matching_nova_payload()
    service = CurrentLineupService(
        CurrentMotoService(tmp_path / "current.json"),
        NoDatabaseEvents(),
        NoDatabaseMotos(),
        tmp_path / "cache.json",
        sqorz=sqorz,
    )

    lineup = CurrentLineup(
        moto_number=1,
        race_phase=RacePhase.ROUND_1,
        class_name="7 Intermediate",
        riders=[LineupRider(bike_number=17, first_name="Nova", last_name="Archer")],
        source="demo",
    )

    result = service._augment_with_sqorz(lineup)

    assert result.riders[0].time_seconds is None
    assert result is lineup  # untouched -- returned before any matching ran


def test_the_demo_api_endpoint_never_returns_a_sqorz_time(tmp_path: Path) -> None:
    """End-to-end: /api/lineup/current?demo=true, with a Sqorz payload
    engineered to match a real demo rider exactly, still returns no times."""
    sqorz = SqorzService(enabled=True, mode="internet", event_id="demo-event")
    sqorz._get_json = lambda url: _matching_nova_payload()
    current = CurrentMotoService(tmp_path / "current.json")
    current.set(CurrentMotoUpdate(moto_number=1, race_phase=RacePhase.ROUND_1))
    service = CurrentLineupService(
        current, NoDatabaseEvents(), NoDatabaseMotos(), tmp_path / "cache.json", sqorz=sqorz
    )
    app.dependency_overrides[get_current_lineup_service] = lambda: service

    response = TestClient(app).get("/api/lineup/current?demo=true")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "demo"
    assert all(r["time_seconds"] is None for r in body["riders"])
    app.dependency_overrides.clear()


def test_no_sqorz_phase_name_can_ever_reach_a_phase_label_or_stage_label(tmp_path: Path) -> None:
    """Sqorz never sets round labels -- RaceManager's finalization method
    does. The lineup overlay's round header (#round) shows BBS's own
    phase_label only; the Sqorz phaseCode used for times may appear ONLY in
    the time column's own caption (sqorz_phase_code, e.g. "M1") -- never
    Sqorz's own phaseName wording ("Moto 1"), and never phase_label."""
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
    service = CurrentLineupService(
        CurrentMotoService(tmp_path / "current.json"),
        NoDatabaseEvents(),
        NoDatabaseMotos(),
        tmp_path / "cache.json",
        sqorz=sqorz,
    )

    baseline = CurrentLineup(
        moto_number=1,
        race_phase=RacePhase.ROUND_1,
        phase_label="Round 1",
        class_name="7 Intermediate",
        riders=[LineupRider(bike_number=17, first_name="Nova", last_name="Archer")],
        source="racemanager",
    )
    augmented = service._augment_with_sqorz(baseline)

    assert augmented.phase_label == baseline.phase_label == "Round 1"
    assert augmented.race_phase == baseline.race_phase
    # The one confidently-matched rider does get a time from this payload...
    nova = next(r for r in augmented.riders if r.last_name == "Archer")
    assert nova.time_seconds == 41.234
    # ...the BBS-mapped Sqorz phase CODE is exposed for the column caption...
    assert augmented.sqorz_phase_code == "M1"
    # ...but Sqorz's own phase NAME wording must never leak into the
    # response anywhere, and phase_label must stay exactly BBS's own text.
    dumped = augmented.model_dump_json()
    assert row.phase_name not in dumped
    assert "Round 1" in dumped


def test_the_served_page_reads_the_sqorz_caption_from_the_time_column_never_the_round_header() -> None:
    from connector.routes.lineup import LINEUP_OVERLAY_HTML

    assert "sqorz_phase_code" in LINEUP_OVERLAY_HTML
    round_assignment = next(
        line
        for line in LINEUP_OVERLAY_HTML.splitlines()
        if "#round" in line and "textContent" in line
    )
    assert "sqorz_phase_code" not in round_assignment
    time_label_assignment = next(
        line
        for line in LINEUP_OVERLAY_HTML.splitlines()
        if "#time-label" in line and "textContent" in line
    )
    assert "sqorz_phase_code" in time_label_assignment


def test_an_alias_saved_between_two_polls_takes_effect_immediately(tmp_path: Path) -> None:
    """No BBS restart, no cache -- the alias store re-reads its file on
    every lookup, so a save takes effect on the very next lineup poll."""
    payload = {
        "classRanks": [
            {
                "classCode": "C1",
                "className": "Sqorz Calls It Something Else",
                "competitorRankSummaries": [
                    {
                        # Different name than the BBS rider on purpose -- this
                        # must go through the bare-plate path (strong/weak),
                        # not "exact", to actually exercise class scoping.
                        "plate": "17",
                        "firstName": "Someone",
                        "lastName": "Unrelated",
                        "competitorRankDetails": [{"phaseCode": "M1", "time": "41.234"}],
                    }
                ],
            }
        ]
    }
    sqorz = SqorzService(enabled=True, mode="internet", event_id="e")
    sqorz._get_json = lambda url: payload
    aliases = SqorzClassAliasStore(tmp_path / "aliases.json")
    service = CurrentLineupService(
        CurrentMotoService(tmp_path / "current.json"),
        NoDatabaseEvents(),
        NoDatabaseMotos(),
        tmp_path / "cache.json",
        sqorz=sqorz,
        sqorz_class_aliases=aliases,
    )
    lineup = CurrentLineup(
        moto_number=1,
        race_phase=RacePhase.ROUND_1,
        class_name="RaceManager's Own Class Name",
        riders=[LineupRider(bike_number=17, first_name="Nova", last_name="Archer")],
        source="racemanager",
    )

    before = service._augment_with_sqorz(lineup)
    assert before.riders[0].time_seconds is None  # class names don't line up yet

    aliases.set_alias("RaceManager's Own Class Name", "Sqorz Calls It Something Else")

    after = service._augment_with_sqorz(lineup)
    assert after.riders[0].time_seconds == 41.234  # picked up without restarting anything
