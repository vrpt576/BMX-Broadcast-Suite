from pathlib import Path
from uuid import UUID

from connector.models import CurrentMotoUpdate, RacePhase
from connector.services.current_lineup_service import CurrentLineupService, DEMO_MOTO
from connector.services.current_moto_service import CurrentMotoService


class UnusedService:
    def current(self):  # pragma: no cover
        raise AssertionError("demo mode should not query RaceManager")

    def get_moto(self, *_args, **_kwargs):  # pragma: no cover
        raise AssertionError("demo mode should not query RaceManager")


def test_demo_lineup_uses_coherent_fictional_data(tmp_path: Path) -> None:
    current = CurrentMotoService(tmp_path / "current.json")
    service = CurrentLineupService(current, UnusedService(), UnusedService())

    lineup = service.get(demo=True)

    assert lineup.class_name == "7 Intermediate"
    assert [rider.gate for rider in lineup.riders] == [2, 4, 6, 8]
    assert [rider.bike_number for rider in lineup.riders] == [17, 28, 46, 73]
    assert [rider.age for rider in lineup.riders] == [7, 7, 7, 7]
    assert all(rider.home_track for rider in lineup.riders)
    assert lineup.riders[0].first_name == "Nova"
    assert lineup.source == "demo"


def test_round_two_selects_lane_two(tmp_path: Path) -> None:
    current = CurrentMotoService(tmp_path / "current.json")
    current.set(CurrentMotoUpdate(moto_number=1, race_phase=RacePhase.ROUND_2))
    demo = DEMO_MOTO.model_copy(deep=True)
    demo.riders[0].lane_2 = 7

    lineup = CurrentLineupService._build(current.get(), demo, source="test")

    nova = next(rider for rider in lineup.riders if rider.last_name == "Archer")
    assert nova.gate == 7


def test_elimination_round_falls_back_to_available_gate(tmp_path: Path) -> None:
    current = CurrentMotoService(tmp_path / "current.json")
    current.set(CurrentMotoUpdate(moto_number=1, race_phase=RacePhase.MAIN))

    lineup = CurrentLineupService._build(current.get(), DEMO_MOTO, source="test")

    assert [rider.gate for rider in lineup.riders] == [2, 4, 6, 8]


def test_legacy_context_labels_a_third_moto_moto_three_not_round_three(
    tmp_path: Path,
) -> None:
    """Adapters without resolve_state must not synthesize a banned label."""
    current = CurrentMotoService(tmp_path / "current.json")
    current.set(CurrentMotoUpdate(moto_number=1, race_phase=RacePhase.ROUND_3))

    stage, _program = CurrentLineupService._legacy_context(
        current.get(),
        DEMO_MOTO,
        UUID("00000000-0000-0000-0000-000000000099"),
    )

    assert stage.label == "Moto 3"


def test_lineup_maps_verified_age_and_home_track(tmp_path: Path) -> None:
    current = CurrentMotoService(tmp_path / "current.json")
    demo = DEMO_MOTO.model_copy(deep=True)
    demo.riders[0].age = 7
    demo.riders[0].home_track = "Bend BMX"

    lineup = CurrentLineupService._build(current.get(), demo, source="test")

    assert lineup.riders[0].age == 7
    assert lineup.riders[0].home_track == "Bend BMX"
