"""The one named exception to Sqorz-only mode's RaceManager isolation:
GET /api/lineup/current must serve the right lineup regardless of mode,
since OBS points at one fixed Browser Source URL. Kept to this one small
function -- these tests exercise it directly (pure dispatch logic) and
through the real route (test_sqorz_director_route.py covers the fuller
end-to-end Sqorz-only path once the Director routes exist).
"""

from __future__ import annotations

from pathlib import Path

from connector.services.current_lineup_service import CurrentLineupService
from connector.services.current_moto_service import CurrentMotoService
from connector.services.lineup_dispatch import resolve_current_lineup
from connector.services.operating_mode_service import ModeDecision, OperatingMode
from connector.services.sqorz_current_race_service import SqorzCurrentRaceService
from connector.services.sqorz_navigation_service import SqorzRaceSlot
from connector.services.sqorz_service import SqorzService


class _BoomEvents:
    def current(self):
        raise AssertionError("Sqorz-only mode must never query RaceManager")


class _BoomMotos:
    def get_moto(self, *_args, **_kwargs):
        raise AssertionError("Sqorz-only mode must never query RaceManager")

    def resolve_state(self, *_args, **_kwargs):
        raise AssertionError("Sqorz-only mode must never query RaceManager")


def racemanager_lineup_service(tmp_path: Path) -> CurrentLineupService:
    """A RaceManager lineup service wired to fail loudly if it's ever
    actually called -- used in Sqorz-only-mode tests to prove the
    dispatcher really branched away from it, not just that the result
    happened to look right."""
    return CurrentLineupService(
        CurrentMotoService(tmp_path / "current.json"),
        _BoomEvents(),
        _BoomMotos(),
        tmp_path / "cache.json",
    )


def test_racemanager_mode_dispatches_straight_to_the_racemanager_service(tmp_path: Path) -> None:
    calls: list[dict] = []

    class RecordingService:
        def get(self, *, demo, motoboard_id):
            calls.append({"demo": demo, "motoboard_id": motoboard_id})
            from connector.models import CurrentLineup, RacePhase

            return CurrentLineup(moto_number=1, race_phase=RacePhase.ROUND_1, class_name="X", riders=[], source="racemanager")

    result = resolve_current_lineup(
        mode=ModeDecision(OperatingMode.RACEMANAGER, "Connected to RaceManager."),
        racemanager_lineup=RecordingService(),
        sqorz_current_race=SqorzCurrentRaceService(tmp_path / "sqorz.json"),
        sqorz=SqorzService(enabled=False),
        demo=True,
    )

    assert result.source == "racemanager"
    assert calls == [{"demo": True, "motoboard_id": None}]


def test_unavailable_mode_also_dispatches_to_the_racemanager_service(tmp_path: Path) -> None:
    """UNAVAILABLE (neither RaceManager nor Sqorz configured) is not
    SQORZ_ONLY -- it must fall through to the same path as RACEMANAGER
    mode (today's existing "fix your setup" behaviour), not a third
    branch."""
    from connector.models import CurrentLineup, RacePhase

    called = {"value": False}

    class RecordingService:
        def get(self, *, demo, motoboard_id):
            called["value"] = True
            return CurrentLineup(moto_number=1, race_phase=RacePhase.ROUND_1, class_name="X", riders=[], source="racemanager")

    resolve_current_lineup(
        mode=ModeDecision(OperatingMode.UNAVAILABLE, "Neither RaceManager nor Sqorz is usable yet -- see /setup."),
        racemanager_lineup=RecordingService(),
        sqorz_current_race=SqorzCurrentRaceService(tmp_path / "sqorz.json"),
        sqorz=SqorzService(enabled=False),
    )

    assert called["value"] is True


def test_sqorz_only_mode_never_calls_the_racemanager_service(tmp_path: Path) -> None:
    sqorz_current_race = SqorzCurrentRaceService(tmp_path / "sqorz.json")
    sqorz_current_race.select(
        SqorzRaceSlot(
            class_code="308", class_name="12 Expert", phase_code="M1", phase_name="Moto 1", has_recorded_time=True
        )
    )
    sqorz = SqorzService(enabled=True, mode="internet", event_id="e")
    sqorz._get_json = lambda url: {
        "classRanks": [
            {
                "classCode": "308",
                "className": "12 Expert",
                "competitorRankSummaries": [
                    {
                        "plate": "1",
                        "firstName": "A",
                        "lastName": "RIDER",
                        "competitorRankDetails": [{"phaseCode": "M1", "phaseName": "Moto 1", "time": "40.0"}],
                    }
                ],
            }
        ]
    }

    result = resolve_current_lineup(
        mode=ModeDecision(OperatingMode.SQORZ_ONLY, "Sqorz-only mode is explicitly enabled in Configuration."),
        racemanager_lineup=racemanager_lineup_service(tmp_path),  # would raise if ever called
        sqorz_current_race=sqorz_current_race,
        sqorz=sqorz,
    )

    assert result.source == "sqorz"
    assert result.phase_label == "Moto 1"
    assert result.riders[0].last_name == "RIDER"


def test_sqorz_only_mode_with_nothing_selected_returns_the_empty_lineup(tmp_path: Path) -> None:
    result = resolve_current_lineup(
        mode=ModeDecision(OperatingMode.SQORZ_ONLY, "Sqorz-only mode is explicitly enabled in Configuration."),
        racemanager_lineup=racemanager_lineup_service(tmp_path),  # would raise if ever called
        sqorz_current_race=SqorzCurrentRaceService(tmp_path / "sqorz.json"),
        sqorz=SqorzService(enabled=True, mode="internet", event_id="e"),
    )

    assert result.riders == []
    assert result.warning


def test_sqorz_only_mode_filters_riders_to_the_selected_slot_only(tmp_path: Path) -> None:
    """A rider from a different class/phase in the same poll must never
    leak into the selected slot's lineup."""
    sqorz_current_race = SqorzCurrentRaceService(tmp_path / "sqorz.json")
    sqorz_current_race.select(
        SqorzRaceSlot(
            class_code="308", class_name="12 Expert", phase_code="M1", phase_name="Moto 1", has_recorded_time=True
        )
    )
    sqorz = SqorzService(enabled=True, mode="internet", event_id="e")
    sqorz._get_json = lambda url: {
        "classRanks": [
            {
                "classCode": "308",
                "className": "12 Expert",
                "competitorRankSummaries": [
                    {
                        "plate": "1", "firstName": "In", "lastName": "SLOT",
                        "competitorRankDetails": [{"phaseCode": "M1", "phaseName": "Moto 1", "time": "40.0"}],
                    },
                    {
                        "plate": "2", "firstName": "Other", "lastName": "PHASE",
                        "competitorRankDetails": [{"phaseCode": "M2", "phaseName": "Moto 2", "time": "41.0"}],
                    },
                ],
            },
            {
                "classCode": "601",
                "className": "9-10 Girls Cruiser",
                "competitorRankSummaries": [
                    {
                        "plate": "3", "firstName": "Other", "lastName": "CLASS",
                        "competitorRankDetails": [{"phaseCode": "M1", "phaseName": "Moto 1", "time": "39.0"}],
                    }
                ],
            },
        ]
    }

    result = resolve_current_lineup(
        mode=ModeDecision(OperatingMode.SQORZ_ONLY, "reason"),
        racemanager_lineup=racemanager_lineup_service(tmp_path),
        sqorz_current_race=sqorz_current_race,
        sqorz=sqorz,
    )

    assert [r.last_name for r in result.riders] == ["SLOT"]
