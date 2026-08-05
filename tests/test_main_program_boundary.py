"""Event-level Main-program boundary regression coverage."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from connector.models import (
    MainProgramBoundaryConfidence,
    MainProgramBoundarySource,
    RacePhase,
)
from connector.services.motoboard_service import MotoboardService
from connector.services.phase_classification_service import (
    PhaseClassificationOverrideStore,
)
from connector.services.race_slot_service import RaceSlotService
from tests.test_round_aware_program import (
    BOARD_ID,
    FakeDatabase,
    next_main_rows,
    total_points_rows,
)


OTHER_BOARD_ID = UUID("aa55aa55-aa55-aa55-aa55-aa55aa55aa55")


def _remap_rows(
    rows: list[dict[str, object]],
    *,
    key: str,
    moto_number: int,
) -> list[dict[str, object]]:
    """Clone a structural class fixture with stable, isolated identities."""

    def mapped(kind: str, value: object) -> UUID:
        return uuid5(NAMESPACE_URL, f"bbs-main-boundary:{key}:{kind}:{value}")

    cloned: list[dict[str, object]] = []
    for item in rows:
        cloned.append(
            {
                **item,
                "class_id": mapped("class", item["class_id"]),
                "class_name": f"{key} class",
                "class_name_short": key,
                "round_id": mapped("round", item["round_id"]),
                "motogroup_id": mapped("group", item["motogroup_id"]),
                "motogroup_rider_id": mapped(
                    "motogroup-rider", item["motogroup_rider_id"]
                ),
                "rider_id": mapped("rider", item["rider_id"]),
                "moto_number": moto_number,
            }
        )
    return cloned


def _points(key: str, moto_number: int) -> list[dict[str, object]]:
    return _remap_rows(total_points_rows(), key=key, moto_number=moto_number)


def _transfer(key: str, moto_number: int) -> list[dict[str, object]]:
    return _remap_rows(next_main_rows(), key=key, moto_number=moto_number)


def _service(
    tmp_path: Path,
    rows: list[dict[str, object]],
    *,
    start_moto: int | None,
) -> MotoboardService:
    service = MotoboardService(
        FakeDatabase(rows),
        phase_override_file=tmp_path / "race-phase-overrides.json",
    )
    if start_moto is not None:
        service.phase_overrides.set_main_program_start(BOARD_ID, start_moto)
    return service


def _numbers(service: MotoboardService, phase: RacePhase) -> list[int]:
    return [
        slot.moto_number
        for slot in RaceSlotService(service).catalog(BOARD_ID, phase)
    ]


def test_total_points_only_event_can_have_a_main_program(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        _points("points-only-a", 40) + _points("points-only-b", 43),
        start_moto=40,
    )

    assert _numbers(service, RacePhase.MAIN) == [40, 43]
    assert _numbers(service, RacePhase.ROUND_3) == []
    boundary = service.get_main_program_boundary(BOARD_ID)
    assert boundary.start_moto == 40
    assert boundary.suggested_start_moto is None


def test_main_program_can_begin_with_total_points_before_transfer(
    tmp_path: Path,
) -> None:
    service = _service(
        tmp_path,
        _points("opening-points", 28) + _transfer("later-transfer", 29),
        start_moto=28,
    )

    assert _numbers(service, RacePhase.MAIN) == [28, 29]


def test_main_program_can_end_with_total_points_after_transfer(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        _transfer("opening-transfer", 31) + _points("ending-points", 32),
        start_moto=31,
    )

    assert _numbers(service, RacePhase.MAIN) == [31, 32]


def test_main_program_can_interleave_scoring_methods_and_gaps(tmp_path: Path) -> None:
    rows = (
        _points("points-a", 28)
        + _transfer("transfer-a", 29)
        + _points("points-b", 32)
        + _transfer("transfer-b", 35)
    )
    service = _service(tmp_path, rows, start_moto=28)

    assert _numbers(service, RacePhase.MAIN) == [28, 29, 32, 35]


def test_true_round_three_immediately_before_main_boundary(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        _points("round-three", 27)
        + _points("main-points", 28)
        + _transfer("main-transfer", 29),
        start_moto=28,
    )

    assert _numbers(service, RacePhase.ROUND_3) == [27]
    assert _numbers(service, RacePhase.MAIN) == [28, 29]


def test_transfer_evidence_is_only_a_suggestion_until_operator_override(
    tmp_path: Path,
) -> None:
    rows = _points("ambiguous-points", 28) + _transfer("transfer", 29)
    service = _service(tmp_path, rows, start_moto=None)

    boundary = service.get_main_program_boundary(BOARD_ID)
    assert boundary.start_moto is None
    assert boundary.source == MainProgramBoundarySource.UNRESOLVED
    assert boundary.confidence == MainProgramBoundaryConfidence.LOW
    assert boundary.suggested_start_moto == 29
    assert _numbers(service, RacePhase.ROUND_3) == [28]
    assert _numbers(service, RacePhase.MAIN) == [29]

    service.set_main_program_boundary(BOARD_ID, 28)

    assert _numbers(service, RacePhase.MAIN) == [28, 29]


def test_event_boundary_persists_resets_and_is_isolated(tmp_path: Path) -> None:
    path = tmp_path / "race-phase-overrides.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "events": {
                    str(BOARD_ID): {
                        "classes": {"fixture-class": "accumulated_points"}
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    store = PhaseClassificationOverrideStore(path)

    store.set_main_program_start(BOARD_ID, 28)

    reloaded = PhaseClassificationOverrideStore(path)
    assert reloaded.get_main_program_start(BOARD_ID) == 28
    assert reloaded.get_main_program_start(OTHER_BOARD_ID) is None

    reloaded.set_main_program_start(OTHER_BOARD_ID, 50)
    reloaded.set_main_program_start(BOARD_ID, None)

    final = PhaseClassificationOverrideStore(path)
    assert final.get_main_program_start(BOARD_ID) is None
    assert final.get_main_program_start(OTHER_BOARD_ID) == 50
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["events"][str(BOARD_ID)]["classes"] == {
        "fixture-class": "accumulated_points"
    }
