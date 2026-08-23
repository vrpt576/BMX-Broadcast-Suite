"""Round/phase display labels sourced from RaceManager's own Ref.Rounds table.

RaceManager has no "Round 1/2/3" concept anywhere in its data model. Ref.Rounds
is a small static reference table naming every round RaceManager actually
produces: Round_Type_ID 123 ("Moto", Round_Type 'H') covers the whole
qualifying phase regardless of how many motos a class runs, and the
bracket-advancement rounds (Main, Semi, Qtr, LCQ, 8th, 16th, 32nd) each get
their own Round_Type_ID. This module reads that table instead of inferring a
label from which Lane_N/Finish_N columns happen to be populated.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from database import queries
from database.racemanager import RaceManagerDatabase

MOTO_ROUND_TYPE_ID = 123


@dataclass(frozen=True)
class RoundLabel:
    round_type_id: int
    name: str
    round_type: str
    description: str


# Static mirror of Ref.Rounds, used only if the live lookup is unavailable
# (e.g. schema not yet present on an install). Ref.Rounds itself remains the
# source of truth and is preferred whenever the query succeeds.
_FALLBACK_ROUNDS = {
    1: RoundLabel(1, "Main", "Z", "Main"),
    2: RoundLabel(2, "Semi", "M", "Semi"),
    3: RoundLabel(3, "Semi", "M", "Semi for LCQ"),
    4: RoundLabel(4, "Qtr", "M", "Qtr"),
    5: RoundLabel(5, "LCQ", "M", "LCQ"),
    8: RoundLabel(8, "8th", "M", "8th"),
    16: RoundLabel(16, "16th", "M", "16th"),
    32: RoundLabel(32, "32nd", "M", "32nd"),
    MOTO_ROUND_TYPE_ID: RoundLabel(MOTO_ROUND_TYPE_ID, "Moto", "H", "Moto"),
}


class RoundLabelResolver:
    """Resolves Round_Type_ID to RaceManager's own round name, with caching.

    Ref.Rounds is a handful of static rows, so the result is cached in memory
    and only refreshed periodically in case USA BMX adds a new round type.
    """

    def __init__(
        self,
        database: RaceManagerDatabase,
        *,
        refresh_interval_seconds: float = 3600.0,
    ) -> None:
        self.database = database
        self._refresh_interval = refresh_interval_seconds
        self._rounds: dict[int, RoundLabel] = {}
        self._loaded_at: float = 0.0

    def _ensure_loaded(self) -> None:
        now = time.monotonic()
        if self._rounds and (now - self._loaded_at) < self._refresh_interval:
            return
        try:
            rows: list[dict[str, Any]] = self.database.fetch_all(queries.REF_ROUNDS)
        except Exception:
            if not self._rounds:
                self._rounds = dict(_FALLBACK_ROUNDS)
                self._loaded_at = now
            return

        rounds: dict[int, RoundLabel] = {}
        for row in rows:
            round_type_id = row.get("round_type_id")
            if round_type_id is None:
                continue
            rounds[int(round_type_id)] = RoundLabel(
                round_type_id=int(round_type_id),
                name=(row.get("round_name") or "").strip() or "Unknown",
                round_type=(row.get("round_type") or "").strip(),
                description=(row.get("description") or "").strip(),
            )
        if rounds:
            self._rounds = rounds
            self._loaded_at = now
        elif not self._rounds:
            self._rounds = dict(_FALLBACK_ROUNDS)
            self._loaded_at = now

    def resolve(self, round_type_id: int) -> RoundLabel:
        self._ensure_loaded()
        return self._rounds.get(
            round_type_id,
            _FALLBACK_ROUNDS.get(
                round_type_id,
                RoundLabel(round_type_id, "Unknown", "", "Unknown"),
            ),
        )

    def round_name(self, round_type_id: int) -> str:
        return self.resolve(round_type_id).name

    def is_moto(self, round_type_id: int) -> bool:
        return round_type_id == MOTO_ROUND_TYPE_ID

    def moto_label(self, moto_index: int, total_motos: int | None = None) -> str:
        """Label for one qualifying moto, e.g. "Moto 2" or "Moto 2 of 3".

        Never returns a "Round N" style label -- RaceManager only ever calls
        this phase "Moto" (Ref.Rounds Round_DBID 123), regardless of how many
        physical motos a class runs.
        """
        if total_motos:
            return f"Moto {moto_index} of {total_motos}"
        return f"Moto {moto_index}"
