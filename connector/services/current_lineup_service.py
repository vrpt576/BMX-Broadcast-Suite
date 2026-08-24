"""Resolve the selected RaceManager stage into resilient lineup data."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from connector.models import (
    CurrentLineup,
    CurrentMoto,
    LineupRider,
    Moto,
    RacePhase,
    RaceProgram,
    RaceStage,
)
from connector.services.current_moto_service import CurrentMotoService
from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService

DEMO_MOTO = Moto.model_validate(
    {
        "moto_number": 1,
        "motogroup_number": 1,
        "motogroup_id": "00000000-0000-0000-0000-000000000010",
        "class_id": "00000000-0000-0000-0000-000000000001",
        "class_name": "7 Intermediate",
        "class_name_short": "7 Intermediate",
        "round_id": "00000000-0000-0000-0000-000000000123",
        "round_type_id": 123,
        "state": "scored",
        "riders_scored": 4,
        "riders_total": 4,
        "updated_at": "2026-07-23T18:31:29.437",
        "riders": [
            {
                "rider_id": "00000000-0000-0000-0001-000000000093",
                "motogroup_rider_id": "00000000-0000-0000-0101-000000000093",
                "rider_order": 1,
                "bike_number": 17,
                "first_name": "Nova",
                "last_name": "Archer",
                "age": 7,
                "home_track": "Aurora Valley BMX",
                "lane_1": 2,
                "lane_2": 6,
                "finish_1": 2,
                "finish_2": "X",
            },
            {
                "rider_id": "00000000-0000-0000-0001-000000000085",
                "motogroup_rider_id": "00000000-0000-0000-0101-000000000085",
                "rider_order": 2,
                "bike_number": 28,
                "first_name": "Orion",
                "last_name": "Vale",
                "age": 7,
                "home_track": "Rivergate BMX",
                "lane_1": 4,
                "lane_2": 2,
                "finish_1": 1,
            },
            {
                "rider_id": "00000000-0000-0000-0001-000000000072",
                "motogroup_rider_id": "00000000-0000-0000-0101-000000000072",
                "rider_order": 3,
                "bike_number": 46,
                "first_name": "Piper",
                "last_name": "Skye",
                "age": 7,
                "home_track": "Northstar Metro BMX Championship Track",
                "lane_1": 6,
                "lane_2": 8,
                "finish_1": 3,
            },
            {
                "rider_id": "00000000-0000-0000-0001-000000000004",
                "motogroup_rider_id": "00000000-0000-0000-0101-000000000004",
                "rider_order": 4,
                "bike_number": 73,
                "first_name": "Milo",
                "last_name": "Finch",
                "age": 7,
                "home_track": "Silver Pine BMX",
                "lane_1": 8,
                "lane_2": 4,
                "finish_1": 4,
            },
        ],
    }
)


class CurrentLineupService:
    """Combines persisted state, exact stage resolution, and a safe cache."""

    def __init__(
        self,
        current: CurrentMotoService,
        events: EventService,
        motos: MotoboardService,
        cache_file: Path | None = None,
    ) -> None:
        self.current, self.events, self.motos = current, events, motos
        self.cache_file = cache_file or current.state_file.parent / "last_known_lineup.json"

    def get(
        self,
        *,
        demo: bool = False,
        motoboard_id: UUID | None = None,
    ) -> CurrentLineup:
        state = self.current.get()
        if demo:
            stage = self._demo_stage(state)
            program = RaceProgram(
                motoboard_id=UUID("00000000-0000-0000-0000-000000000099"),
                class_id=DEMO_MOTO.class_id,
                class_name=DEMO_MOTO.class_name,
                qualifier_motogroup_id=DEMO_MOTO.motogroup_id,
                stages=[stage],
                available_phases=[stage.phase],
            )
            return self._build(
                state,
                DEMO_MOTO,
                stage,
                program,
                source="demo",
                motoboard_id=None,
            )

        selected_board_id = motoboard_id or state.motoboard_id
        expected_board_id = selected_board_id or state.resolved_motoboard_id
        try:
            board_id = selected_board_id or self.events.current().motoboard_id
            if hasattr(self.motos, "resolve_state"):
                resolved = self.motos.resolve_state(board_id, state)
                synced = self.current.sync_race_position(
                    motoboard_id=board_id,
                    program=resolved.program,
                    stage=resolved.stage,
                    expected_state=state,
                    slot_key=state.slot_key,
                    slot_class_ids=(state.slot_class_ids or None),
                    slot_motogroup_ids=(state.slot_motogroup_ids or None),
                    slot_class_name=(state.class_name if state.slot_key else None),
                )
                moto, stage, program = resolved.moto, resolved.stage, resolved.program
            else:  # compatibility with older adapters and simple test doubles
                moto = self.motos.get_moto(board_id, state.moto_number)
                stage, program = self._legacy_context(state, moto, board_id)
                synced = state
            result = self._build(
                synced,
                moto,
                stage,
                program,
                source="racemanager",
                motoboard_id=board_id,
            )
            self._write_cache(result)
            return result
        except Exception as exc:
            cached = self._read_cache(
                state,
                expected_motoboard_id=expected_board_id,
            )
            if cached is None:
                raise
            return cached.model_copy(
                update={"source": "cache", "is_stale": True, "warning": str(exc)}
            )

    @staticmethod
    def gate_for_round(rider: object, round_index: int) -> int | None:
        gate = getattr(rider, f"lane_{round_index}", None)
        return None if gate in (None, 0) else int(gate)

    @classmethod
    def _build(
        cls,
        state: CurrentMoto,
        moto: Moto,
        stage: RaceStage | None = None,
        program: RaceProgram | None = None,
        *,
        source: str,
        motoboard_id: UUID | None = None,
        is_stale: bool = False,
    ) -> CurrentLineup:
        if stage is None or program is None:
            stage, program = cls._legacy_context(
                state,
                moto,
                motoboard_id or UUID("00000000-0000-0000-0000-000000000099"),
            )
        riders = [
            LineupRider(
                gate=cls.gate_for_round(rider, stage.round_index),
                bike_number=rider.bike_number,
                first_name=rider.first_name,
                last_name=rider.last_name,
                nickname=rider.nickname,
                age=rider.age,
                home_track=rider.home_track,
            )
            for rider in moto.riders
        ]
        riders.sort(
            key=lambda rider: (
                rider.gate is None,
                rider.gate or 999,
                rider.last_name,
            )
        )
        return CurrentLineup(
            moto_number=moto.moto_number,
            race_phase=stage.phase,
            phase_label=stage.label,
            available_phases=program.available_phases,
            motoboard_id=motoboard_id,
            class_id=stage.class_id,
            round_type_id=stage.round_type_id,
            round_id=stage.round_id,
            motogroup_id=stage.motogroup_id,
            round_index=stage.round_index,
            competition_stage=stage.competition_stage,
            scoring_method=stage.scoring_method,
            finalization_method=stage.finalization_method,
            class_name=(
                state.class_name
                if state.slot_key and state.class_name
                else moto.class_name or "Class not set"
            ),
            riders=riders,
            source=source,
            updated_at=moto.updated_at,
            cached_at=datetime.now(timezone.utc),
            is_stale=is_stale,
        )


    @staticmethod
    def _legacy_context(
        state: CurrentMoto,
        moto: Moto,
        motoboard_id: UUID,
    ) -> tuple[RaceStage, RaceProgram]:
        round_index = {
            RacePhase.ROUND_1: 1,
            RacePhase.ROUND_2: 2,
            RacePhase.ROUND_3: 3,
        }.get(state.race_phase, 1)
        # Title-casing the phase value would turn round_3 into "Round 3",
        # a label BBS never displays (see docs/racemanager-round-model.md).
        fallback_labels = {
            RacePhase.ROUND_1: "Round 1",
            RacePhase.ROUND_2: "Round 2",
            RacePhase.ROUND_3: "Moto 3",
            RacePhase.QUARTERFINAL: "Quarterfinals",
            RacePhase.SEMIFINAL: "Semifinals",
            RacePhase.MAIN: "Main",
        }
        label = state.phase_label or fallback_labels[state.race_phase]
        stage = RaceStage(
            phase=state.race_phase,
            label=label,
            kind="legacy",
            moto_number=moto.moto_number,
            class_id=moto.class_id,
            class_name=moto.class_name,
            round_type_id=moto.round_type_id,
            round_id=moto.round_id,
            motogroup_id=moto.motogroup_id,
            round_index=round_index,
        )
        program = RaceProgram(
            motoboard_id=motoboard_id,
            class_id=moto.class_id,
            class_name=moto.class_name,
            qualifier_motogroup_id=(moto.motogroup_id if moto.round_type_id == 123 else None),
            stages=[stage],
            available_phases=[stage.phase],
        )
        return stage, program

    @staticmethod
    def _demo_stage(state: CurrentMoto) -> RaceStage:
        phase = state.race_phase
        round_index = {
            RacePhase.ROUND_1: 1,
            RacePhase.ROUND_2: 2,
            RacePhase.ROUND_3: 3,
        }.get(phase, 1)
        return RaceStage(
            phase=phase,
            label=phase.value.replace("_", " ").title(),
            kind="demo",
            moto_number=DEMO_MOTO.moto_number,
            class_id=DEMO_MOTO.class_id,
            class_name=DEMO_MOTO.class_name,
            round_type_id=DEMO_MOTO.round_type_id,
            round_id=DEMO_MOTO.round_id,
            motogroup_id=DEMO_MOTO.motogroup_id,
            round_index=round_index,
        )

    def _write_cache(self, lineup: CurrentLineup) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_file.with_suffix(self.cache_file.suffix + ".tmp")
        temporary.write_text(
            json.dumps(lineup.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.cache_file)

    def _read_cache(
        self,
        state: CurrentMoto,
        *,
        expected_motoboard_id: UUID | None,
    ) -> CurrentLineup | None:
        try:
            cached = CurrentLineup.model_validate_json(
                self.cache_file.read_text(encoding="utf-8")
            )
            if cached.race_phase != state.race_phase:
                return None
            if state.motogroup_id is not None and cached.motogroup_id != state.motogroup_id:
                return None
            if state.motogroup_id is None and cached.moto_number != state.moto_number:
                return None
            if (
                expected_motoboard_id is not None
                and cached.motoboard_id != expected_motoboard_id
            ):
                return None
            return cached
        except (OSError, ValueError):
            return None
