from pathlib import Path

from connector.models import CurrentMotoUpdate, RacePhase
from connector.services.current_lineup_service import CurrentLineupService, DEMO_MOTO
from connector.services.current_moto_service import CurrentMotoService


class UnusedService:
    def current(self):  # pragma: no cover
        raise AssertionError("demo mode should not query RaceManager")

    def get_moto(self, *_args, **_kwargs):  # pragma: no cover
        raise AssertionError("demo mode should not query RaceManager")


def test_demo_lineup_uses_verified_historic_data(tmp_path: Path) -> None:
    current = CurrentMotoService(tmp_path / "current.json")
    service = CurrentLineupService(current, UnusedService(), UnusedService())

    lineup = service.get(demo=True)

    assert lineup.class_name == "7 Intermediate"
    assert [rider.gate for rider in lineup.riders] == [2, 4, 6, 8]
    assert [rider.bike_number for rider in lineup.riders] == [93, 85, 72, 4]
    assert lineup.riders[0].first_name == "Dylan"
    assert lineup.source == "demo"


def test_round_two_selects_lane_two(tmp_path: Path) -> None:
    current = CurrentMotoService(tmp_path / "current.json")
    current.set(CurrentMotoUpdate(moto_number=1, race_phase=RacePhase.ROUND_2))
    demo = DEMO_MOTO.model_copy(deep=True)
    demo.riders[0].lane_2 = 7

    lineup = CurrentLineupService._build(current.get(), demo, source="test")

    dylan = next(rider for rider in lineup.riders if rider.last_name == "Allen")
    assert dylan.gate == 7


def test_elimination_round_falls_back_to_available_gate(tmp_path: Path) -> None:
    current = CurrentMotoService(tmp_path / "current.json")
    current.set(CurrentMotoUpdate(moto_number=1, race_phase=RacePhase.MAIN))

    lineup = CurrentLineupService._build(current.get(), DEMO_MOTO, source="test")

    assert [rider.gate for rider in lineup.riders] == [2, 4, 6, 8]
