from pathlib import Path

import pytest

from connector.models import CurrentMotoUpdate
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
