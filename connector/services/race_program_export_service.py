"""Privacy-safe RaceManager race-program structure export."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from database import queries
from database.racemanager import RaceManagerDatabase

from connector.models import (
    CurrentMoto,
    Moto,
    RacePhase,
    RaceProgramClassificationEvidence,
    RaceProgramExportClass,
    RaceProgramExportSlot,
    RaceProgramExportStage,
    RaceProgramSchemaColumn,
    RaceProgramStructureExport,
)
from connector.services.event_service import EventService
from connector.services.motoboard_service import (
    MotoboardService,
    RaceProgramNotFoundError,
)
from connector.services.phase_classification_service import classify_final


PHASE_ORDER = {
    RacePhase.ROUND_1: 1,
    RacePhase.ROUND_2: 2,
    RacePhase.ROUND_3: 3,
    RacePhase.QUARTERFINAL: 4,
    RacePhase.SEMIFINAL: 5,
    RacePhase.MAIN: 6,
    RacePhase.OVERALL: 7,
}


class RaceProgramExportService:
    """Build a shareable structural snapshot without rider personal data."""

    def __init__(
        self,
        database: RaceManagerDatabase,
        events: EventService,
        motoboards: MotoboardService,
    ) -> None:
        self.database = database
        self.events = events
        self.motoboards = motoboards

    def export(self, motoboard_id: UUID | None = None) -> RaceProgramStructureExport:
        event = (
            self.events.by_motoboard(motoboard_id)
            if motoboard_id is not None
            else self.events.current()
        )
        board_id = event.motoboard_id
        motos = self.motoboards.list_motos(board_id, round_type_id=None).motos
        schema_columns = [
            RaceProgramSchemaColumn.model_validate(row)
            for row in self.database.fetch_all(
                queries.PROGRAM_STRUCTURE_SCHEMA_COLUMNS
            )
        ]

        by_class: dict[UUID, list[Moto]] = defaultdict(list)
        final_classes_by_moto: dict[int, set[UUID]] = defaultdict(set)
        for moto in motos:
            by_class[moto.class_id].append(moto)
            if moto.round_type_id == 1:
                final_classes_by_moto[moto.moto_number].add(moto.class_id)

        classes = [
            self._class_export(board_id, class_motos, final_classes_by_moto)
            for _, class_motos in sorted(
                by_class.items(),
                key=lambda item: (
                    min(moto.moto_number for moto in item[1]),
                    item[1][0].class_name,
                    str(item[0]),
                ),
            )
        ]
        slots = self._slots(classes)

        return RaceProgramStructureExport(
            generated_at=datetime.now(timezone.utc),
            event_id=event.event_id,
            event_name=event.event_name,
            event_date=event.date_begin,
            race_id=event.race_id,
            race_description=event.race_description,
            motoboard_id=board_id,
            total_motos=event.total_motos,
            total_riders=event.total_riders,
            schema_columns=schema_columns,
            classes=classes,
            slots=slots,
        )

    def _class_export(
        self,
        motoboard_id: UUID,
        class_motos: list[Moto],
        final_classes_by_moto: dict[int, set[UUID]],
    ) -> RaceProgramExportClass:
        ordered = sorted(
            class_motos,
            key=lambda moto: (
                moto.round_type_id,
                moto.moto_number,
                moto.motogroup_number,
                str(moto.motogroup_id),
            ),
        )
        qualifiers = [moto for moto in ordered if moto.round_type_id == 123]
        finals = [moto for moto in ordered if moto.round_type_id == 1]
        combined_final = any(
            len(final_classes_by_moto[moto.moto_number]) > 1 for moto in finals
        )
        stages: list[RaceProgramExportStage] = []
        seen: set[tuple[RacePhase, UUID, int]] = set()
        seeds = qualifiers or finals

        for seed in seeds:
            state = CurrentMoto(
                moto_number=seed.moto_number,
                race_phase=(
                    RacePhase.ROUND_1
                    if seed.round_type_id == 123
                    else RacePhase.OVERALL
                ),
                motoboard_id=motoboard_id,
                class_id=seed.class_id,
                round_type_id=seed.round_type_id,
                round_id=seed.round_id,
                motogroup_id=seed.motogroup_id,
                qualifier_motogroup_id=(
                    seed.motogroup_id if seed.round_type_id == 123 else None
                ),
            )
            try:
                program = self.motoboards.get_program(motoboard_id, state)
            except RaceProgramNotFoundError:
                continue
            for stage in program.stages:
                key = (stage.phase, stage.motogroup_id, stage.moto_number)
                if key in seen:
                    continue
                seen.add(key)
                stages.append(
                    RaceProgramExportStage(
                        phase=stage.phase,
                        round_label=stage.label,
                        kind=stage.kind,
                        displayed_moto=stage.moto_number,
                        round_type_id=stage.round_type_id,
                        round_id=stage.round_id,
                        motogroup_id=stage.motogroup_id,
                        class_id=stage.class_id,
                        class_name=stage.class_name,
                        round_index=stage.round_index,
                        round_moto_number_first=stage.round_moto_number_first,
                        round_moto_number_last=stage.round_moto_number_last,
                        round_motogroup_count=stage.round_motogroup_count,
                    )
                )

        stages.sort(
            key=lambda stage: (
                PHASE_ORDER[stage.phase],
                stage.displayed_moto,
                str(stage.motogroup_id),
            )
        )
        available_stages = list(dict.fromkeys(stage.phase for stage in stages))
        reference = ordered[0]
        return RaceProgramExportClass(
            class_id=reference.class_id,
            class_name=reference.class_name,
            available_stages=available_stages,
            classification=self._classification_evidence(
                motoboard_id,
                qualifiers,
                finals,
                combined_final=combined_final,
            ),
            stages=stages,
        )

    def _classification_evidence(
        self,
        motoboard_id: UUID,
        qualifiers: list[Moto],
        finals: list[Moto],
        *,
        combined_final: bool,
    ) -> RaceProgramClassificationEvidence:
        qualifier_riders = {
            rider.rider_id for moto in qualifiers for rider in moto.riders
        }
        final_riders = {rider.rider_id for moto in finals for rider in moto.riders}
        has_transfer_markers = any(
            isinstance(value, str) and value.strip().upper() == "X"
            for moto in qualifiers
            for rider in moto.riders
            for value in (rider.finish_1, rider.finish_2, rider.finish_3)
        )

        override = None
        if finals:
            override = self.motoboards.phase_overrides.get(
                motoboard_id,
                finals[0].class_id,
                finals[0].motogroup_id,
            )
        decision = classify_final(
            qualifiers,
            finals,
            combined_final=combined_final,
            override=override,
        )

        return RaceProgramClassificationEvidence(
            qualifier_group_count=len(qualifiers),
            qualifier_rider_count=len(qualifier_riders),
            final_group_count=len(finals),
            final_rider_count=len(final_riders),
            has_transfer_markers=has_transfer_markers,
            rider_sets_equal=(
                qualifier_riders == final_riders
                if qualifier_riders and final_riders
                else None
            ),
            inferred_phase=decision.phase,
            inference_reason=decision.reason,
            ambiguous=decision.ambiguous,
            overridden=decision.overridden,
        )

    @staticmethod
    def _slots(
        classes: list[RaceProgramExportClass],
    ) -> list[RaceProgramExportSlot]:
        grouped: dict[tuple[RacePhase, int], list[RaceProgramExportStage]] = (
            defaultdict(list)
        )
        for class_entry in classes:
            for stage in class_entry.stages:
                grouped[(stage.phase, stage.displayed_moto)].append(stage)

        slots: list[RaceProgramExportSlot] = []
        for (phase, displayed_moto), stages in grouped.items():
            class_pairs = sorted(
                {(stage.class_id, stage.class_name) for stage in stages},
                key=lambda item: (item[1], str(item[0])),
            )
            slots.append(
                RaceProgramExportSlot(
                    slot_key=f"{phase.value}:{displayed_moto}",
                    phase=phase,
                    round_label=stages[0].round_label,
                    displayed_moto=displayed_moto,
                    combined=len(class_pairs) > 1,
                    class_ids=[item[0] for item in class_pairs],
                    class_names=[item[1] for item in class_pairs],
                    round_type_ids=sorted({stage.round_type_id for stage in stages}),
                    round_ids=sorted(
                        {stage.round_id for stage in stages}, key=str
                    ),
                    motogroup_ids=sorted(
                        {stage.motogroup_id for stage in stages}, key=str
                    ),
                )
            )
        return sorted(
            slots,
            key=lambda slot: (
                PHASE_ORDER[slot.phase],
                slot.displayed_moto,
                slot.slot_key,
            ),
        )
