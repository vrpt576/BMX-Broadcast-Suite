from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable
from uuid import UUID

from database import queries
from database.racemanager import RaceManagerDatabase

from connector.models import Moto, MotoList, MotoState, Rider


class MotoNotFoundError(LookupError):
    pass


def _present(value: Any) -> bool:
    return value is not None and value != ""


def _latest(values: Iterable[datetime | None]) -> datetime | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


class MotoboardService:
    def __init__(self, database: RaceManagerDatabase) -> None:
        self.database = database

    def list_motos(self, motoboard_id: UUID) -> MotoList:
        rows = self.database.fetch_all(queries.MOTO_RIDERS, [motoboard_id])
        motos = self._group(rows)
        return MotoList(motoboard_id=motoboard_id, count=len(motos), motos=motos)

    def get_moto(self, motoboard_id: UUID, moto_number: int) -> Moto:
        rows = self.database.fetch_all(
            queries.MOTO_RIDERS_BY_NUMBER,
            [motoboard_id, moto_number],
        )
        motos = self._group(rows)
        if not motos:
            raise MotoNotFoundError(
                f"Moto {moto_number} was not found on motoboard {motoboard_id}."
            )
        return motos[0]

    @staticmethod
    def _group(rows: list[dict[str, Any]]) -> list[Moto]:
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[int(row["moto_number"])].append(row)

        motos: list[Moto] = []
        for moto_number in sorted(grouped):
            moto_rows = grouped[moto_number]
            first = moto_rows[0]
            riders = [Rider.model_validate(row) for row in moto_rows]
            scored = sum(1 for row in moto_rows if _present(row.get("finish_1")))
            total = len(riders)
            if scored == 0:
                state = MotoState.STAGED
            elif scored < total:
                state = MotoState.SCORING
            else:
                state = MotoState.SCORED

            motos.append(
                Moto(
                    moto_number=moto_number,
                    motogroup_number=first["motogroup_number"],
                    class_id=first["class_id"],
                    class_name=first["class_name"],
                    class_name_short=first.get("class_name_short"),
                    round_id=first["round_id"],
                    round_type_id=first["round_type_id"],
                    state=state,
                    riders_scored=scored,
                    riders_total=total,
                    updated_at=_latest(rider.updated_at for rider in riders),
                    riders=riders,
                )
            )
        return motos
