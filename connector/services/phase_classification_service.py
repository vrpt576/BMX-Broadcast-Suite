"""Deterministic interpretation of RaceManager final classifications."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from connector.models import Moto, RacePhase


class FinalClassification(StrEnum):
    NONE = "none"
    MAIN = "main"
    OVERALL = "overall"


@dataclass(frozen=True)
class FinalClassificationDecision:
    classification: FinalClassification
    reason: str
    ambiguous: bool = False
    overridden: bool = False

    @property
    def phase(self) -> RacePhase | None:
        if self.classification == FinalClassification.MAIN:
            return RacePhase.MAIN
        if self.classification == FinalClassification.OVERALL:
            return RacePhase.OVERALL
        return None


class PhaseClassificationOverrideStore:
    """Read narrowly scoped event/class overrides from a local JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path

    def get(
        self,
        motoboard_id: UUID,
        class_id: UUID,
        motogroup_id: UUID | None,
    ) -> FinalClassification | None:
        if self.path is None or not self.path.exists():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        event = payload.get("events", {}).get(str(motoboard_id), {})
        value = None
        if motogroup_id is not None:
            value = event.get("motogroups", {}).get(str(motogroup_id))
        if value is None:
            value = event.get("classes", {}).get(str(class_id))
        if value is None:
            return None
        try:
            return FinalClassification(str(value).strip().lower())
        except ValueError as exc:
            raise ValueError(
                f"Invalid final classification override {value!r} for "
                f"motoboard {motoboard_id}, class {class_id}."
            ) from exc


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
    override: FinalClassification | None = None,
) -> FinalClassificationDecision:
    """Classify a RaceManager Round_Type_ID 1 record using stable evidence.

    RaceManager uses the same round type for separately raced finals and
    accumulated-points classifications.  The order below prefers an exact
    operator override, then explicit structural evidence, then scored-round
    evidence.  Only the last same-slot/same-rider shape remains ambiguous.
    """
    if override is not None:
        return FinalClassificationDecision(
            override,
            "event_specific_operator_override",
            overridden=True,
        )
    if not finals:
        return FinalClassificationDecision(
            FinalClassification.NONE,
            "no_round_type_1_classification",
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

    if combined_final:
        return FinalClassificationDecision(
            FinalClassification.MAIN,
            "multiple_classes_share_final_moto",
        )
    if not qualifiers:
        return FinalClassificationDecision(
            FinalClassification.MAIN,
            "standalone_final_without_qualifier_branch",
        )
    if len(qualifiers) > 1:
        return FinalClassificationDecision(
            FinalClassification.MAIN,
            "multiple_qualifier_motogroups_feed_final",
        )
    if has_transfer_markers:
        return FinalClassificationDecision(
            FinalClassification.MAIN,
            "qualifier_transfer_marker",
        )
    if qualifier_riders and final_riders != qualifier_riders:
        return FinalClassificationDecision(
            FinalClassification.MAIN,
            "final_rider_set_differs_from_qualifiers",
        )
    if final_numbers.isdisjoint(qualifier_numbers):
        return FinalClassificationDecision(
            FinalClassification.MAIN,
            "final_uses_separate_displayed_moto",
        )
    if qualifier_riders == final_riders and scored_rounds >= 2:
        return FinalClassificationDecision(
            FinalClassification.OVERALL,
            "same_riders_with_accumulated_round_scores",
        )

    return FinalClassificationDecision(
        FinalClassification.OVERALL,
        "ambiguous_same_slot_same_riders_defaulted_to_overall",
        ambiguous=True,
    )
