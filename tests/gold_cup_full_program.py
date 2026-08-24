"""Shared loader for the privacy-safe full 2026-08-01 Gold Cup program export.

The fixture is a structural snapshot of every motogroup on the Gold Cup /
State Race motoboard, taken read-only from RaceManager.  Rider identities are
replaced with stable non-reversible integer keys, so the qualifier/final rider
set comparisons that drive phase classification behave exactly as they do
live while no personal data enters the repository.  See
``docs/gold-cup-full-program-fixture.md`` for the export query.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from connector.models import Event
from connector.services.current_moto_service import CurrentMotoService
from connector.services.motoboard_service import MotoboardService
from connector.services.race_program_service import RaceProgramService
from tests.test_round_aware_program import FakeDatabase

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "gold_cup_2026_08_01_full_program.json"
)

# The operator confirmed this boundary for the historic event: the Main
# program block runs from displayed moto 28.
OPERATOR_MAIN_PROGRAM_START = 28


def fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def board_id() -> UUID:
    return UUID(str(fixture()["source"]["motoboard_id"]))


def _anonymous_rider_id(key: int) -> UUID:
    return UUID(f"00000000-0000-0000-0000-{key % 10**12:012d}")


def full_program_rows(payload: dict[str, object] | None = None) -> list[dict[str, object]]:
    """Rebuild RaceManager's rider rows from the structural export."""
    payload = payload or fixture()
    classes = {item["class_id"]: item for item in payload["classes"]}
    rows: list[dict[str, object]] = []
    for group in payload["motogroups"]:
        entry = classes[group["class_id"]]
        for rider in group["riders"]:
            rows.append(
                {
                    "moto_number": group["moto_number"],
                    "motogroup_number": group["motogroup_number"],
                    "motogroup_id": UUID(group["motogroup_id"]),
                    "class_id": UUID(group["class_id"]),
                    "class_name": entry["class_name"],
                    "class_name_short": entry["class_name_short"],
                    "round_id": UUID(group["round_id"]),
                    "round_type_id": group["round_type_id"],
                    "round_moto_number_first": group["round_moto_number_first"],
                    "round_moto_number_last": group["round_moto_number_last"],
                    "round_motogroup_count": group["round_motogroup_count"],
                    "motogroup_rider_id": _anonymous_rider_id(
                        rider["rider_key"] + group["round_type_id"] * 10**9
                    ),
                    "rider_order": rider["rider_order"],
                    "lane_1": rider["lane_1"],
                    "lane_2": rider["lane_2"],
                    "lane_3": rider["lane_3"],
                    "finish_1": rider["finish_1"],
                    "finish_2": rider["finish_2"],
                    "finish_3": rider["finish_3"],
                    "did_not_race": False,
                    "updated_at": datetime(2026, 8, 1, 12, 0, 0),
                    "rider_id": _anonymous_rider_id(rider["rider_key"]),
                    "bike_number": rider["rider_key"] % 1000,
                    "first_name": "Rider",
                    "last_name": "Anonymised",
                    "nickname": None,
                    "proficiency": "I",
                    "sponsor": None,
                }
            )
    return rows


class PinnedGoldCupEvents:
    """The historic event stays pinned; nothing may fall back to "live"."""

    def __init__(self, motoboard_id: UUID) -> None:
        self.motoboard_id = motoboard_id

    def current(self) -> Event:
        raise AssertionError("The historic Gold Cup event must remain pinned")

    def by_motoboard(self, motoboard_id: UUID) -> Event:
        assert motoboard_id == self.motoboard_id
        payload = fixture()["source"]
        return Event(
            event_id=UUID("11111111-1111-1111-1111-111111111111"),
            event_name=str(payload["event_name"]),
            date_begin=str(payload["event_date"]),
            race_id=UUID("22222222-2222-2222-2222-222222222222"),
            race_description=str(payload["race_description"]),
            motoboard_id=motoboard_id,
            total_motos=int(payload["total_motos"]),
            total_riders=int(payload["total_riders"]),
        )


def motoboards(
    tmp_path: Path,
    *,
    main_program_start: int | None = OPERATOR_MAIN_PROGRAM_START,
) -> MotoboardService:
    service = MotoboardService(
        FakeDatabase(full_program_rows()),
        phase_override_file=tmp_path / "race-phase-overrides.json",
    )
    if main_program_start is not None:
        service.phase_overrides.set_main_program_start(board_id(), main_program_start)
    return service


def services(
    tmp_path: Path,
    *,
    main_program_start: int | None = OPERATOR_MAIN_PROGRAM_START,
) -> tuple[UUID, MotoboardService, CurrentMotoService, RaceProgramService]:
    board = board_id()
    boards = motoboards(tmp_path, main_program_start=main_program_start)
    current = CurrentMotoService(tmp_path / "current.json")
    programs = RaceProgramService(current, PinnedGoldCupEvents(board), boards)
    return board, boards, current, programs
