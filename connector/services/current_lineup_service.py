"""Resolve the operator-selected moto into broadcast-ready rider gate data."""

from __future__ import annotations

from uuid import UUID

from connector.models import (
    CurrentLineup,
    CurrentMoto,
    LineupRider,
    Moto,
    RacePhase,
)
from connector.services.current_moto_service import CurrentMotoService
from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService


# Verified RaceManager data from Thursday Night Racing on 2026-07-23.
# This makes it possible to design and test the lower third away from the track.
DEMO_MOTO = Moto.model_validate(
    {
        "moto_number": 1,
        "motogroup_number": 1,
        "class_id": "00000000-0000-0000-0000-000000000001",
        "class_name": "7 Intermediate",
        "class_name_short": "7 Intermediate",
        "round_id": "00000000-0000-0000-0000-000000000123",
        "round_type_id": 123,
        "state": "scored",
        "riders_scored": 4,
        "riders_total": 4,
        "updated_at": "2026-07-23T18:31:29.437",
        "riders": [
            {
                "rider_id": "00000000-0000-0000-0001-000000000093",
                "motogroup_rider_id": "00000000-0000-0000-0101-000000000093",
                "rider_order": 1,
                "bike_number": 93,
                "first_name": "Dylan",
                "last_name": "Allen",
                "lane_1": 2,
                "finish_1": 2,
            },
            {
                "rider_id": "00000000-0000-0000-0001-000000000085",
                "motogroup_rider_id": "00000000-0000-0000-0101-000000000085",
                "rider_order": 2,
                "bike_number": 85,
                "first_name": "Kadin",
                "last_name": "Faler",
                "lane_1": 4,
                "finish_1": 1,
            },
            {
                "rider_id": "00000000-0000-0000-0001-000000000072",
                "motogroup_rider_id": "00000000-0000-0000-0101-000000000072",
                "rider_order": 3,
                "bike_number": 72,
                "first_name": "Dash",
                "last_name": "Hodkins",
                "lane_1": 6,
                "finish_1": 3,
            },
            {
                "rider_id": "00000000-0000-0000-0001-000000000004",
                "motogroup_rider_id": "00000000-0000-0000-0101-000000000004",
                "rider_order": 4,
                "bike_number": 4,
                "first_name": "Rye",
                "last_name": "Cohen",
                "lane_1": 8,
                "finish_1": 4,
            },
        ],
    }
)


class CurrentLineupService:
    """Combines current manual control state with RaceManager moto data."""

    def __init__(
        self,
        current: CurrentMotoService,
        events: EventService,
        motos: MotoboardService,
    ) -> None:
        self.current = current
        self.events = events
        self.motos = motos

    def get(self, *, demo: bool = False, motoboard_id: UUID | None = None) -> CurrentLineup:
        state = self.current.get()
        if demo:
            return self._build(state, DEMO_MOTO, source="demo")

        board_id = motoboard_id or self.events.current().motoboard_id
        moto = self.motos.get_moto(board_id, state.moto_number)
        return self._build(state, moto, source="racemanager")

    @staticmethod
    def _gate_for_phase(rider: object, phase: RacePhase) -> int | None:
        # RaceManager exposes three verified lane fields. Later elimination/main
        # round storage still needs track-side validation, so use the first
        # available gate as a safe fallback instead of returning a blank graphic.
        preferred = {
            RacePhase.ROUND_1: getattr(rider, "lane_1", None),
            RacePhase.ROUND_2: getattr(rider, "lane_2", None),
            RacePhase.ROUND_3: getattr(rider, "lane_3", None),
        }.get(phase)
        if preferred is not None:
            return preferred
        return next(
            (
                lane
                for lane in (
                    getattr(rider, "lane_1", None),
                    getattr(rider, "lane_2", None),
                    getattr(rider, "lane_3", None),
                )
                if lane is not None
            ),
            None,
        )

    @classmethod
    def _build(cls, state: CurrentMoto, moto: Moto, *, source: str) -> CurrentLineup:
        riders = [
            LineupRider(
                gate=cls._gate_for_phase(rider, state.race_phase),
                bike_number=rider.bike_number,
                first_name=rider.first_name,
                last_name=rider.last_name,
                nickname=rider.nickname,
            )
            for rider in moto.riders
        ]
        riders.sort(key=lambda rider: (rider.gate is None, rider.gate or 999, rider.last_name))
        return CurrentLineup(
            moto_number=state.moto_number,
            race_phase=state.race_phase,
            class_name=moto.class_name or state.class_name,
            riders=riders,
            source=source,
            updated_at=moto.updated_at,
        )
