"""The two guarantees 1.3.2 exists to make, each pinned by its own test
rather than assumed:

  1. test_sqorz_only_mode_never_touches_racemanager -- an operator running
     Sqorz-only mode for a full session (checking mode, picking a class,
     jumping to recent activity, stepping next/previous, reading the
     lineup) never triggers a single RaceManager query. Exercises the real
     production dependency graph end to end, not a slice of it: the real
     CurrentLineupService, wired to EventService/MotoboardService doubles
     that raise AssertionError on any call, is what the lineup route
     actually gets via dependency_overrides -- if the dispatcher (or
     anything upstream of it) ever took the RaceManager branch while mode
     is Sqorz-only, this test would fail loudly, not silently pass.

  2. test_an_existing_racemanager_install_upgrading_to_1_3_2_sees_no_behavior_change --
     most of the install base runs RaceManager only and has never heard of
     Sqorz. Loading Settings from an .env file that mentions none of
     1.3.2's new keys (exactly what an upgrading install's real .env looks
     like) must still resolve to RACEMANAGER mode and dispatch the lineup
     route to the exact same CurrentLineupService call as every release
     before 1.3.2 -- pinned by a test, not assumed.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from connector.config import Settings
from connector.dependencies import (
    get_current_lineup_service,
    get_operating_mode,
    get_sqorz_current_race_service,
    get_sqorz_service,
)
from connector.main import app
from connector.services.current_lineup_service import CurrentLineupService
from connector.services.current_moto_service import CurrentMotoService
from connector.services.lineup_dispatch import resolve_current_lineup
from connector.services.operating_mode_service import (
    ModeDecision,
    OperatingMode,
    check_racemanager_reachable,
    resolve_operating_mode,
)
from connector.services.sqorz_current_race_service import SqorzCurrentRaceService
from connector.services.sqorz_service import SqorzService

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sqorz"


class _RaceManagerTouched(AssertionError):
    """Distinct exception type so a failure here is unmistakably "Sqorz-only
    mode touched RaceManager", not confused with an ordinary test bug."""


class BoomEvents:
    def current(self):
        raise _RaceManagerTouched("EventService.current() called during a Sqorz-only session")


class BoomMotos:
    def get_moto(self, *_args, **_kwargs):
        raise _RaceManagerTouched("MotoboardService.get_moto() called during a Sqorz-only session")

    def resolve_state(self, *_args, **_kwargs):
        raise _RaceManagerTouched("MotoboardService.resolve_state() called during a Sqorz-only session")


def _real_fixture_payload() -> dict:
    return json.loads((FIXTURES / "hoosier_day3_event.json").read_text(encoding="utf-8"))


def _boom_lineup_service(tmp_path: Path) -> CurrentLineupService:
    """A real CurrentLineupService -- not a fake standing in for it -- wired
    to event/motos doubles that raise if ever called. Proves the production
    dispatch logic itself never reaches this far in Sqorz-only mode,
    rather than proving a test double was never called by code written to
    skip it."""
    return CurrentLineupService(
        CurrentMotoService(tmp_path / "current.json"),
        BoomEvents(),
        BoomMotos(),
        tmp_path / "cache.json",
    )


def test_sqorz_only_mode_never_touches_racemanager(tmp_path: Path) -> None:
    sqorz = SqorzService(enabled=True, mode="internet", event_id="e")
    sqorz._get_json = lambda url: _real_fixture_payload()
    sqorz_current_race = SqorzCurrentRaceService(tmp_path / "sqorz_current.json")

    app.dependency_overrides[get_operating_mode] = lambda: ModeDecision(
        OperatingMode.SQORZ_ONLY, "Sqorz-only mode is explicitly enabled in Configuration."
    )
    app.dependency_overrides[get_current_lineup_service] = lambda: _boom_lineup_service(tmp_path)
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz
    app.dependency_overrides[get_sqorz_current_race_service] = lambda: sqorz_current_race
    client = TestClient(app)

    try:
        # A full operator session, in the order an operator would actually
        # perform it -- not each endpoint tested in isolation.
        mode_response = client.get("/api/mode")
        assert mode_response.status_code == 200
        assert mode_response.json()["mode"] == "sqorz_only"

        state = client.get("/api/sqorz-director/state").json()
        assert state["selected"] is None
        assert any(c["class_code"] == "308" for c in state["classes"])

        selected = client.post("/api/sqorz-director/select-class/308").json()
        assert selected["selected"]["phase_code"] == "M1"

        jumped = client.post("/api/sqorz-director/jump-to-recent").json()
        assert jumped["selected"]["phase_code"] == "1F"

        back_to_start = client.post("/api/sqorz-director/previous").json()
        assert back_to_start["selected"]["phase_code"] == "2F"

        forward_again = client.post("/api/sqorz-director/next").json()
        assert forward_again["selected"]["phase_code"] == "1F"

        lineup_response = client.get("/api/lineup/current")
        assert lineup_response.status_code == 200
        lineup = lineup_response.json()
        assert lineup["source"] == "sqorz"
        assert lineup["phase_label"] == "Main"
        assert lineup["riders"]
    finally:
        app.dependency_overrides.clear()


def test_sqorz_only_mode_never_touches_racemanager_even_via_the_dispatcher_directly(tmp_path: Path) -> None:
    """Same guarantee, called as a plain function rather than over HTTP --
    catches a regression in the dispatcher itself even if a future change
    to route wiring somehow bypassed dependency_overrides."""
    sqorz = SqorzService(enabled=True, mode="internet", event_id="e")
    sqorz._get_json = lambda url: _real_fixture_payload()
    sqorz_current_race = SqorzCurrentRaceService(tmp_path / "sqorz_current.json")
    from connector.services.sqorz_navigation_service import build_class_phase_sequence

    sqorz_current_race.select(build_class_phase_sequence(sqorz.get_riders().riders, "308")[0])

    result = resolve_current_lineup(
        mode=ModeDecision(OperatingMode.SQORZ_ONLY, "reason"),
        racemanager_lineup=_boom_lineup_service(tmp_path),
        sqorz_current_race=sqorz_current_race,
        sqorz=sqorz,
    )

    assert result.source == "sqorz"


# ---------------------------------------------------------------------------
# RaceManager-only upgrade path: no behaviour change, pinned by a test
# ---------------------------------------------------------------------------


PRE_1_3_2_ENV = """
BBS_TRACK_NAME=Example Track
BBS_SQL_HOST=racemanager-pc
BBS_SQL_DATABASE=RACE
BBS_SQL_USER=bbs_connector
BBS_SQL_PASSWORD=hunter2
""".strip()


def test_an_existing_racemanager_install_upgrading_to_1_3_2_sees_no_behavior_change(
    tmp_path: Path,
) -> None:
    """That's most of the install base, and it should be pinned by a test,
    not assumed. Loads Settings from an .env file shaped exactly like a
    pre-1.3.2 install's real file -- it mentions none of 1.3.2's new keys
    (BBS_SQORZ_*, BBS_FORCE_SQORZ_ONLY_MODE) at all, which is exactly what
    upgrading in place looks like, not a hand-picked "off" value for each
    new setting."""
    env_file = tmp_path / ".env"
    env_file.write_text(PRE_1_3_2_ENV + "\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.sqorz_enabled is False
    assert settings.force_sqorz_only_mode is False

    decision = resolve_operating_mode(
        racemanager_reachable=True,  # the install's whole reason to exist
        sqorz_enabled=settings.sqorz_enabled,
        force_sqorz_only=settings.force_sqorz_only_mode,
    )

    assert decision.mode is OperatingMode.RACEMANAGER
    assert decision.reason == "Connected to RaceManager."


def test_upgraded_install_dispatches_the_lineup_route_exactly_as_before(tmp_path: Path) -> None:
    """The behavioural half of "no change": with mode resolved to
    RACEMANAGER, the lineup dispatcher must call the real RaceManager
    lineup service -- not a Sqorz branch that happens to also produce
    a plausible-looking result."""
    calls: list[bool] = []

    class RecordingLineupService:
        def get(self, *, demo, motoboard_id):
            calls.append(True)
            from connector.models import CurrentLineup, RacePhase

            return CurrentLineup(
                moto_number=3, race_phase=RacePhase.ROUND_2, class_name="17-20 Expert", riders=[], source="racemanager"
            )

    result = resolve_current_lineup(
        mode=ModeDecision(OperatingMode.RACEMANAGER, "Connected to RaceManager."),
        racemanager_lineup=RecordingLineupService(),
        sqorz_current_race=SqorzCurrentRaceService(tmp_path / "sqorz.json"),
        sqorz=SqorzService(enabled=False),
    )

    assert calls == [True]
    assert result.source == "racemanager"
    assert result.class_name == "17-20 Expert"


# ---------------------------------------------------------------------------
# Results boundary: per the approved control-mapping table, Sqorz-only mode
# hides the Results Roll cluster entirely and disables "Show current
# results" -- there is no Sqorz-only results feature in 1.3.2 at all, so
# these two services must stay completely oblivious to Sqorz's existence,
# not just unused by it.
# ---------------------------------------------------------------------------


def test_results_services_never_mention_sqorz() -> None:
    root = Path(__file__).resolve().parents[1] / "connector" / "services"
    for name in ("current_results_service.py", "results_roll_service.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "sqorz" not in source.lower(), f"{name} must stay completely unaware of Sqorz"


def test_check_racemanager_reachable_against_a_database_shaped_like_the_real_one(tmp_path: Path) -> None:
    """Belt-and-suspenders on the reachability probe itself, using
    RaceManagerDatabase's real interface shape (fetch_one), not a
    hand-rolled stand-in with a different method name that could silently
    drift from the real class."""

    class WorkingDatabase:
        def fetch_one(self, query: str):
            return {"ok": 1}

    assert check_racemanager_reachable(WorkingDatabase()) is True
