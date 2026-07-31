"""Round-aware results derived from exact RaceManager stage fields."""

from __future__ import annotations

from uuid import UUID

from connector.models import CurrentResults, ResultRider
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
                lineup = self.lineups.get(demo=True)
                moto = DEMO_MOTO
                round_index = lineup.round_index or 1
                board_id = None
                phase_label = lineup.phase_label
                phases = lineup.available_phases
                class_id = lineup.class_id
                round_type_id = lineup.round_type_id
                round_id = lineup.round_id
                motogroup_id = lineup.motogroup_id
                race_phase = lineup.race_phase
            else:
                board_id = selected_board_id or self.events.current().motoboard_id
                if hasattr(self.motos, "resolve_state"):
                    resolved = self.motos.resolve_state(board_id, state)
                    synced = self.current.sync_race_position(
                        motoboard_id=board_id,
                        program=resolved.program,
                        stage=resolved.stage,
                        expected_state=state,
                    )
                    moto = resolved.moto
                    stage, program = resolved.stage, resolved.program
                    race_phase = synced.race_phase
                else:  # compatibility with older adapters and test doubles
                    moto = self.motos.get_moto(board_id, state.moto_number)
                    stage, program = CurrentLineupService._legacy_context(
                        state, moto, board_id
                    )
                    race_phase = state.race_phase
                round_index = stage.round_index
                phase_label = stage.label
                phases = program.available_phases
                class_id = stage.class_id
                round_type_id = stage.round_type_id
                round_id = stage.round_id
                motogroup_id = stage.motogroup_id

            riders: list[ResultRider] = []
            field = f"finish_{round_index}"
            for rider in moto.riders:
                finish, transferred, status = self._normalize_finish(
                    getattr(rider, field, None)
                )
                riders.append(
                    ResultRider(
                        finish=finish,
                        transferred=transferred,
                        status=status,
                        bike_number=rider.bike_number,
                        first_name=rider.first_name,
                        last_name=rider.last_name,
                    )
                )
            riders.sort(
                key=lambda rider: (
                    rider.finish is None,
                    rider.finish if rider.finish is not None else 999,
                    not rider.transferred,
                    rider.last_name,
                )
            )
            return CurrentResults(
                moto_number=moto.moto_number,
                race_phase=race_phase,
                phase_label=phase_label,
                available_phases=phases,
                motoboard_id=board_id,
                class_id=class_id,
                round_type_id=round_type_id,
                round_id=round_id,
                motogroup_id=motogroup_id,
                round_index=round_index,
                class_name=moto.class_name or state.class_name or "Class not set",
                riders=riders,
                source="demo" if demo else "racemanager",
                updated_at=moto.updated_at,
                experimental=True,
            )
        except Exception as exc:
            lineup = self.lineups.get(
                demo=False,
                motoboard_id=selected_board_id,
            )
            return CurrentResults(
                moto_number=lineup.moto_number,
                race_phase=lineup.race_phase,
                phase_label=lineup.phase_label,
                available_phases=lineup.available_phases,
                motoboard_id=lineup.motoboard_id,
                class_id=lineup.class_id,
                round_type_id=lineup.round_type_id,
                round_id=lineup.round_id,
                motogroup_id=lineup.motogroup_id,
                round_index=lineup.round_index,
                class_name=lineup.class_name,
                riders=[],
                source="cache",
                is_stale=True,
                warning=str(exc),
                experimental=True,
            )

    @staticmethod
    def _normalize_finish(value: object) -> tuple[int | None, bool, str | None]:
        if value is None:
            return None, False, None
        if isinstance(value, bool):
            return int(value), False, None
        if isinstance(value, int):
            return value, False, None
        text = str(value).strip()
        if not text:
            return None, False, None
        if text.upper() == "X":
            return None, True, "Transfer"
        try:
            return int(text), False, None
        except ValueError:
            return None, False, text
