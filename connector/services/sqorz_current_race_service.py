"""Thread-safe, file-backed operator selection for Sqorz-only mode.

Mirrors CurrentMotoService's persistence pattern (RLock, atomic
write-then-replace, tolerant of a missing or corrupt state file) but keyed
on Sqorz's own identifiers (class_code, phase_code) instead of
RaceManager's motoboard/class/round ids -- there is no RaceManager identity
to persist here, and this service never imports anything that has one. See
docs/sqorz-only-mode.md.

Deliberately pure state storage, nothing else: it does not know about a
catalog, cannot step forward or back, and cannot resolve a (class_code,
phase_code) pair against live rider data. That composition lives one layer
up (connector/routes/sqorz_director.py), which calls
sqorz_navigation_service's catalog/step functions and only hands this
service the resulting SqorzRaceSlot to persist -- the same separation
RaceManager's own architecture already uses between RaceProgramService
(catalog + stepping) and CurrentMotoService (storage only).
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from connector.services.sqorz_navigation_service import SqorzRaceSlot


@dataclass(frozen=True)
class SqorzCurrentRace:
    class_code: str | None
    class_name: str | None
    phase_code: str | None
    phase_name: str | None
    updated_at: str  # ISO 8601, UTC


class SqorzCurrentRaceService:
    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file
        self._lock = threading.RLock()

    def get(self) -> SqorzCurrentRace | None:
        """None means nothing has been selected yet -- distinct from "the
        default race". Unlike RaceManager mode, there is no fixed schedule
        to imply a starting point (Moto 1); the operator, or the Director
        UI's own first-load logic, must make an explicit first selection."""
        with self._lock:
            return self._read()

    def select(self, slot: SqorzRaceSlot) -> SqorzCurrentRace:
        with self._lock:
            result = SqorzCurrentRace(
                class_code=slot.class_code,
                class_name=slot.class_name,
                phase_code=slot.phase_code,
                phase_name=slot.phase_name,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            self._write(result)
            return result

    def reset(self) -> None:
        with self._lock:
            if self.state_file.exists():
                self.state_file.unlink()

    def _read(self) -> SqorzCurrentRace | None:
        if not self.state_file.exists():
            return None
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            return SqorzCurrentRace(
                class_code=payload.get("class_code"),
                class_name=payload.get("class_name"),
                phase_code=payload.get("phase_code"),
                phase_name=payload.get("phase_name"),
                updated_at=payload["updated_at"],
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            return None

    def _write(self, state: SqorzCurrentRace) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        temporary.write_text(json.dumps(asdict(state), indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.state_file)
