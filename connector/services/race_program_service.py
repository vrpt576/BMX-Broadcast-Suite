"""Resolve and step through only phases that RaceManager actually contains."""

from __future__ import annotations

from uuid import UUID

from connector.models import CurrentMoto, CurrentMotoUpdate, RacePhase, RaceProgram
from connector.services.current_moto_service import CurrentMotoService
from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService
from connector.services.race_slot_service import RaceSlotService


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
        self.slots = RaceSlotService(motos)

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
        """Move exactly one unique displayed race slot in the selected phase."""
        state = self.current.get()
        if direction == 0:
            return state

        board_id = self.board_id(state)
        slots = self.slots.catalog(board_id, state.race_phase)
        if not slots:
            return state
        index = next(
            (
                item_index for item_index, slot in enumerate(slots)
                if state.slot_key is not None and slot.slot_key == state.slot_key
            ),
            -1,
        )
        if index < 0:
            index = next(
                (
                    item_index for item_index, slot in enumerate(slots)
                    if slot.moto_number == state.moto_number
                    and (
                        state.class_id is None
                        or state.class_id in slot.class_ids
                    )
                ),
                -1,
            )
        if index < 0:
            index = next(
                (
                    item_index for item_index, slot in enumerate(slots)
                    if slot.moto_number == state.moto_number
                ),
                -1,
            )
        step = 1 if direction > 0 else -1
        if index < 0:
            index = -1 if step > 0 else len(slots)
        target_index = index + step
        if not 0 <= target_index < len(slots):
            return state

        slot = slots[target_index]
        member = slot.members[0]
        probe = state.model_copy(
            update={
                "moto_number": slot.moto_number,
                "race_phase": slot.phase,
                "class_id": member.stage.class_id,
                "round_type_id": member.stage.round_type_id,
                "round_id": member.stage.round_id,
                "motogroup_id": member.stage.motogroup_id,
                "qualifier_motogroup_id": member.qualifier_motogroup_id,
            }
        )
        program = self.motos.get_program(board_id, probe)
        return self.current.sync_race_position(
            motoboard_id=board_id,
            program=program,
            stage=member.stage,
            expected_state=state,
            slot_key=slot.slot_key,
            slot_class_ids=slot.class_ids,
            slot_motogroup_ids=slot.motogroup_ids,
            slot_class_name=slot.class_name,
        )

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
