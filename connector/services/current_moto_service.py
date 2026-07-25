"""Thread-safe, file-backed manual current-moto state."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from connector.models import CurrentMoto, CurrentMotoUpdate, RacePhase


class CurrentMotoValidationError(ValueError):
    """Raised when a requested manual moto value is invalid."""


PHASE_ORDER: tuple[RacePhase, ...] = (
    RacePhase.ROUND_1,
    RacePhase.ROUND_2,
    RacePhase.ROUND_3,
    RacePhase.QUARTERFINAL,
    RacePhase.SEMIFINAL,
    RacePhase.MAIN,
)


class CurrentMotoService:
    """Stores the operator-selected current moto independently of RaceManager.

    The small JSON state file lets the selection survive connector restarts while
    keeping the keyboard controller usable even when SQL Server is unavailable.
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
            minimum = update.minimum_moto if update.minimum_moto is not None else current.minimum_moto
            maximum = update.maximum_moto if update.maximum_moto is not None else current.maximum_moto
            self._validate_bounds(update.moto_number, minimum, maximum)
            result = CurrentMoto(
                moto_number=update.moto_number,
                race_phase=update.race_phase or current.race_phase,
                class_name=self._normalize_class_name(update.class_name) if update.class_name is not None else current.class_name,
                minimum_moto=minimum,
                maximum_moto=maximum,
                updated_at=datetime.now(timezone.utc),
                source="manual",
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
                    race_phase=current.race_phase,
                    class_name=current.class_name,
                    minimum_moto=current.minimum_moto,
                    maximum_moto=current.maximum_moto,
                )
            )

    def previous(self) -> CurrentMoto:
        with self._lock:
            current = self._read_or_default()
            target = max(current.moto_number - 1, current.minimum_moto)
            return self.set(
                CurrentMotoUpdate(
                    moto_number=target,
                    race_phase=current.race_phase,
                    class_name=current.class_name,
                    minimum_moto=current.minimum_moto,
                    maximum_moto=current.maximum_moto,
                )
            )

    def next_phase(self) -> CurrentMoto:
        return self._step_phase(1)

    def previous_phase(self) -> CurrentMoto:
        return self._step_phase(-1)

    def _step_phase(self, direction: int) -> CurrentMoto:
        with self._lock:
            current = self._read_or_default()
            index = PHASE_ORDER.index(current.race_phase)
            target_index = max(0, min(index + direction, len(PHASE_ORDER) - 1))
            return self.set(
                CurrentMotoUpdate(
                    moto_number=current.moto_number,
                    race_phase=PHASE_ORDER[target_index],
                    class_name=current.class_name,
                    minimum_moto=current.minimum_moto,
                    maximum_moto=current.maximum_moto,
                )
            )

    def reset(self) -> CurrentMoto:
        return self.set(
            CurrentMotoUpdate(
                moto_number=self.default_moto,
                race_phase=RacePhase.ROUND_1,
                class_name="",
                minimum_moto=self.default_minimum,
                maximum_moto=None,
            )
        )

    def _read_or_default(self) -> CurrentMoto:
        if not self.state_file.exists():
            return CurrentMoto(
                moto_number=self.default_moto,
                race_phase=RacePhase.ROUND_1,
                class_name=None,
                minimum_moto=self.default_minimum,
                maximum_moto=None,
                updated_at=None,
                source="manual",
            )
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            return CurrentMoto.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValueError):
            # A corrupt state file should not take down a live broadcast. Start
            # from the safe default; the next operator action rewrites the file.
            return CurrentMoto(
                moto_number=self.default_moto,
                race_phase=RacePhase.ROUND_1,
                class_name=None,
                minimum_moto=self.default_minimum,
                maximum_moto=None,
                updated_at=None,
                source="manual",
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
    def _validate_bounds(moto_number: int, minimum: int, maximum: int | None) -> None:
        if minimum < 1:
            raise CurrentMotoValidationError("minimum_moto must be at least 1.")
        if maximum is not None and maximum < minimum:
            raise CurrentMotoValidationError(
                "maximum_moto must be greater than or equal to minimum_moto."
            )
        if moto_number < minimum:
            raise CurrentMotoValidationError(
                f"moto_number must be at least {minimum}."
            )
        if maximum is not None and moto_number > maximum:
            raise CurrentMotoValidationError(
                f"moto_number must not exceed {maximum}."
            )
