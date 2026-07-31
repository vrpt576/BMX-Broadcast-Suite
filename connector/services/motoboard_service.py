"""Round-aware RaceManager motoboard access and phase resolution."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from uuid import NAMESPACE_URL, UUID, uuid5

from database import queries
from database.racemanager import RaceManagerDatabase

from connector.models import (
    CurrentMoto,
    Moto,
    MotoList,
    MotoState,
    RacePhase,
    RaceProgram,
    RaceStage,
    Rider,
)


class MotoNotFoundError(LookupError):
    pass


class RaceProgramNotFoundError(LookupError):
    pass


class RacePhaseUnavailableError(LookupError):
    pass


@dataclass(frozen=True)
class ResolvedRaceStage:
    program: RaceProgram
    stage: RaceStage
    moto: Moto


def _present(value: Any) -> bool:
    return value is not None and value != ""


def _lane_present(value: Any) -> bool:
    return value not in (None, "", 0, "0")


def _is_transfer(value: Any) -> bool:
    return isinstance(value, str) and value.strip().upper() == "X"


def _latest(values: Iterable[datetime | None]) -> datetime | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


class MotoboardService:
    """Read motogroups without conflating duplicate moto numbers.

    RaceManager uses Round_Type_ID 123 for qualifying/moto progression and
    Round_Type_ID 1 for the class's final classification.  Both branches may
    reuse Moto_Number, so Motogroup_DBID is the stable stage identity.
    """

    def __init__(self, database: RaceManagerDatabase) -> None:
        self.database = database
        self._nickname_supported: bool | None = None

    def _supports_nickname(self) -> bool:
        if self._nickname_supported is None:
            checker = getattr(self.database, "column_exists", None)
            self._nickname_supported = bool(
                checker and checker("MB", "Race_Riders", "Nickname")
            )
        return self._nickname_supported

    def _query(self, plain: str, nickname: str, params: list[Any]) -> list[Moto]:
        query = nickname if self._supports_nickname() else plain
        return self._group(self.database.fetch_all(query, params))

    def list_motos(
        self,
        motoboard_id: UUID,
        *,
        round_type_id: int | None = 123,
    ) -> MotoList:
        if round_type_id == 123:
            motos = self._query(
                queries.MOTO_RIDERS_QUALIFIERS,
                queries.MOTO_RIDERS_QUALIFIERS_WITH_NICKNAME,
                [motoboard_id],
            )
        else:
            motos = self._query(
                queries.MOTO_RIDERS,
                queries.MOTO_RIDERS_WITH_NICKNAME,
                [motoboard_id],
            )
            if round_type_id is not None:
                motos = [moto for moto in motos if moto.round_type_id == round_type_id]
        return MotoList(motoboard_id=motoboard_id, count=len(motos), motos=motos)

    def get_moto(
        self,
        motoboard_id: UUID,
        moto_number: int,
        *,
        round_type_id: int | None = 123,
    ) -> Moto:
        motos = self._query(
            queries.MOTO_RIDERS_BY_NUMBER,
            queries.MOTO_RIDERS_BY_NUMBER_WITH_NICKNAME,
            [motoboard_id, moto_number],
        )
        if round_type_id is not None:
            motos = [moto for moto in motos if moto.round_type_id == round_type_id]
        if not motos:
            branch = "" if round_type_id is None else f" in round type {round_type_id}"
            raise MotoNotFoundError(
                f"Moto {moto_number}{branch} was not found on motoboard {motoboard_id}."
            )
        return motos[0]

    def get_group(self, motoboard_id: UUID, motogroup_id: UUID) -> Moto:
        motos = self._query(
            queries.MOTO_RIDERS_BY_GROUP,
            queries.MOTO_RIDERS_BY_GROUP_WITH_NICKNAME,
            [motoboard_id, motogroup_id],
        )
        if not motos:
            raise MotoNotFoundError(
                f"Motogroup {motogroup_id} was not found on motoboard {motoboard_id}."
            )
        return motos[0]

    def get_class_motos(self, motoboard_id: UUID, class_id: UUID) -> list[Moto]:
        motos = self._query(
            queries.MOTO_RIDERS_BY_CLASS,
            queries.MOTO_RIDERS_BY_CLASS_WITH_NICKNAME,
            [motoboard_id, class_id],
        )
        if not motos:
            raise RaceProgramNotFoundError(
                f"Class {class_id} was not found on motoboard {motoboard_id}."
            )
        return motos

    def get_program(self, motoboard_id: UUID, state: CurrentMoto) -> RaceProgram:
        class_id = state.class_id
        if (
            state.resolved_motoboard_id is not None
            and state.resolved_motoboard_id != motoboard_id
        ):
            class_id = None
        seed: Moto | None = None

        if class_id is None and state.motogroup_id is not None:
            seed = self.get_group(motoboard_id, state.motogroup_id)
            class_id = seed.class_id

        if class_id is None:
            candidates = self._query(
                queries.MOTO_RIDERS_BY_NUMBER,
                queries.MOTO_RIDERS_BY_NUMBER_WITH_NICKNAME,
                [motoboard_id, state.moto_number],
            )
            if not candidates:
                raise RaceProgramNotFoundError(
                    f"Moto {state.moto_number} was not found on motoboard {motoboard_id}."
                )
            preferred_type = (
                1
                if state.race_phase in {RacePhase.MAIN, RacePhase.OVERALL}
                else 123
            )
            seed = next(
                (moto for moto in candidates if moto.round_type_id == preferred_type),
                candidates[0],
            )
            class_id = seed.class_id

        class_motos = self.get_class_motos(motoboard_id, class_id)
        qualifiers = sorted(
            (moto for moto in class_motos if moto.round_type_id == 123),
            key=lambda moto: (moto.moto_number, moto.motogroup_number),
        )
        finals = sorted(
            (moto for moto in class_motos if moto.round_type_id == 1),
            key=lambda moto: (moto.moto_number, moto.motogroup_number),
        )

        qualifier_id = state.qualifier_motogroup_id
        if qualifier_id is None and state.round_type_id == 123:
            qualifier_id = state.motogroup_id
        if qualifier_id is None and seed is not None and seed.round_type_id == 123:
            qualifier_id = seed.motogroup_id

        selected_qualifier = next(
            (moto for moto in qualifiers if moto.motogroup_id == qualifier_id),
            None,
        )
        if selected_qualifier is None:
            selected_qualifier = next(
                (moto for moto in qualifiers if moto.moto_number == state.moto_number),
                qualifiers[0] if qualifiers else None,
            )

        reference = selected_qualifier or (finals[0] if finals else None)
        if reference is None:
            raise RaceProgramNotFoundError(
                f"No broadcast stages were found for class {class_id}."
            )

        stages: list[RaceStage] = []
        if selected_qualifier is not None:
            for index, phase, label in (
                (1, RacePhase.ROUND_1, "Round 1"),
                (2, RacePhase.ROUND_2, "Round 2"),
                (3, RacePhase.ROUND_3, "Round 3"),
            ):
                if any(
                    _lane_present(getattr(rider, f"lane_{index}"))
                    for rider in selected_qualifier.riders
                ):
                    stages.append(
                        self._stage(
                            selected_qualifier,
                            phase=phase,
                            label=label,
                            kind="qualifier",
                            round_index=index,
                        )
                    )

        if finals:
            final = finals[0]
            qualifier_riders = {
                rider.rider_id for moto in qualifiers for rider in moto.riders
            }
            final_riders = {rider.rider_id for rider in final.riders}
            has_transfer_markers = any(
                _is_transfer(value)
                for moto in qualifiers
                for rider in moto.riders
                for value in (rider.finish_1, rider.finish_2, rider.finish_3)
            )
            is_main = has_transfer_markers or (
                bool(qualifier_riders) and final_riders != qualifier_riders
            )
            stages.append(
                self._stage(
                    final,
                    phase=RacePhase.MAIN if is_main else RacePhase.OVERALL,
                    label="Main" if is_main else "Overall",
                    kind="main" if is_main else "overall",
                    round_index=1,
                )
            )

        return RaceProgram(
            motoboard_id=motoboard_id,
            class_id=reference.class_id,
            class_name=reference.class_name,
            qualifier_motogroup_id=(
                selected_qualifier.motogroup_id if selected_qualifier else None
            ),
            stages=stages,
            available_phases=[stage.phase for stage in stages],
        )

    def resolve_state(self, motoboard_id: UUID, state: CurrentMoto) -> ResolvedRaceStage:
        program = self.get_program(motoboard_id, state)
        stage = next(
            (candidate for candidate in program.stages if candidate.phase == state.race_phase),
            None,
        )
        if stage is None:
            available = ", ".join(phase.value for phase in program.available_phases)
            raise RacePhaseUnavailableError(
                f"{state.race_phase.value} is unavailable for {program.class_name}. "
                f"Available phases: {available or 'none'}."
            )
        return ResolvedRaceStage(
            program=program,
            stage=stage,
            moto=self.get_group(motoboard_id, stage.motogroup_id),
        )

    @staticmethod
    def _stage(
        moto: Moto,
        *,
        phase: RacePhase,
        label: str,
        kind: str,
        round_index: int,
    ) -> RaceStage:
        return RaceStage(
            phase=phase,
            label=label,
            kind=kind,
            moto_number=moto.moto_number,
            class_id=moto.class_id,
            class_name=moto.class_name,
            round_type_id=moto.round_type_id,
            round_id=moto.round_id,
            motogroup_id=moto.motogroup_id,
            round_index=round_index,
        )

    @staticmethod
    def _group(rows: list[dict[str, Any]]) -> list[Moto]:
        grouped: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            raw_group_id = row.get("motogroup_id")
            if raw_group_id is None:
                raw_group_id = uuid5(
                    NAMESPACE_URL,
                    f"{row.get('round_type_id')}:{row.get('moto_number')}:{row.get('motogroup_number', 1)}:{row.get('class_name')}",
                )
            grouped[UUID(str(raw_group_id))].append(row)

        motos: list[Moto] = []
        for motogroup_id, moto_rows in grouped.items():
            first = moto_rows[0]
            riders = [Rider.model_validate(row) for row in moto_rows]
            scored = sum(
                1
                for rider in riders
                if any(
                    _present(value)
                    for value in (rider.finish_1, rider.finish_2, rider.finish_3)
                )
            )
            total = len(riders)
            if scored == 0:
                state = MotoState.STAGED
            elif scored < total:
                state = MotoState.SCORING
            else:
                state = MotoState.SCORED

            motos.append(
                Moto(
                    moto_number=int(first["moto_number"]),
                    motogroup_number=int(first["motogroup_number"]),
                    motogroup_id=motogroup_id,
                    class_id=first["class_id"],
                    class_name=first["class_name"],
                    class_name_short=first.get("class_name_short"),
                    round_id=first["round_id"],
                    round_type_id=int(first["round_type_id"]),
                    state=state,
                    riders_scored=scored,
                    riders_total=total,
                    updated_at=_latest(rider.updated_at for rider in riders),
                    riders=riders,
                )
            )
        return sorted(
            motos,
            key=lambda moto: (
                moto.round_type_id,
                moto.moto_number,
                moto.motogroup_number,
                str(moto.motogroup_id),
            ),
        )
