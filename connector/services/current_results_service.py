"""Experimental results view derived from RaceManager finish fields."""

from __future__ import annotations

from uuid import UUID

from connector.models import CurrentResults, RacePhase, ResultRider
from connector.services.current_lineup_service import CurrentLineupService, DEMO_MOTO
from connector.services.current_moto_service import CurrentMotoService
from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService


class CurrentResultsService:
    def __init__(
        self,
        current: CurrentMotoService,
        events: EventService,
        motos: MotoboardService,
        lineups: CurrentLineupService,
    ) -> None:
        self.current = current
        self.events = events
        self.motos = motos
        self.lineups = lineups

    def get(
        self,
        *,
        demo: bool = False,
        motoboard_id: UUID | None = None,
    ) -> CurrentResults:
        state = self.current.get()
        selected_board_id = motoboard_id or state.motoboard_id
        try:
            if demo:
                board_id = None
                moto = DEMO_MOTO
            else:
                board_id = selected_board_id or self.events.current().motoboard_id
                moto = self.motos.get_moto(board_id, state.moto_number)

            field = {
                RacePhase.ROUND_1: "finish_1",
                RacePhase.ROUND_2: "finish_2",
                RacePhase.ROUND_3: "finish_3",
            }.get(state.race_phase)
            riders: list[ResultRider] = []
            for rider in moto.riders:
                finish = (
                    getattr(rider, field, None)
                    if field
                    else next(
                        (
                            value
                            for value in (
                                rider.finish_3,
                                rider.finish_2,
                                rider.finish_1,
                            )
                            if value is not None
                        ),
                        None,
                    )
                )
                riders.append(
                    ResultRider(
                        finish=finish,
                        bike_number=rider.bike_number,
                        first_name=rider.first_name,
                        last_name=rider.last_name,
                    )
                )
            riders.sort(
                key=lambda rider: (
                    rider.finish is None,
                    rider.finish or 999,
                    rider.last_name,
                )
            )
            return CurrentResults(
                moto_number=state.moto_number,
                race_phase=state.race_phase,
                motoboard_id=board_id,
                class_name=moto.class_name or state.class_name or "Class not set",
                riders=riders,
                source="demo" if demo else "racemanager",
                updated_at=moto.updated_at,
            )
        except Exception as exc:
            lineup = self.lineups.get(
                demo=False,
                motoboard_id=selected_board_id,
            )
            return CurrentResults(
                moto_number=lineup.moto_number,
                race_phase=lineup.race_phase,
                motoboard_id=lineup.motoboard_id,
                class_name=lineup.class_name,
                riders=[],
                source="cache",
                is_stale=True,
                warning=str(exc),
            )
