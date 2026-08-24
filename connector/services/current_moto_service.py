"""Thread-safe, file-backed exact RaceManager stage selection."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from connector.models import (
    ActiveGraphic,
    CompetitionStage,
    CurrentMoto,
    CurrentMotoUpdate,
    FinalizationMethod,
    RacePhase,
    RaceProgram,
    RaceStage,
    ScoringMethod,
)


_UNSET = object()


class CurrentMotoValidationError(ValueError):
    """Raised when a requested manual moto value is invalid."""


class CurrentMotoService:
    """Persist operator selection while remaining usable when SQL is offline.

    Version 1.2.8 stores the exact RaceManager identity resolved for a phase.
    Older state JSON remains valid because every new identity field is optional.
    """

    def __init__(
        self,
        state_file: Path,
        *,
        default_moto: int = 1,
        default_minimum: int = 1,
    ) -> None:
        self.state_file = state_file
        self.default_moto = default_moto
        self.default_minimum = default_minimum
        self._lock = threading.RLock()

    def get(self) -> CurrentMoto:
        with self._lock:
            return self._read_or_default()

    def set(self, update: CurrentMotoUpdate) -> CurrentMoto:
        with self._lock:
            current = self._read_or_default()
            minimum = (
                update.minimum_moto
                if update.minimum_moto is not None
                else current.minimum_moto
            )
            maximum = (
                update.maximum_moto
                if "maximum_moto" in update.model_fields_set
                else current.maximum_moto
            )
            motoboard_id = (
                update.motoboard_id
                if "motoboard_id" in update.model_fields_set
                else current.motoboard_id
            )
            phase = update.race_phase or current.race_phase
            self._validate_bounds(update.moto_number, minimum, maximum)

            selection_changed = (
                update.moto_number != current.moto_number
                or motoboard_id != current.motoboard_id
            )
            phase_changed = phase != current.race_phase

            def identity(name: str):
                if name in update.model_fields_set:
                    return getattr(update, name)
                if selection_changed:
                    return None
                if phase_changed and name in {
                    "round_type_id",
                    "round_id",
                    "motogroup_id",
                    "round_index",
                    "phase_label",
                }:
                    return None
                return getattr(current, name)

            def classification(name: str, unknown):
                if name in update.model_fields_set:
                    return getattr(update, name) or unknown
                if selection_changed or phase_changed:
                    return unknown
                return getattr(current, name)

            class_name = (
                self._normalize_class_name(update.class_name)
                if "class_name" in update.model_fields_set
                else (None if selection_changed else current.class_name)
            )

            result = CurrentMoto(
                moto_number=update.moto_number,
                race_phase=phase,
                phase_label=identity("phase_label"),
                class_name=class_name,
                minimum_moto=minimum,
                maximum_moto=maximum,
                motoboard_id=motoboard_id,
                resolved_motoboard_id=(None if selection_changed else current.resolved_motoboard_id),
                class_id=identity("class_id"),
                round_type_id=identity("round_type_id"),
                round_id=identity("round_id"),
                motogroup_id=identity("motogroup_id"),
                qualifier_motogroup_id=identity("qualifier_motogroup_id"),
                slot_key=identity("slot_key"),
                slot_class_ids=identity("slot_class_ids") or [],
                slot_motogroup_ids=identity("slot_motogroup_ids") or [],
                navigation_message=identity("navigation_message"),
                round_index=identity("round_index"),
                competition_stage=classification(
                    "competition_stage", CompetitionStage.UNKNOWN
                ),
                scoring_method=classification(
                    "scoring_method", ScoringMethod.UNKNOWN
                ),
                finalization_method=classification(
                    "finalization_method", FinalizationMethod.UNKNOWN
                ),
                updated_at=datetime.now(timezone.utc),
                source="manual",
                active_graphic=update.active_graphic or current.active_graphic,
            )
            self._write(result)
            return result

    def next(self) -> CurrentMoto:
        with self._lock:
            current = self._read_or_default()
            target = current.moto_number + 1
            if current.maximum_moto is not None:
                target = min(target, current.maximum_moto)
            return self.set(
                CurrentMotoUpdate(
                    moto_number=target,
                    race_phase=RacePhase.ROUND_1,
                    class_name=current.class_name,
                    minimum_moto=current.minimum_moto,
                    maximum_moto=current.maximum_moto,
                    motoboard_id=current.motoboard_id,
                    active_graphic=current.active_graphic,
                )
            )

    def previous(self) -> CurrentMoto:
        with self._lock:
            current = self._read_or_default()
            target = max(current.moto_number - 1, current.minimum_moto)
            return self.set(
                CurrentMotoUpdate(
                    moto_number=target,
                    race_phase=RacePhase.ROUND_1,
                    class_name=current.class_name,
                    minimum_moto=current.minimum_moto,
                    maximum_moto=current.maximum_moto,
                    motoboard_id=current.motoboard_id,
                    active_graphic=current.active_graphic,
                )
            )


    def next_phase(self) -> CurrentMoto:
        """Legacy offline phase stepping; API routes use RaceProgramService."""
        return self._legacy_step_phase(1)

    def previous_phase(self) -> CurrentMoto:
        """Legacy offline phase stepping; API routes use RaceProgramService."""
        return self._legacy_step_phase(-1)

    def _legacy_step_phase(self, direction: int) -> CurrentMoto:
        order = (
            RacePhase.ROUND_1,
            RacePhase.ROUND_2,
            RacePhase.ROUND_3,
            RacePhase.QUARTERFINAL,
            RacePhase.SEMIFINAL,
            RacePhase.MAIN,
        )
        current = self.get()
        index = order.index(current.race_phase)
        target = max(0, min(index + direction, len(order) - 1))
        return self.select_phase(order[target])

    def select_phase(self, phase: RacePhase) -> CurrentMoto:
        current = self.get()
        return self.set(
            CurrentMotoUpdate(
                moto_number=current.moto_number,
                race_phase=phase,
                minimum_moto=current.minimum_moto,
                maximum_moto=current.maximum_moto,
                motoboard_id=current.motoboard_id,
                class_id=current.class_id,
                qualifier_motogroup_id=current.qualifier_motogroup_id,
                active_graphic=current.active_graphic,
            )
        )

    def sync_race_position(
        self,
        *,
        motoboard_id: UUID,
        program: RaceProgram,
        stage: RaceStage,
        expected_state: CurrentMoto | None = None,
        slot_key: str | None = None,
        slot_class_ids: list[UUID] | None = None,
        slot_motogroup_ids: list[UUID] | None = None,
        slot_class_name: str | None = None,
        pinned_motoboard_id: UUID | None | object = _UNSET,
        minimum_moto: int | None = None,
        maximum_moto: int | None | object = _UNSET,
        active_graphic: ActiveGraphic | None = None,
        navigation_message: str | None = None,
    ) -> CurrentMoto:
        """Persist the exact stage returned by RaceManager.

        Database-backed lineup and results requests resolve outside this
        service's lock.  ``expected_state`` prevents an older request from
        overwriting a newer operator selection when its SQL query finishes.
        """
        with self._lock:
            current = self._read_or_default()
            if expected_state is not None and not self._same_selection(
                current, expected_state
            ):
                return current
            result = current.model_copy(
                update={
                    "moto_number": stage.moto_number,
                    "race_phase": stage.phase,
                    "phase_label": stage.label,
                    "class_name": self._normalize_class_name(stage.class_name),
                    "resolved_motoboard_id": motoboard_id,
                    "class_id": stage.class_id,
                    "round_type_id": stage.round_type_id,
                    "round_id": stage.round_id,
                    "motogroup_id": stage.motogroup_id,
                    "qualifier_motogroup_id": program.qualifier_motogroup_id,
                    "slot_key": slot_key
                    or f"{motoboard_id}:{stage.phase.value}:{stage.moto_number}",
                    "slot_class_ids": slot_class_ids or [stage.class_id],
                    "slot_motogroup_ids": slot_motogroup_ids
                    or [stage.motogroup_id],
                    "round_index": stage.round_index,
                    "competition_stage": stage.competition_stage,
                    "scoring_method": stage.scoring_method,
                    "finalization_method": stage.finalization_method,
                    "source": "racemanager",
                    "motoboard_id": (
                        current.motoboard_id
                        if pinned_motoboard_id is _UNSET
                        else pinned_motoboard_id
                    ),
                    "minimum_moto": (
                        current.minimum_moto
                        if minimum_moto is None
                        else minimum_moto
                    ),
                    "maximum_moto": (
                        current.maximum_moto
                        if maximum_moto is _UNSET
                        else maximum_moto
                    ),
                    "active_graphic": active_graphic or current.active_graphic,
                    "navigation_message": navigation_message,
                }
            )
            self._validate_bounds(
                result.moto_number,
                result.minimum_moto,
                result.maximum_moto,
            )
            if slot_class_name is not None:
                result = result.model_copy(
                    update={
                        "class_name": self._normalize_class_name(slot_class_name)
                    }
                )
            if result == current:
                return current
            result = result.model_copy(
                update={"updated_at": datetime.now(timezone.utc)}
            )
            self._write(result)
            return result

    def sync_class_name(self, class_name: str) -> CurrentMoto:
        """Backward-compatible helper used by older integrations."""
        with self._lock:
            current = self._read_or_default()
            normalized = self._normalize_class_name(class_name)
            if normalized == current.class_name:
                return current
            result = current.model_copy(
                update={
                    "class_name": normalized,
                    "updated_at": datetime.now(timezone.utc),
                    "source": "racemanager",
                }
            )
            self._write(result)
            return result

    def set_graphic(self, graphic: ActiveGraphic) -> CurrentMoto:
        with self._lock:
            current = self._read_or_default()
            result = current.model_copy(
                update={
                    "active_graphic": graphic,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._write(result)
            return result

    def reset(self) -> CurrentMoto:
        result = self._default_state().model_copy(
            update={"updated_at": datetime.now(timezone.utc)}
        )
        with self._lock:
            self._write(result)
        return result

    def _read_or_default(self) -> CurrentMoto:
        if not self.state_file.exists():
            return self._default_state()
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            if payload.get("race_phase") == "overall":
                # Overall was exposed incorrectly as a navigation phase before
                # v1.2.11.  Preserve the selected moto while migrating it into
                # the final Main program segment.
                payload["race_phase"] = RacePhase.MAIN.value
                payload["phase_label"] = "Main"
                payload["slot_key"] = None
            if (
                payload.get("race_phase") == RacePhase.ROUND_3.value
                and str(payload.get("phase_label") or "").strip().lower() == "round 3"
            ):
                # v1.2.15 and earlier persisted the literal label "Round 3",
                # which BBS never displays any more (see
                # docs/racemanager-round-model.md). Whether this stage is
                # "Main" or "Moto 3" depends on the class's finalization
                # method, which requires the database -- drop the stale label
                # so the next resolve re-derives it instead of guessing here.
                payload["phase_label"] = None
                payload["slot_key"] = None
            return CurrentMoto.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValueError):
            return self._default_state()

    def _default_state(self) -> CurrentMoto:
        return CurrentMoto(
            moto_number=self.default_moto,
            race_phase=RacePhase.ROUND_1,
            minimum_moto=self.default_minimum,
            active_graphic=ActiveGraphic.CURRENT_MOTO,
        )

    def _write(self, state: CurrentMoto) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        temporary.write_text(
            json.dumps(state.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.state_file)

    @staticmethod
    def _normalize_class_name(class_name: str | None) -> str | None:
        if class_name is None:
            return None
        normalized = " ".join(class_name.strip().split())
        if not normalized:
            return None
        if len(normalized) > 100:
            raise CurrentMotoValidationError("class_name must be 100 characters or fewer.")
        return normalized

    @staticmethod
    def _same_selection(current: CurrentMoto, expected: CurrentMoto) -> bool:
        """Return whether two snapshots represent the same operator choice."""
        if (
            current.moto_number != expected.moto_number
            or current.race_phase != expected.race_phase
            or current.motoboard_id != expected.motoboard_id
        ):
            return False

        for field in (
            "class_id",
            "round_type_id",
            "round_id",
            "motogroup_id",
            "qualifier_motogroup_id",
            "slot_key",
            "round_index",
            "competition_stage",
            "scoring_method",
            "finalization_method",
        ):
            current_value = getattr(current, field)
            expected_value = getattr(expected, field)
            if (
                current_value is not None
                and expected_value is not None
                and current_value != expected_value
            ):
                return False
        return True

    @staticmethod
    def _validate_bounds(moto_number: int, minimum: int, maximum: int | None) -> None:
        if minimum < 1:
            raise CurrentMotoValidationError("minimum_moto must be at least 1.")
        if maximum is not None and maximum < minimum:
            raise CurrentMotoValidationError(
                "maximum_moto must be greater than or equal to minimum_moto."
            )
        if moto_number < minimum:
            raise CurrentMotoValidationError(f"moto_number must be at least {minimum}.")
        if maximum is not None and moto_number > maximum:
            raise CurrentMotoValidationError(
                f"moto_number must not exceed {maximum}."
            )
