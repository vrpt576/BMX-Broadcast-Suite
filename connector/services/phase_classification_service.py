"""Interpret RaceManager final records without inventing navigation phases."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Protocol
from uuid import UUID

from connector.models import (
    CompetitionStage,
    FinalizationMethod,
    MainProgramBoundary,
    MainProgramBoundaryConfidence,
    MainProgramBoundarySource,
    Moto,
    ProgramSegment,
    ScoringMethod,
)


_OVERRIDE_FILE_LOCK = RLock()


@dataclass(frozen=True)
class FinalClassificationDecision:
    """Scoring metadata for a class's Round_Type_ID 1 record.

    ``program_segment`` is Main for every physical final-program occurrence.
    An accumulated-points classification describes official results; it is
    never an operator-facing Overall segment.
    """

    scoring_method: ScoringMethod
    finalization_method: FinalizationMethod
    competition_stage: CompetitionStage
    reason: str
    ambiguous: bool = False
    overridden: bool = False

    @property
    def program_segment(self) -> ProgramSegment | None:
        if self.finalization_method == FinalizationMethod.UNKNOWN:
            return None
        return ProgramSegment.MAIN


class PhaseClassificationOverrideStore:
    """Read narrowly scoped event/class finalization overrides.

    Existing ``main`` / ``overall`` override files remain compatible.  The
    legacy words are translated to finalization methods and never returned as
    navigation phases.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lock = _OVERRIDE_FILE_LOCK

    def _read(self) -> dict[str, object]:
        if self.path is None or not self.path.exists():
            return {"version": 1, "events": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Race phase override file must contain a JSON object.")
        payload.setdefault("version", 1)
        payload.setdefault("events", {})
        return payload

    def _write(self, payload: dict[str, object]) -> None:
        if self.path is None:
            raise ValueError("A phase override file is required to save a boundary.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def get_main_program_start(self, motoboard_id: UUID) -> int | None:
        with self._lock:
            event = self._read().get("events", {}).get(str(motoboard_id), {})
        value = event.get("main_program_start_moto")
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(
                f"Invalid Main program start {value!r} for motoboard {motoboard_id}."
            )
        return value

    def set_main_program_start(
        self,
        motoboard_id: UUID,
        start_moto: int | None,
    ) -> None:
        invalid_start = (
            isinstance(start_moto, bool)
            or not isinstance(start_moto, int)
            or start_moto < 1
        )
        if start_moto is not None and invalid_start:
            raise ValueError("Main program start must be a positive whole-number moto.")
        with self._lock:
            payload = self._read()
            events = payload.setdefault("events", {})
            event = events.setdefault(str(motoboard_id), {})
            if start_moto is None:
                event.pop("main_program_start_moto", None)
                if not event:
                    events.pop(str(motoboard_id), None)
            else:
                event["main_program_start_moto"] = start_moto
            self._write(payload)

    def get(
        self,
        motoboard_id: UUID,
        class_id: UUID,
        motogroup_id: UUID | None,
    ) -> FinalizationMethod | None:
        if self.path is None or not self.path.exists():
            return None
        with self._lock:
            payload = self._read()
            event = payload.get("events", {}).get(str(motoboard_id), {})
        value = None
        if motogroup_id is not None:
            value = event.get("motogroups", {}).get(str(motogroup_id))
        if value is None:
            value = event.get("classes", {}).get(str(class_id))
        if value is None:
            return None
        normalized = str(value).strip().lower()
        aliases = {
            "main": FinalizationMethod.FINAL_RACE,
            "final_race": FinalizationMethod.FINAL_RACE,
            "overall": FinalizationMethod.ACCUMULATED_POINTS,
            "accumulated_points": FinalizationMethod.ACCUMULATED_POINTS,
            "total_points": FinalizationMethod.ACCUMULATED_POINTS,
        }
        try:
            return aliases[normalized]
        except KeyError as exc:
            raise ValueError(
                f"Invalid finalization override {value!r} for motoboard "
                f"{motoboard_id}, class {class_id}."
            ) from exc


class _OverrideReader(Protocol):
    def get(
        self,
        motoboard_id: UUID,
        class_id: UUID,
        motogroup_id: UUID | None,
    ) -> FinalizationMethod | None: ...


def classify_event_finals(
    motoboard_id: UUID,
    motos: list[Moto],
    override_store: _OverrideReader | None = None,
) -> dict[UUID, FinalClassificationDecision]:
    """Classify every final record with event-level combined-moto evidence."""
    by_class: dict[UUID, list[Moto]] = defaultdict(list)
    final_classes_by_number: dict[int, set[UUID]] = defaultdict(set)
    for moto in motos:
        by_class[moto.class_id].append(moto)
        if moto.round_type_id == 1:
            final_classes_by_number[moto.moto_number].add(moto.class_id)

    decisions: dict[UUID, FinalClassificationDecision] = {}
    for class_id, class_motos in by_class.items():
        qualifiers = [moto for moto in class_motos if moto.round_type_id == 123]
        finals = [moto for moto in class_motos if moto.round_type_id == 1]
        final = finals[0] if finals else None
        override = (
            override_store.get(
                motoboard_id,
                class_id,
                final.motogroup_id if final else None,
            )
            if override_store is not None and final is not None
            else None
        )
        decisions[class_id] = classify_final(
            qualifiers,
            finals,
            combined_final=bool(
                final
                and len(final_classes_by_number[final.moto_number]) > 1
            ),
            override=override,
        )
    return decisions


def resolve_main_program_boundary(
    motoboard_id: UUID,
    motos: list[Moto],
    decisions: dict[UUID, FinalClassificationDecision],
    override_store: PhaseClassificationOverrideStore | None = None,
) -> MainProgramBoundary:
    """Resolve the scheduled Main block without inventing a SQL-backed fact.

    RaceManager's validated structural fields describe classes, branches, and
    scoring, but none identifies the event-wide point where the Main program
    begins.  Transfer finals are therefore exposed only as a low-confidence
    suggestion.  An event-scoped operator boundary is the sole authoritative
    fallback and never writes to RaceManager.
    """
    transfer_main_numbers = sorted(
        {
            moto.moto_number
            for moto in motos
            if moto.round_type_id == 1
            and decisions.get(moto.class_id) is not None
            and decisions[moto.class_id].finalization_method
            == FinalizationMethod.FINAL_RACE
        }
    )
    suggested = min(transfer_main_numbers) if transfer_main_numbers else None
    evidence = ["race_manager_main_program_start_field:not_available"]
    if transfer_main_numbers:
        evidence.append(
            "transfer_final_motos:"
            + ",".join(str(value) for value in transfer_main_numbers)
        )
        evidence.append("transfer_final_start_is_suggestion_only")
    else:
        evidence.append("transfer_final_motos:none")

    start_moto = (
        override_store.get_main_program_start(motoboard_id)
        if override_store is not None
        else None
    )
    if start_moto is not None:
        evidence.insert(0, f"operator_confirmed_main_program_start:{start_moto}")
        return MainProgramBoundary(
            motoboard_id=motoboard_id,
            start_moto=start_moto,
            source=MainProgramBoundarySource.OPERATOR_OVERRIDE,
            confidence=MainProgramBoundaryConfidence.CONFIRMED,
            suggested_start_moto=suggested,
            evidence=evidence,
        )
    return MainProgramBoundary(
        motoboard_id=motoboard_id,
        source=MainProgramBoundarySource.UNRESOLVED,
        confidence=(
            MainProgramBoundaryConfidence.LOW
            if suggested is not None
            else MainProgramBoundaryConfidence.NONE
        ),
        suggested_start_moto=suggested,
        evidence=evidence,
    )


def _is_transfer(value: object) -> bool:
    return isinstance(value, str) and value.strip().upper() == "X"


def _is_numeric_finish(value: object) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return value > 0
    return isinstance(value, str) and value.strip().isdigit()


def classify_final(
    qualifiers: list[Moto],
    finals: list[Moto],
    *,
    combined_final: bool = False,
    override: FinalizationMethod | None = None,
) -> FinalClassificationDecision:
    """Classify scoring/finalization independently from program navigation."""
    if not finals:
        return FinalClassificationDecision(
            ScoringMethod.UNKNOWN,
            FinalizationMethod.UNKNOWN,
            CompetitionStage.UNKNOWN,
            "no_round_type_1_classification",
        )

    if override is not None:
        accumulated = override == FinalizationMethod.ACCUMULATED_POINTS
        return FinalClassificationDecision(
            ScoringMethod.TOTAL_POINTS if accumulated else ScoringMethod.TRANSFER,
            override,
            (
                CompetitionStage.TOTAL_POINTS_CLASSIFICATION
                if accumulated
                else CompetitionStage.MAIN_EVENT
            ),
            "event_specific_operator_override",
            overridden=True,
        )

    qualifier_riders = {rider.rider_id for moto in qualifiers for rider in moto.riders}
    final_riders = {rider.rider_id for moto in finals for rider in moto.riders}
    has_transfer_markers = any(
        _is_transfer(value)
        for moto in qualifiers
        for rider in moto.riders
        for value in (rider.finish_1, rider.finish_2, rider.finish_3)
    )
    scored_rounds = max(
        (
            sum(
                any(
                    _is_numeric_finish(getattr(rider, f"finish_{index}"))
                    for rider in moto.riders
                )
                for index in (1, 2, 3)
            )
            for moto in qualifiers
        ),
        default=0,
    )
    qualifier_numbers = {moto.moto_number for moto in qualifiers}
    final_numbers = {moto.moto_number for moto in finals}

    final_race_reason: str | None = None
    if combined_final:
        final_race_reason = "multiple_classes_share_final_moto"
    elif not qualifiers:
        final_race_reason = "standalone_final_without_qualifier_branch"
    elif len(qualifiers) > 1:
        final_race_reason = "multiple_qualifier_motogroups_feed_final"
    elif has_transfer_markers:
        final_race_reason = "qualifier_transfer_marker"
    elif qualifier_riders and final_riders != qualifier_riders:
        final_race_reason = "final_rider_set_differs_from_qualifiers"
    elif final_numbers.isdisjoint(qualifier_numbers):
        final_race_reason = "final_uses_separate_displayed_moto"

    if final_race_reason is not None:
        return FinalClassificationDecision(
            ScoringMethod.TRANSFER,
            FinalizationMethod.FINAL_RACE,
            CompetitionStage.MAIN_EVENT,
            final_race_reason,
        )

    if qualifier_riders == final_riders and scored_rounds >= 2:
        return FinalClassificationDecision(
            ScoringMethod.TOTAL_POINTS,
            FinalizationMethod.ACCUMULATED_POINTS,
            CompetitionStage.TOTAL_POINTS_CLASSIFICATION,
            "same_riders_with_accumulated_round_scores",
        )

    return FinalClassificationDecision(
        ScoringMethod.TOTAL_POINTS,
        FinalizationMethod.ACCUMULATED_POINTS,
        CompetitionStage.TOTAL_POINTS_CLASSIFICATION,
        "ambiguous_same_slot_same_riders_defaulted_to_total_points",
        ambiguous=True,
    )
