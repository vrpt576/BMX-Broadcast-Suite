"""Official RaceManager results, historic-event catalogs, and safe caching."""

from __future__ import annotations

from collections import defaultdict
import json
import logging
import os
from pathlib import Path
import threading
from uuid import UUID

from connector.models import CurrentResults, Moto, RacePhase, ResultRider
from connector.services.current_lineup_service import CurrentLineupService, DEMO_MOTO
from connector.services.current_moto_service import CurrentMotoService
from connector.services.event_service import EventService
from connector.services.motoboard_service import (
    MotoboardService,
    is_main_classification,
)

logger = logging.getLogger(__name__)


class CurrentResultsService:
    """Build results only from RaceManager finish/classification fields."""

    def __init__(
        self,
        current: CurrentMotoService,
        events: EventService,
        motos: MotoboardService,
        lineups: CurrentLineupService,
        cache_file: Path | None = None,
    ) -> None:
        self.current = current
        self.events = events
        self.motos = motos
        self.lineups = lineups
        self.cache_file = cache_file or current.state_file.parent / "last_known_results.json"
        self._catalogs: dict[UUID, list[CurrentResults]] = {}
        self._lock = threading.RLock()

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
                result = self._build_result(
                    DEMO_MOTO,
                    race_phase=lineup.race_phase,
                    phase_label=lineup.phase_label or "Round 1",
                    round_index=lineup.round_index or 1,
                    motoboard_id=None,
                    event_name="Demo Event",
                    source="demo",
                )
            else:
                board_id = selected_board_id or self.events.current().motoboard_id
                if hasattr(self.motos, "resolve_state"):
                    resolved = self.motos.resolve_state(board_id, state)
                    moto = resolved.moto
                    race_phase = resolved.stage.phase
                    phase_label = resolved.stage.label
                    round_index = resolved.stage.round_index
                else:  # compatibility with older adapters and test doubles
                    moto = self.motos.get_moto(board_id, state.moto_number)
                    stage, _program = CurrentLineupService._legacy_context(
                        state, moto, board_id
                    )
                    race_phase = stage.phase
                    phase_label = stage.label
                    round_index = stage.round_index
                event_name = self._event_name(board_id)
                result = self._build_result(
                    moto,
                    race_phase=race_phase,
                    phase_label=phase_label,
                    round_index=round_index,
                    motoboard_id=board_id,
                    event_name=event_name,
                    source="racemanager",
                )
            self._write_cache(result)
            return result
        except Exception as exc:
            cached = self._read_cache(selected_board_id)
            if cached is None:
                raise
            return cached.model_copy(
                update={"source": "cache", "is_stale": True, "warning": str(exc)}
            )

    def catalog(
        self,
        motoboard_id: UUID,
        *,
        event_name: str | None = None,
        refresh: bool = False,
    ) -> list[CurrentResults]:
        """Return cached official final/overall results in moto order."""
        with self._lock:
            cached = self._catalogs.get(motoboard_id)
            if cached is not None and not refresh:
                return [item.model_copy(deep=True) for item in cached]

        all_motos = self.motos.list_motos(motoboard_id, round_type_id=None).motos
        qualifiers: dict[UUID, list[Moto]] = defaultdict(list)
        finals: list[Moto] = []
        for moto in all_motos:
            if moto.round_type_id == 123:
                qualifiers[moto.class_id].append(moto)
            elif moto.round_type_id == 1:
                finals.append(moto)

        name = event_name or self._event_name(motoboard_id)
        results: list[CurrentResults] = []
        qualifier_order = sorted(
            (moto for motos in qualifiers.values() for moto in motos),
            key=lambda item: (
                item.moto_number,
                item.motogroup_number,
                str(item.motogroup_id),
            ),
        )
        for round_index, phase, label in (
            (1, RacePhase.ROUND_1, "Round 1"),
            (2, RacePhase.ROUND_2, "Round 2"),
            (3, RacePhase.ROUND_3, "Round 3"),
        ):
            for qualifier in qualifier_order:
                result = self._build_result(
                    qualifier,
                    race_phase=phase,
                    phase_label=label,
                    round_index=round_index,
                    motoboard_id=motoboard_id,
                    event_name=name,
                    source="racemanager",
                )
                if result.result_status == "unavailable":
                    logger.info(
                        "Skipping %s results for moto %s (%s): no official finish values.",
                        label,
                        qualifier.moto_number,
                        qualifier.class_name,
                    )
                    continue
                results.append(result)

        for final in sorted(
            finals,
            key=lambda item: (item.moto_number, item.motogroup_number, str(item.motogroup_id)),
        ):
            phase = (
                RacePhase.MAIN
                if is_main_classification(qualifiers[final.class_id], final)
                else RacePhase.OVERALL
            )
            result = self._build_result(
                final,
                race_phase=phase,
                phase_label="Main" if phase == RacePhase.MAIN else "Overall",
                round_index=1,
                motoboard_id=motoboard_id,
                event_name=name,
                source="racemanager",
            )
            if result.result_status == "unavailable":
                logger.warning(
                    "Skipping results for moto %s (%s): no official finish values.",
                    final.moto_number,
                    final.class_name,
                )
                continue
            results.append(result)

        total = len(results)
        results = [
            item.model_copy(
                update={"progress_index": index, "progress_total": total}
            )
            for index, item in enumerate(results, 1)
        ]
        with self._lock:
            self._catalogs[motoboard_id] = results
        return [item.model_copy(deep=True) for item in results]

    def _event_name(self, motoboard_id: UUID) -> str | None:
        try:
            return self.events.by_motoboard(motoboard_id).event_name
        except (AttributeError, LookupError):
            return None

    @classmethod
    def _build_result(
        cls,
        moto: Moto,
        *,
        race_phase: RacePhase,
        phase_label: str,
        round_index: int,
        motoboard_id: UUID | None,
        event_name: str | None,
        source: str,
    ) -> CurrentResults:
        riders: list[ResultRider] = []
        official_count = 0
        completed_count = 0
        field = f"finish_{round_index}"
        for rider in moto.riders:
            finish, transferred, status = cls._normalize_finish(getattr(rider, field, None))
            if finish is not None:
                official_count += 1
                completed_count += 1
            elif rider.did_not_race:
                status = "Did Not Race"
                completed_count += 1
            elif status is not None:
                completed_count += 1
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
                rider.status != "Did Not Race",
                rider.last_name,
            )
        )
        if official_count == 0:
            result_status = "unavailable"
        elif completed_count == len(riders):
            result_status = "official"
        else:
            result_status = "incomplete"
        return CurrentResults(
            event_name=event_name,
            moto_number=moto.moto_number,
            race_phase=race_phase,
            phase_label=phase_label,
            available_phases=[race_phase],
            motoboard_id=motoboard_id,
            class_id=moto.class_id,
            round_type_id=moto.round_type_id,
            round_id=moto.round_id,
            motogroup_id=moto.motogroup_id,
            round_index=round_index,
            class_name=moto.class_name,
            riders=riders,
            source=source,
            updated_at=moto.updated_at,
            result_status=result_status,
        )

    def _write_cache(self, result: CurrentResults) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_file.with_suffix(self.cache_file.suffix + ".tmp")
        temporary.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.cache_file)

    def _read_cache(self, motoboard_id: UUID | None) -> CurrentResults | None:
        try:
            result = CurrentResults.model_validate_json(
                self.cache_file.read_text(encoding="utf-8")
            )
            if motoboard_id is not None and result.motoboard_id != motoboard_id:
                return None
            return result
        except (OSError, ValueError):
            return None

    @staticmethod
    def _normalize_finish(value: object) -> tuple[int | None, bool, str | None]:
        if value is None:
            return None, False, None
        if isinstance(value, bool):
            return None, False, None
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
