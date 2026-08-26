"""Operator-editable RaceManager-class -> Sqorz-class aliases.

Follows the same pattern as PhaseClassificationOverrideStore
(phase_classification_service.py): a small local JSON file, atomic writes,
operator wins over inference, never written back to RaceManager or Sqorz.
There is no cache here -- every lookup re-reads the file, so an alias saved
through the UI takes effect on the very next poll without restarting BBS.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

_LOCK = threading.RLock()


class SqorzClassAliasStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lock = _LOCK

    def _read(self) -> dict[str, str]:
        if self.path is None or not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Sqorz class alias file must contain a JSON object.")
        return {str(key): str(value) for key, value in payload.items()}

    def _write(self, payload: dict[str, str]) -> None:
        if self.path is None:
            raise ValueError("A Sqorz class alias file is required to save an alias.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, self.path)

    def get_alias(self, bbs_class_name: str) -> str | None:
        with self._lock:
            return self._read().get(bbs_class_name)

    def all_aliases(self) -> dict[str, str]:
        with self._lock:
            return self._read()

    def set_alias(self, bbs_class_name: str, sqorz_class_name: str | None) -> None:
        with self._lock:
            payload = self._read()
            if sqorz_class_name is None or not sqorz_class_name.strip():
                payload.pop(bbs_class_name, None)
            else:
                payload[bbs_class_name] = sqorz_class_name.strip()
            self._write(payload)
