from __future__ import annotations

from uuid import UUID

from database import queries
from database.racemanager import RaceManagerDatabase

from connector.models import Event


class EventNotFoundError(LookupError):
    pass


class EventService:
    def __init__(self, database: RaceManagerDatabase) -> None:
        self.database = database

    def current(self) -> Event:
        row = self.database.fetch_one(queries.CURRENT_EVENT)
        if row is None:
            raise EventNotFoundError("No RaceManager event with a motoboard was found.")
        return Event.model_validate(row)

    def by_motoboard(self, motoboard_id: UUID) -> Event:
        row = self.database.fetch_one(queries.EVENT_BY_MOTOBOARD, [motoboard_id])
        if row is None:
            raise EventNotFoundError(f"Motoboard {motoboard_id} was not found.")
        return Event.model_validate(row)
