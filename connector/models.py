"""Normalized API contracts exposed by the BBS Connector."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(ApiModel):
    status: str
    version: str
    database: str


class Event(ApiModel):
    event_id: UUID
    event_name: str
    location: str | None = None
    date_begin: date | datetime | None = None
    date_end: date | datetime | None = None
    race_id: UUID
    race_description: str | None = None
    motoboard_id: UUID
    total_motos: int
    total_riders: int
    updated_at: datetime | None = None


class MotoState(StrEnum):
    STAGED = "staged"
    SCORING = "scoring"
    SCORED = "scored"


class Rider(ApiModel):
    rider_id: UUID
    motogroup_rider_id: UUID
    rider_order: int
    bike_number: str | int | None = None
    first_name: str
    last_name: str
    nickname: str | None = None
    proficiency: str | None = None
    sponsor: str | None = None
    lane_1: int | None = None
    lane_2: int | None = None
    lane_3: int | None = None
    finish_1: int | None = None
    finish_2: int | None = None
    finish_3: int | None = None
    did_not_race: bool = False
    updated_at: datetime | None = None


class Moto(ApiModel):
    moto_number: int
    motogroup_number: int
    class_id: UUID
    class_name: str
    class_name_short: str | None = None
    round_id: UUID
    round_type_id: int
    state: MotoState
    riders_scored: int
    riders_total: int
    updated_at: datetime | None = None
    riders: list[Rider]


class MotoList(ApiModel):
    motoboard_id: UUID
    count: int
    motos: list[Moto]
