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
            expected_state=state,
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
        """Move to the next compatible RaceManager moto.

        Qualifying phases walk Round_Type_ID 123 motogroups.
        Main and Overall phases walk Round_Type_ID 1 classifications,
        skipping classes that do not contain the currently selected phase.
        """
        state = self.current.get()
        if direction == 0:
            return state

        board_id = self.board_id(state)
        final_branch = state.race_phase in {
            RacePhase.MAIN,
            RacePhase.OVERALL,
        }

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
                -1,
            )

        step = 1 if direction > 0 else -1

        # When the current group cannot be found, start at the appropriate
        # end of the branch.
        if index < 0:
            index = -1 if step > 0 else len(branch)

        candidate_index = index + step

        while 0 <= candidate_index < len(branch):
            target = branch[candidate_index]

            probe = state.model_copy(
                update={
                    "moto_number": target.moto_number,
                    "class_id": target.class_id,
                    "round_type_id": target.round_type_id,
                    "round_id": target.round_id,
                    "motogroup_id": target.motogroup_id,
                    "qualifier_motogroup_id": (
                        target.motogroup_id
                        if target.round_type_id == 123
                        else None
                    ),
                }
            )

            try:
                resolved = self.motos.resolve_state(board_id, probe)
            except LookupError:
                if final_branch:
                    # Some Round_Type_ID 1 entries are Overall/points
                    # classifications rather than Mains, or vice versa.
                    # Skip them without changing the selected phase.
                    candidate_index += step
                    continue

                # Preserve the existing qualifier behavior: a target class
                # may not contain the same qualifying round.
                try:
                    program = self.motos.get_program(board_id, probe)
                    if not program.available_phases:
                        candidate_index += step
                        continue

                    probe = probe.model_copy(
                        update={"race_phase": program.available_phases[0]}
                    )
                    resolved = self.motos.resolve_state(board_id, probe)
                except LookupError:
                    candidate_index += step
                    continue

            return self.current.sync_race_position(
                motoboard_id=board_id,
                program=resolved.program,
                stage=resolved.stage,
                expected_state=state,
            )

        # Already at the beginning/end of the compatible branch.
        return state

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
