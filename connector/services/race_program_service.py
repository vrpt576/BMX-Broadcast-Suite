"""Resolve and step through only phases that RaceManager actually contains."""

from __future__ import annotations

from uuid import UUID

from connector.models import CurrentMoto, CurrentMotoUpdate, RacePhase, RaceProgram
from connector.services.current_moto_service import CurrentMotoService
from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService


class RaceProgramService:
    def __init__(
        self,
        current: CurrentMotoService,
        events: EventService,
        motos: MotoboardService,
    ) -> None:
        self.current = current
        self.events = events
        self.motos = motos

    def board_id(
        self,
        state: CurrentMoto | None = None,
        *,
        motoboard_id: UUID | None = None,
    ) -> UUID:
        state = state or self.current.get()
        return motoboard_id or state.motoboard_id or self.events.current().motoboard_id

    def get_program(
        self,
        *,
        motoboard_id: UUID | None = None,
    ) -> RaceProgram:
        state = self.current.get()
        return self.motos.get_program(
            self.board_id(state, motoboard_id=motoboard_id),
            state,
        )

    def resolve_and_sync(
        self,
        *,
        motoboard_id: UUID | None = None,
    ) -> CurrentMoto:
        state = self.current.get()
        board_id = self.board_id(state, motoboard_id=motoboard_id)
        resolved = self.motos.resolve_state(board_id, state)
        return self.current.sync_race_position(
            motoboard_id=board_id,
            program=resolved.program,
            stage=resolved.stage,
        )

    def select_phase(self, phase: RacePhase) -> CurrentMoto:
        program = self.get_program()
        if phase not in program.available_phases:
            available = ", ".join(item.value for item in program.available_phases)
            raise ValueError(
                f"{phase.value} is unavailable for {program.class_name}. "
                f"Available phases: {available or 'none'}."
            )
        self.current.select_phase(phase)
        return self.resolve_and_sync()

    def step_moto(self, direction: int) -> CurrentMoto:
        """Move within the RaceManager branch for the current phase.

        Qualifying phases walk Round_Type_ID 123 motogroups. Main/Overall
        phases walk Round_Type_ID 1 classifications. This prevents a Next
        Moto command during mains from jumping back into qualifier data.
        """
        state = self.current.get()
        board_id = self.board_id(state)
        final_branch = state.race_phase in {RacePhase.MAIN, RacePhase.OVERALL}
        branch = self.motos.list_motos(
            board_id,
            round_type_id=1 if final_branch else 123,
        ).motos
        if not branch:
            return state

        current_group_id = (
            state.motogroup_id
            if final_branch
            else state.qualifier_motogroup_id or state.motogroup_id
        )
        index = next(
            (
                item_index
                for item_index, moto in enumerate(branch)
                if moto.motogroup_id == current_group_id
            ),
            -1,
        )
        if index < 0 and state.class_id is not None:
            index = next(
                (
                    item_index
                    for item_index, moto in enumerate(branch)
                    if moto.class_id == state.class_id
                    and moto.moto_number == state.moto_number
                ),
                -1,
            )
        if index < 0:
            index = next(
                (
                    item_index
                    for item_index, moto in enumerate(branch)
                    if moto.moto_number == state.moto_number
                ),
                0,
            )

        target_index = max(0, min(index + direction, len(branch) - 1))
        target = branch[target_index]
        self.current.set(
            CurrentMotoUpdate(
                moto_number=target.moto_number,
                race_phase=state.race_phase,
                minimum_moto=state.minimum_moto,
                maximum_moto=state.maximum_moto,
                motoboard_id=state.motoboard_id,
                class_id=target.class_id,
                round_type_id=target.round_type_id,
                round_id=target.round_id,
                motogroup_id=target.motogroup_id,
                qualifier_motogroup_id=(
                    target.motogroup_id if target.round_type_id == 123 else None
                ),
                active_graphic=state.active_graphic,
            )
        )
        try:
            return self.resolve_and_sync()
        except LookupError:
            # A target may not contain the same qualifier round (for example,
            # Round 3 on a transfer class). Fall back to its first real phase.
            program = self.get_program()
            if not program.available_phases:
                return self.current.get()
            return self.select_phase(program.available_phases[0])

    def step_phase(self, direction: int) -> CurrentMoto:
        state = self.current.get()
        program = self.get_program()
        phases = program.available_phases
        if not phases:
            return state
        try:
            index = phases.index(state.race_phase)
        except ValueError:
            index = 0
        target = max(0, min(index + direction, len(phases) - 1))
        return self.select_phase(phases[target])
