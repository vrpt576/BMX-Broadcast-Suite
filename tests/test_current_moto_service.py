from pathlib import Path

import pytest

from connector.models import CurrentMotoUpdate, RacePhase
from connector.services.current_moto_service import (
    CurrentMotoService,
    CurrentMotoValidationError,
)


def service(tmp_path: Path) -> CurrentMotoService:
    return CurrentMotoService(tmp_path / "current.json")


def test_defaults_to_moto_one(tmp_path: Path) -> None:
    state = service(tmp_path).get()
    assert state.moto_number == 1
    assert state.maximum_moto is None
    assert state.race_phase == RacePhase.ROUND_1


def test_next_previous_and_persistence(tmp_path: Path) -> None:
    first = service(tmp_path)
    assert first.next().moto_number == 2
    assert first.next().moto_number == 3
    assert first.previous().moto_number == 2

    restarted = service(tmp_path)
    assert restarted.get().moto_number == 2


def test_respects_maximum_moto(tmp_path: Path) -> None:
    current = service(tmp_path)
    current.set(CurrentMotoUpdate(moto_number=3, maximum_moto=3))
    assert current.next().moto_number == 3


def test_rejects_out_of_range_moto(tmp_path: Path) -> None:
    current = service(tmp_path)
    with pytest.raises(CurrentMotoValidationError):
        current.set(CurrentMotoUpdate(moto_number=5, maximum_moto=4))


def test_round_progression_and_persistence(tmp_path: Path) -> None:
    current = service(tmp_path)
    assert current.next_phase().race_phase == RacePhase.ROUND_2
    assert current.next_phase().race_phase == RacePhase.ROUND_3
    assert current.next_phase().race_phase == RacePhase.QUARTERFINAL
    assert current.next_phase().race_phase == RacePhase.SEMIFINAL
    assert current.next_phase().race_phase == RacePhase.MAIN
    assert current.next_phase().race_phase == RacePhase.MAIN

    restarted = service(tmp_path)
    assert restarted.get().race_phase == RacePhase.MAIN
    assert restarted.previous_phase().race_phase == RacePhase.SEMIFINAL


def test_can_set_phase_without_changing_moto(tmp_path: Path) -> None:
    current = service(tmp_path)
    state = current.set(CurrentMotoUpdate(moto_number=12, race_phase=RacePhase.SEMIFINAL))
    assert state.moto_number == 12
    assert state.race_phase == RacePhase.SEMIFINAL
