"""Normalized API contracts exposed by the BBS Connector."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    # RaceManager uses numeric strings for places and "X" for a transfer.
    finish_1: int | str | None = None
    finish_2: int | str | None = None
    finish_3: int | str | None = None
    did_not_race: bool = False
    updated_at: datetime | None = None


class Moto(ApiModel):
    moto_number: int
    motogroup_number: int
    motogroup_id: UUID
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


class RacePhase(StrEnum):
    """Broadcast phase backed by an exact RaceManager stage."""

    ROUND_1 = "round_1"
    ROUND_2 = "round_2"
    ROUND_3 = "round_3"
    QUARTERFINAL = "quarterfinal"
    SEMIFINAL = "semifinal"
    MAIN = "main"
    OVERALL = "overall"


class RaceStage(ApiModel):
    """One selectable phase with its exact RaceManager identity."""

    phase: RacePhase
    label: str
    kind: str
    moto_number: int
    class_id: UUID
    class_name: str
    round_type_id: int
    round_id: UUID
    motogroup_id: UUID
    round_index: int = Field(ge=1, le=3)


class RaceProgram(ApiModel):
    """Available phases for one class and qualifier motogroup."""

    motoboard_id: UUID
    class_id: UUID
    class_name: str
    qualifier_motogroup_id: UUID | None = None
    stages: list[RaceStage]
    available_phases: list[RacePhase]


class ActiveGraphic(StrEnum):
    """Graphic selected by the race director."""

    HIDDEN = "hidden"
    CURRENT_MOTO = "current_moto"
    LINEUP = "lineup"
    RESULTS = "results"
    ROUND_1_BREAK = "round_1_break"
    MAIN_BREAK = "main_break"


class BreakPreset(StrEnum):
    """Validated presets rendered by the shared break graphic."""

    ROUND_1 = "round_1"
    MAIN = "main"


class CurrentMoto(ApiModel):
    """Operator-selected exact RaceManager stage used by broadcast controls."""

    moto_number: int
    race_phase: RacePhase = RacePhase.ROUND_1
    phase_label: str | None = None
    class_name: str | None = None
    minimum_moto: int = 1
    maximum_moto: int | None = None
    motoboard_id: UUID | None = None
    resolved_motoboard_id: UUID | None = None
    class_id: UUID | None = None
    round_type_id: int | None = None
    round_id: UUID | None = None
    motogroup_id: UUID | None = None
    qualifier_motogroup_id: UUID | None = None
    round_index: int | None = Field(default=None, ge=1, le=3)
    updated_at: datetime | None = None
    source: str = "manual"
    active_graphic: ActiveGraphic = ActiveGraphic.CURRENT_MOTO


class CurrentMotoUpdate(ApiModel):
    moto_number: int
    race_phase: RacePhase | None = None
    phase_label: str | None = None
    class_name: str | None = None
    minimum_moto: int | None = None
    maximum_moto: int | None = None
    motoboard_id: UUID | None = None
    class_id: UUID | None = None
    round_type_id: int | None = None
    round_id: UUID | None = None
    motogroup_id: UUID | None = None
    qualifier_motogroup_id: UUID | None = None
    round_index: int | None = Field(default=None, ge=1, le=3)
    active_graphic: ActiveGraphic | None = None


class LineupRider(ApiModel):
    """One rider row formatted for a gate-assignment graphic."""

    gate: int | None = None
    bike_number: str | int | None = None
    first_name: str
    last_name: str
    nickname: str | None = None


class CurrentLineup(ApiModel):
    """Broadcast-ready lineup for the resolved RaceManager stage."""

    moto_number: int
    race_phase: RacePhase
    phase_label: str | None = None
    available_phases: list[RacePhase] = Field(default_factory=list)
    motoboard_id: UUID | None = None
    class_id: UUID | None = None
    round_type_id: int | None = None
    round_id: UUID | None = None
    motogroup_id: UUID | None = None
    round_index: int | None = None
    class_name: str
    riders: list[LineupRider]
    source: str
    updated_at: datetime | None = None
    cached_at: datetime | None = None
    is_stale: bool = False
    warning: str | None = None


class ResultRider(ApiModel):
    finish: int | None = None
    transferred: bool = False
    status: str | None = None
    bike_number: str | int | None = None
    first_name: str
    last_name: str


class CurrentResults(ApiModel):
    event_name: str | None = None
    moto_number: int
    race_phase: RacePhase
    phase_label: str | None = None
    available_phases: list[RacePhase] = Field(default_factory=list)
    motoboard_id: UUID | None = None
    class_id: UUID | None = None
    round_type_id: int | None = None
    round_id: UUID | None = None
    motogroup_id: UUID | None = None
    round_index: int | None = None
    class_name: str
    riders: list[ResultRider]
    source: str
    updated_at: datetime | None = None
    is_stale: bool = False
    warning: str | None = None
    result_status: str = "official"
    progress_index: int | None = None
    progress_total: int | None = None


class ResultsRollStart(ApiModel):
    start_from: str = Field(default="first", pattern="^(first|current)$")
    interval_seconds: int = Field(default=10, ge=2, le=300)


class ResultsRollState(ApiModel):
    active: bool = False
    paused: bool = False
    interval_seconds: int = Field(default=10, ge=2, le=300)
    motoboard_id: UUID | None = None
    event_name: str | None = None
    current_result_index: int | None = None
    current_result_moto: int | None = None
    total_available_results: int = 0
    started_at: datetime | None = None
    next_change_at: datetime | None = None
