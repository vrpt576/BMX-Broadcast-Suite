"""File-backed operator selection for Sqorz-only mode -- pure storage, no
catalog or stepping logic (that lives in sqorz_navigation_service.py and,
one layer up, connector/routes/sqorz_director.py). Mirrors
test_current_moto_service.py's coverage of the same persistence pattern:
defaults, round-tripping through a fresh process, and tolerance of a
missing or corrupt state file.
"""

from __future__ import annotations

from pathlib import Path

from connector.services.sqorz_current_race_service import (
    SqorzCurrentRace,
    SqorzCurrentRaceService,
)
from connector.services.sqorz_navigation_service import SqorzRaceSlot


def service(tmp_path: Path) -> SqorzCurrentRaceService:
    return SqorzCurrentRaceService(tmp_path / "sqorz_current_race.json")


def slot(**overrides) -> SqorzRaceSlot:
    defaults = dict(
        class_code="308",
        class_name="12 Expert",
        phase_code="M1",
        phase_name="Moto 1",
        has_recorded_time=True,
    )
    defaults.update(overrides)
    return SqorzRaceSlot(**defaults)


def test_nothing_selected_yet_returns_none_not_a_default(tmp_path: Path) -> None:
    """Unlike CurrentMotoService (which defaults to Moto 1 -- a real
    RaceManager schedule assumption), Sqorz-only mode has no fixed schedule
    to imply a starting point."""
    assert service(tmp_path).get() is None


def test_select_persists_the_slots_own_fields(tmp_path: Path) -> None:
    svc = service(tmp_path)
    result = svc.select(slot())

    assert isinstance(result, SqorzCurrentRace)
    assert result.class_code == "308"
    assert result.class_name == "12 Expert"
    assert result.phase_code == "M1"
    assert result.phase_name == "Moto 1"
    assert result.updated_at  # non-empty ISO timestamp


def test_selection_survives_a_fresh_service_instance(tmp_path: Path) -> None:
    first = service(tmp_path)
    first.select(slot(phase_code="2F", phase_name="Semi Final"))

    restarted = service(tmp_path)
    current = restarted.get()

    assert current is not None
    assert current.phase_code == "2F"
    assert current.phase_name == "Semi Final"


def test_a_later_select_overwrites_the_earlier_one(tmp_path: Path) -> None:
    svc = service(tmp_path)
    svc.select(slot(phase_code="M1"))
    svc.select(slot(phase_code="M2"))

    assert svc.get().phase_code == "M2"


def test_reset_clears_the_selection(tmp_path: Path) -> None:
    svc = service(tmp_path)
    svc.select(slot())
    assert svc.get() is not None

    svc.reset()

    assert svc.get() is None


def test_reset_on_an_already_empty_state_does_not_raise(tmp_path: Path) -> None:
    service(tmp_path).reset()  # must not raise


def test_a_corrupt_state_file_is_treated_as_nothing_selected(tmp_path: Path) -> None:
    state_file = tmp_path / "sqorz_current_race.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("{not valid json", encoding="utf-8")

    svc = SqorzCurrentRaceService(state_file)

    assert svc.get() is None


def test_a_state_file_missing_a_required_field_is_treated_as_nothing_selected(tmp_path: Path) -> None:
    state_file = tmp_path / "sqorz_current_race.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text('{"class_code": "308"}', encoding="utf-8")

    svc = SqorzCurrentRaceService(state_file)

    assert svc.get() is None


def test_write_is_atomic_no_tmp_file_left_behind(tmp_path: Path) -> None:
    svc = service(tmp_path)
    svc.select(slot())

    assert not (tmp_path / "sqorz_current_race.json.tmp").exists()
    assert (tmp_path / "sqorz_current_race.json").exists()
