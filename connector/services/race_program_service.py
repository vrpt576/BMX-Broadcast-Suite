"""Resolve and step through only phases that RaceManager actually contains."""

from __future__ import annotations

from uuid import UUID

from connector.models import (
    ActiveGraphic,
    CurrentMoto,
    CurrentMotoUpdate,
    RacePhase,
    RaceProgram,
    RaceSlot,
)
from connector.services.current_moto_service import CurrentMotoService
from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService
from connector.services.race_slot_service import RaceSlotService


PHASE_ORDER = (
    RacePhase.ROUND_1,
    RacePhase.ROUND_2,
    RacePhase.ROUND_3,
    RacePhase.QUARTERFINAL,
    RacePhase.SEMIFINAL,
    RacePhase.MAIN,
    RacePhase.OVERALL,
)

_UNSET = object()


class RaceSlotUnavailableError(LookupError):
    def __init__(
        self,
        moto_number: int,
        phase: RacePhase,
        *,
        previous_moto: int | None,
        next_moto: int | None,
    ) -> None:
        nearby = []
        if previous_moto is not None:
            nearby.append(f"previous {previous_moto}")
        if next_moto is not None:
            nearby.append(f"next {next_moto}")
        suffix = f" Nearest available: {', '.join(nearby)}." if nearby else ""
        super().__init__(
            f"Moto {moto_number} is unavailable in {phase.value}.{suffix}"
        )
        self.moto_number = moto_number
        self.phase = phase
        self.previous_moto = previous_moto
        self.next_moto = next_moto


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

    def available_phases(self, *, motoboard_id: UUID | None = None) -> list[RacePhase]:
        state = self.current.get()
        board_id = self.board_id(state, motoboard_id=motoboard_id)
        motos = self.motos.list_motos(board_id, round_type_id=None).motos
        return [
            phase
            for phase in PHASE_ORDER
            if self.slots.catalog_from_motos(board_id, phase, motos)
        ]

    def select_moto(self, update: CurrentMotoUpdate) -> CurrentMoto:
        """Resolve an exact displayed slot before atomically persisting it."""
        state = self.current.get()
        explicit_pin = "motoboard_id" in update.model_fields_set
        pinned_board = update.motoboard_id if explicit_pin else state.motoboard_id
        board_id = pinned_board or self.events.current().motoboard_id
        phase = update.race_phase or state.race_phase
        slots = self.slots.catalog(board_id, phase)
        slot = next(
            (item for item in slots if item.moto_number == update.moto_number),
            None,
        )
        navigation_message = None
        event_changed = explicit_pin and pinned_board != state.motoboard_id
        if slot is None and event_changed and slots:
            slot = min(
                slots,
                key=lambda item: (
                    abs(item.moto_number - update.moto_number),
                    item.moto_number,
                ),
            )
            navigation_message = (
                f"The previous race position is unavailable in the selected event; "
                f"moved to {phase.value} Moto {slot.moto_number}."
            )
        if slot is None:
            previous = max(
                (item.moto_number for item in slots if item.moto_number < update.moto_number),
                default=None,
            )
            following = min(
                (item.moto_number for item in slots if item.moto_number > update.moto_number),
                default=None,
            )
            raise RaceSlotUnavailableError(
                update.moto_number,
                phase,
                previous_moto=previous,
                next_moto=following,
            )
        return self._sync_slot(
            board_id,
            slot,
            state,
            pinned_motoboard_id=pinned_board,
            minimum_moto=(
                update.minimum_moto
                if update.minimum_moto is not None
                else state.minimum_moto
            ),
            maximum_moto=(
                update.maximum_moto
                if "maximum_moto" in update.model_fields_set
                else state.maximum_moto
            ),
            active_graphic=update.active_graphic or state.active_graphic,
            navigation_message=navigation_message,
        )

    def select_phase(self, phase: RacePhase) -> CurrentMoto:
        state = self.current.get()
        board_id = self.board_id(state)
        slots = self.slots.catalog(board_id, phase)
        if not slots:
            available = ", ".join(item.value for item in self.available_phases())
            raise ValueError(
                f"{phase.value} is unavailable. Available phases: {available or 'none'}."
            )
        selected_classes = set(state.slot_class_ids)
        if state.class_id is not None:
            selected_classes.add(state.class_id)
        same_group = [
            slot
            for slot in slots
            if selected_classes and set(slot.class_ids) == selected_classes
        ]
        same_class = [
            slot for slot in slots if selected_classes.intersection(slot.class_ids)
        ]
        candidates = same_group or same_class or slots
        slot = min(
            candidates,
            key=lambda item: (
                abs(item.moto_number - state.moto_number),
                item.moto_number,
            ),
        )
        message = None
        if not same_class:
            message = (
                f"The selected class is unavailable in {phase.value}; "
                f"moved to nearest Moto {slot.moto_number}."
            )
        elif slot.moto_number != state.moto_number:
            message = (
                f"Mapped the selected class to {phase.value} Moto {slot.moto_number}."
            )
        return self._sync_slot(
            board_id,
            slot,
            state,
            navigation_message=message,
        )

    def select_phase_boundary(self, *, last: bool) -> CurrentMoto:
        state = self.current.get()
        board_id = self.board_id(state)
        slots = self.slots.catalog(board_id, state.race_phase)
        if not slots:
            return state
        slot = slots[-1] if last else slots[0]
        return self._sync_slot(
            board_id,
            slot,
            state,
            navigation_message=(
                f"Moved to {'last' if last else 'first'} moto in "
                f"{state.race_phase.value}."
            ),
        )

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
        return self._sync_slot(board_id, slot, state)

    def _sync_slot(
        self,
        board_id: UUID,
        slot: RaceSlot,
        state: CurrentMoto,
        *,
        pinned_motoboard_id: UUID | None | object = _UNSET,
        minimum_moto: int | None = None,
        maximum_moto: int | None | object = _UNSET,
        active_graphic: ActiveGraphic | None = None,
        navigation_message: str | None = None,
    ) -> CurrentMoto:
        member = next(
            (
                item for item in slot.members
                if state.class_id is not None and item.stage.class_id == state.class_id
            ),
            slot.members[0],
        )
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
        kwargs = {}
        if pinned_motoboard_id is not _UNSET:
            kwargs["pinned_motoboard_id"] = pinned_motoboard_id
        if maximum_moto is not _UNSET:
            kwargs["maximum_moto"] = maximum_moto
        return self.current.sync_race_position(
            motoboard_id=board_id,
            program=program,
            stage=member.stage,
            expected_state=state,
            slot_key=slot.slot_key,
            slot_class_ids=slot.class_ids,
            slot_motogroup_ids=slot.motogroup_ids,
            slot_class_name=slot.class_name,
            minimum_moto=minimum_moto,
            active_graphic=active_graphic,
            navigation_message=navigation_message,
            **kwargs,
        )

    def step_phase(self, direction: int) -> CurrentMoto:
        state = self.current.get()
        phases = self.available_phases()
        if not phases:
            return state
        try:
            index = phases.index(state.race_phase)
        except ValueError:
            index = min(
                range(len(phases)),
                key=lambda item: abs(
                    PHASE_ORDER.index(phases[item])
                    - PHASE_ORDER.index(state.race_phase)
                ),
            )
        target = max(0, min(index + direction, len(phases) - 1))
        return self.select_phase(phases[target])
