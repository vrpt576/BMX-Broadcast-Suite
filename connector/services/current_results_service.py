"""Official RaceManager results, historic-event catalogs, and safe caching."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import threading
from uuid import UUID

from connector.models import (
    CompetitionStage,
    CurrentResults,
    FinalizationMethod,
    Moto,
    RacePhase,
    RaceStage,
    ResultRider,
    ScoringMethod,
)
from connector.services.current_lineup_service import CurrentLineupService, DEMO_MOTO
from connector.services.current_moto_service import CurrentMotoService
from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService
from connector.services.race_slot_service import RaceSlotService

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
        self.slots = RaceSlotService(motos)
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
                    race_phase=RacePhase.MAIN,
                    phase_label="Main",
                    round_index=lineup.round_index or 1,
                    motoboard_id=None,
                    event_name="DEMO DATA - BBS Showcase",
                    source="demo",
                )
            else:
                board_id = selected_board_id or self.events.current().motoboard_id
                if hasattr(self.motos, "resolve_state"):
                    resolved = self.motos.resolve_state(board_id, state)
                    stage = resolved.stage
                    moto = (
                        self.motos.get_group(board_id, stage.result_motogroup_id)
                        if stage.result_motogroup_id is not None
                        else resolved.moto
                    )
                    race_phase = resolved.stage.phase
                    phase_label = self._result_label(stage)
                    round_index = stage.result_round_index or stage.round_index
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
                    competition_stage=stage.competition_stage,
                    scoring_method=stage.scoring_method,
                    finalization_method=stage.finalization_method,
                    display_moto_number=stage.moto_number,
                )
                if state.slot_key and state.class_name:
                    result = result.model_copy(
                        update={"class_name": state.class_name}
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
        """Return cached official Main results in ascending moto order."""
        with self._lock:
            cached = self._catalogs.get(motoboard_id)
            if cached is not None and not refresh:
                return [item.model_copy(deep=True) for item in cached]

        all_motos = self.motos.list_motos(motoboard_id, round_type_id=None).motos
        name = event_name or self._event_name(motoboard_id)
        slots = self.slots.catalog_from_motos(
            motoboard_id,
            RacePhase.MAIN,
            all_motos,
        )
        by_group = {moto.motogroup_id: moto for moto in all_motos}
        results: list[CurrentResults] = []
        for slot in slots:
            member_results: list[CurrentResults] = []
            for member in slot.members:
                stage = member.stage
                result_group_id = stage.result_motogroup_id or stage.motogroup_id
                result_moto = by_group.get(result_group_id)
                if result_moto is None:
                    continue
                member_results.append(
                    self._build_result(
                    result_moto,
                    race_phase=RacePhase.MAIN,
                    phase_label=self._result_label(stage),
                    round_index=stage.result_round_index or stage.round_index,
                    motoboard_id=motoboard_id,
                    event_name=name,
                    source="racemanager",
                    competition_stage=stage.competition_stage,
                    scoring_method=stage.scoring_method,
                    finalization_method=stage.finalization_method,
                    display_moto_number=slot.moto_number,
                )
                )
            available = [
                result
                for result in member_results
                if result.result_status != "unavailable"
            ]
            if not available:
                logger.warning(
                    "Skipping results for moto %s (%s): no official finish values.",
                    slot.moto_number,
                    slot.class_name,
                )
                continue
            results.append(self._combine_slot_results(slot.class_name, available))

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

    @staticmethod
    def _combine_slot_results(
        class_name: str,
        results: list[CurrentResults],
    ) -> CurrentResults:
        """Merge combined classification rows into one displayed result."""
        first = results[0]
        unique = {}
        for result in results:
            for rider in result.riders:
                key = (
                    str(rider.bike_number or ""),
                    rider.first_name.casefold(),
                    rider.last_name.casefold(),
                )
                unique.setdefault(key, rider)
        riders = sorted(
            unique.values(),
            key=lambda rider: (
                rider.finish is None,
                rider.finish if rider.finish is not None else 999,
                rider.status != "Did Not Race",
                rider.last_name,
            ),
        )
        status = (
            "official"
            if all(result.result_status == "official" for result in results)
            else "incomplete"
        )
        return first.model_copy(
            update={
                "class_name": class_name,
                "riders": riders,
                "result_status": status,
                "updated_at": max(
                    (
                        result.updated_at
                        for result in results
                        if result.updated_at is not None
                    ),
                    default=first.updated_at,
                ),
            }
        )

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
        competition_stage: CompetitionStage = CompetitionStage.UNKNOWN,
        scoring_method: ScoringMethod = ScoringMethod.UNKNOWN,
        finalization_method: FinalizationMethod = FinalizationMethod.UNKNOWN,
        display_moto_number: int | None = None,
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
                    age=rider.age,
                    home_track=rider.home_track,
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
            moto_number=display_moto_number or moto.moto_number,
            race_phase=race_phase,
            phase_label=phase_label,
            available_phases=[race_phase],
            motoboard_id=motoboard_id,
            class_id=moto.class_id,
            round_type_id=moto.round_type_id,
            round_id=moto.round_id,
            motogroup_id=moto.motogroup_id,
            round_index=round_index,
            competition_stage=competition_stage,
            scoring_method=scoring_method,
            finalization_method=finalization_method,
            class_name=moto.class_name,
            riders=riders,
            source=source,
            updated_at=moto.updated_at,
            result_status=result_status,
        )

    @staticmethod
    def _result_label(stage: RaceStage) -> str:
        if stage.finalization_method == FinalizationMethod.ACCUMULATED_POINTS:
            return "Total Points Results"
        return "Main"

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
