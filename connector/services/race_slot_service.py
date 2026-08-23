"""Unique race-slot catalog shared by navigation and results playback."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from connector.models import (
    CompetitionStage,
    FinalizationMethod,
    Moto,
    RacePhase,
    RaceSlot,
    RaceSlotMember,
    ScoringMethod,
)
from connector.services.motoboard_service import MotoboardService, _lane_present
from connector.services.phase_classification_service import (
    classify_event_finals,
    resolve_main_program_boundary,
)


ROUND_PHASES = {
    RacePhase.ROUND_1: (1, "Round 1"),
    RacePhase.ROUND_2: (2, "Round 2"),
    RacePhase.ROUND_3: (3, "Main"),
}


class RaceSlotService:
    """Collapse class rows into one position per displayed phase/moto."""

    def __init__(self, motoboards: MotoboardService) -> None:
        self.motoboards = motoboards

    def catalog(self, motoboard_id: UUID, phase: RacePhase) -> list[RaceSlot]:
        motos = self.motoboards.list_motos(
            motoboard_id,
            round_type_id=None,
        ).motos
        return self.catalog_from_motos(motoboard_id, phase, motos)

    def catalog_from_motos(
        self,
        motoboard_id: UUID,
        phase: RacePhase,
        motos: list[Moto],
    ) -> list[RaceSlot]:
        by_class: dict[UUID, list[Moto]] = defaultdict(list)
        for moto in motos:
            by_class[moto.class_id].append(moto)

        decisions = classify_event_finals(
            motoboard_id,
            motos,
            getattr(self.motoboards, "phase_overrides", None),
        )
        main_boundary = resolve_main_program_boundary(
            motoboard_id,
            motos,
            decisions,
            getattr(self.motoboards, "phase_overrides", None),
        )

        members_by_number: dict[int, list[RaceSlotMember]] = defaultdict(list)
        for class_id, class_motos in by_class.items():
            qualifiers = sorted(
                [moto for moto in class_motos if moto.round_type_id == 123],
                key=lambda moto: (
                    moto.moto_number,
                    moto.motogroup_number,
                    str(moto.motogroup_id),
                ),
            )
            finals = sorted(
                [moto for moto in class_motos if moto.round_type_id == 1],
                key=lambda moto: (
                    moto.moto_number,
                    moto.motogroup_number,
                    str(moto.motogroup_id),
                ),
            )

            final = finals[0] if finals else None
            decision = decisions[class_id]
            total_points_in_main = bool(
                final
                and main_boundary.start_moto is not None
                and final.moto_number >= main_boundary.start_moto
            )

            if phase in ROUND_PHASES:
                round_index, label = ROUND_PHASES[phase]
                if round_index == 3 and decision.scoring_method == ScoringMethod.TOTAL_POINTS:
                    if total_points_in_main or final is None:
                        continue
                    third_moto = next(
                        (
                            qualifier
                            for qualifier in qualifiers
                            if any(_lane_present(rider.lane_3) for rider in qualifier.riders)
                        ),
                        final,
                    )
                    third_index = 3 if third_moto.round_type_id == 123 else 1
                    stage = MotoboardService._stage(
                        third_moto,
                        phase=RacePhase.ROUND_3,
                        label=label,
                        kind=CompetitionStage.TOTAL_POINTS_FINAL_MOTO.value,
                        round_index=third_index,
                        competition_stage=CompetitionStage.TOTAL_POINTS_FINAL_MOTO,
                        scoring_method=ScoringMethod.TOTAL_POINTS,
                        finalization_method=FinalizationMethod.ACCUMULATED_POINTS,
                        result_round_type_id=final.round_type_id,
                        result_round_id=final.round_id,
                        result_motogroup_id=final.motogroup_id,
                        result_round_index=1,
                        classification_reason=decision.reason,
                        classification_ambiguous=decision.ambiguous,
                        classification_overridden=decision.overridden,
                    )
                    members_by_number[stage.moto_number].append(
                        RaceSlotMember(
                            stage=stage,
                            qualifier_motogroup_id=(
                                third_moto.motogroup_id
                                if third_moto.round_type_id == 123
                                else (qualifiers[0].motogroup_id if qualifiers else None)
                            ),
                        )
                    )
                    continue
                for qualifier in qualifiers:
                    if not any(
                        _lane_present(getattr(rider, f"lane_{round_index}"))
                        for rider in qualifier.riders
                    ):
                        continue
                    stage = MotoboardService._stage(
                        qualifier,
                        phase=phase,
                        label=label,
                        kind="qualifier",
                        round_index=round_index,
                        competition_stage={
                            1: CompetitionStage.QUALIFYING_MOTO_1,
                            2: CompetitionStage.QUALIFYING_MOTO_2,
                            3: CompetitionStage.QUALIFYING_MOTO_3,
                        }[round_index],
                        scoring_method=decision.scoring_method,
                        finalization_method=decision.finalization_method,
                    )
                    members_by_number[stage.moto_number].append(
                        RaceSlotMember(
                            stage=stage,
                            qualifier_motogroup_id=qualifier.motogroup_id,
                        )
                    )
                continue

            if phase != RacePhase.MAIN or final is None:
                continue
            if decision.finalization_method == FinalizationMethod.ACCUMULATED_POINTS:
                if not total_points_in_main:
                    continue
                third_moto = next(
                    (
                        qualifier
                        for qualifier in qualifiers
                        if any(_lane_present(rider.lane_3) for rider in qualifier.riders)
                    ),
                    final,
                )
                third_index = 3 if third_moto.round_type_id == 123 else 1
                stage = MotoboardService._stage(
                    third_moto,
                    phase=RacePhase.MAIN,
                    label=self.motoboards.round_labels.round_name(1),
                    kind=CompetitionStage.TOTAL_POINTS_FINAL_MOTO.value,
                    round_index=third_index,
                    competition_stage=CompetitionStage.TOTAL_POINTS_FINAL_MOTO,
                    scoring_method=ScoringMethod.TOTAL_POINTS,
                    finalization_method=FinalizationMethod.ACCUMULATED_POINTS,
                    result_round_type_id=final.round_type_id,
                    result_round_id=final.round_id,
                    result_motogroup_id=final.motogroup_id,
                    result_round_index=1,
                    classification_reason=decision.reason,
                    classification_ambiguous=decision.ambiguous,
                    classification_overridden=decision.overridden,
                )
            else:
                stage = MotoboardService._stage(
                    final,
                    phase=RacePhase.MAIN,
                    label=self.motoboards.round_labels.round_name(1),
                    kind=CompetitionStage.MAIN_EVENT.value,
                    round_index=1,
                    competition_stage=CompetitionStage.MAIN_EVENT,
                    scoring_method=decision.scoring_method,
                    finalization_method=decision.finalization_method,
                    result_round_type_id=final.round_type_id,
                    result_round_id=final.round_id,
                    result_motogroup_id=final.motogroup_id,
                    result_round_index=1,
                    classification_reason=decision.reason,
                    classification_ambiguous=decision.ambiguous,
                    classification_overridden=decision.overridden,
                )
            qualifier_id = next(
                (
                    qualifier.motogroup_id
                    for qualifier in qualifiers
                    if qualifier.moto_number == final.moto_number
                ),
                qualifiers[0].motogroup_id if qualifiers else None,
            )
            members_by_number[stage.moto_number].append(
                RaceSlotMember(
                    stage=stage,
                    qualifier_motogroup_id=qualifier_id,
                )
            )

        slots: list[RaceSlot] = []
        for moto_number, raw_members in members_by_number.items():
            members = self._unique_members(raw_members)
            class_pairs = sorted(
                {(item.stage.class_id, item.stage.class_name) for item in members},
                key=lambda item: (item[1], str(item[0])),
            )
            group_ids = sorted(
                {item.stage.motogroup_id for item in members}, key=str
            )
            slots.append(
                RaceSlot(
                    slot_key=f"{motoboard_id}:{phase.value}:{moto_number}",
                    motoboard_id=motoboard_id,
                    phase=phase,
                    phase_label=members[0].stage.label,
                    moto_number=moto_number,
                    combined=len(class_pairs) > 1,
                    class_name=" / ".join(name for _, name in class_pairs),
                    class_ids=[class_id for class_id, _ in class_pairs],
                    motogroup_ids=group_ids,
                    members=members,
                )
            )
        return sorted(slots, key=lambda slot: (slot.moto_number, slot.slot_key))

    @staticmethod
    def _unique_members(members: list[RaceSlotMember]) -> list[RaceSlotMember]:
        unique: dict[tuple[UUID, UUID], RaceSlotMember] = {}
        for member in members:
            key = (member.stage.class_id, member.stage.motogroup_id)
            unique.setdefault(key, member)
        return sorted(
            unique.values(),
            key=lambda member: (
                member.stage.class_name,
                str(member.stage.class_id),
                str(member.stage.motogroup_id),
            ),
        )
