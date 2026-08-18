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
    age: int | None = Field(default=None, ge=0, le=120)
    home_track: str | None = None
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
    round_moto_number_first: int | None = None
    round_moto_number_last: int | None = None
    round_motogroup_count: int | None = None
    state: MotoState
    riders_scored: int
    riders_total: int
    updated_at: datetime | None = None
    riders: list[Rider]


class MotoList(ApiModel):
    motoboard_id: UUID
    count: int
    motos: list[Moto]


class ProgramSegment(StrEnum):
    """Operator-facing block in the physical race-day running order."""

    ROUND_1 = "round_1"
    ROUND_2 = "round_2"
    ROUND_3 = "round_3"
    QUARTERFINAL = "quarterfinal"
    SEMIFINAL = "semifinal"
    MAIN = "main"


# ``RacePhase`` remains as an API/source compatibility name.  It now means a
# program segment only; scoring classifications such as Overall never belong
# in this enum.
RacePhase = ProgramSegment


class CompetitionStage(StrEnum):
    """What a class record represents competitively."""

    UNKNOWN = "unknown"
    QUALIFYING_MOTO_1 = "qualifying_moto_1"
    QUALIFYING_MOTO_2 = "qualifying_moto_2"
    QUALIFYING_MOTO_3 = "qualifying_moto_3"
    QUARTER = "quarter"
    SEMI = "semi"
    MAIN_EVENT = "main_event"
    TOTAL_POINTS_FINAL_MOTO = "total_points_final_moto"
    TOTAL_POINTS_CLASSIFICATION = "total_points_classification"


class ScoringMethod(StrEnum):
    """RaceManager qualifying/scoring method for one class."""

    UNKNOWN = "unknown"
    TRANSFER = "transfer"
    TRANSFER_LST = "transfer_lst"
    TOTAL_POINTS = "total_points"


class FinalizationMethod(StrEnum):
    """How the official class placing is produced."""

    UNKNOWN = "unknown"
    FINAL_RACE = "final_race"
    ACCUMULATED_POINTS = "accumulated_points"


class MainProgramBoundarySource(StrEnum):
    """Authority used to place Total Points third motos in the Main block."""

    OPERATOR_OVERRIDE = "operator_override"
    UNRESOLVED = "unresolved"


class MainProgramBoundaryConfidence(StrEnum):
    """Confidence attached to an event-level Main-boundary determination."""

    CONFIRMED = "confirmed"
    LOW = "low"
    NONE = "none"


class MainProgramBoundary(ApiModel):
    """Event-scoped boundary and non-authoritative RaceManager evidence."""

    motoboard_id: UUID
    start_moto: int | None = Field(default=None, ge=1)
    source: MainProgramBoundarySource = MainProgramBoundarySource.UNRESOLVED
    confidence: MainProgramBoundaryConfidence = MainProgramBoundaryConfidence.NONE
    suggested_start_moto: int | None = Field(default=None, ge=1)
    evidence: list[str] = Field(default_factory=list)


class MainProgramBoundaryUpdate(ApiModel):
    start_moto: int = Field(ge=1)


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
    competition_stage: CompetitionStage = CompetitionStage.UNKNOWN
    scoring_method: ScoringMethod = ScoringMethod.UNKNOWN
    finalization_method: FinalizationMethod = FinalizationMethod.UNKNOWN
    result_round_type_id: int | None = None
    result_round_id: UUID | None = None
    result_motogroup_id: UUID | None = None
    result_round_index: int | None = Field(default=None, ge=1, le=3)
    round_moto_number_first: int | None = None
    round_moto_number_last: int | None = None
    round_motogroup_count: int | None = None
    classification_reason: str | None = None
    classification_ambiguous: bool = False
    classification_overridden: bool = False


class RaceProgram(ApiModel):
    """Available phases for one class and qualifier motogroup."""

    motoboard_id: UUID
    class_id: UUID
    class_name: str
    qualifier_motogroup_id: UUID | None = None
    stages: list[RaceStage]
    available_phases: list[RacePhase]


class RaceSlotMember(ApiModel):
    """One class/stage association within a displayed race slot."""

    stage: RaceStage
    qualifier_motogroup_id: UUID | None = None


class RaceSlot(ApiModel):
    """One displayed moto occurrence in one phase, including combined classes."""

    slot_key: str
    motoboard_id: UUID
    phase: RacePhase
    phase_label: str
    moto_number: int
    combined: bool
    class_name: str
    class_ids: list[UUID]
    motogroup_ids: list[UUID]
    members: list[RaceSlotMember]


class RaceProgramSchemaColumn(ApiModel):
    """Allowlisted RaceManager schema metadata included in a safe export."""

    table_schema: str
    table_name: str
    column_name: str
    data_type: str
    ordinal_position: int


class RaceProgramExportStage(ApiModel):
    """One RaceManager stage without rider-level registration data."""

    phase: RacePhase
    round_label: str
    kind: str
    displayed_moto: int
    round_type_id: int
    round_id: UUID
    motogroup_id: UUID
    class_id: UUID
    class_name: str
    round_index: int
    competition_stage: CompetitionStage = CompetitionStage.UNKNOWN
    scoring_method: ScoringMethod = ScoringMethod.UNKNOWN
    finalization_method: FinalizationMethod = FinalizationMethod.UNKNOWN
    physical_race: bool = True
    result_round_type_id: int | None = None
    result_round_id: UUID | None = None
    result_motogroup_id: UUID | None = None
    round_moto_number_first: int | None = None
    round_moto_number_last: int | None = None
    round_motogroup_count: int | None = None


class RaceProgramClassificationEvidence(ApiModel):
    """Non-identifying evidence used by the current final classifier."""

    qualifier_group_count: int
    qualifier_rider_count: int
    final_group_count: int
    final_rider_count: int
    has_transfer_markers: bool
    rider_sets_equal: bool | None = None
    program_segment: ProgramSegment | None = None
    competition_stage: CompetitionStage = CompetitionStage.UNKNOWN
    scoring_method: ScoringMethod = ScoringMethod.UNKNOWN
    finalization_method: FinalizationMethod = FinalizationMethod.UNKNOWN
    inference_reason: str
    ambiguous: bool = False
    overridden: bool = False


class RaceProgramExportClass(ApiModel):
    class_id: UUID
    class_name: str
    available_stages: list[RacePhase]
    classification: RaceProgramClassificationEvidence
    stages: list[RaceProgramExportStage]


class RaceProgramExportSlot(ApiModel):
    """Candidate on-air slot used to diagnose combined classifications."""

    slot_key: str
    phase: RacePhase
    round_label: str
    displayed_moto: int
    combined: bool
    class_ids: list[UUID]
    class_names: list[str]
    round_type_ids: list[int]
    round_ids: list[UUID]
    motogroup_ids: list[UUID]
    competition_stages: list[CompetitionStage] = Field(default_factory=list)
    scoring_methods: list[ScoringMethod] = Field(default_factory=list)
    finalization_methods: list[FinalizationMethod] = Field(default_factory=list)


class RaceProgramStructureExport(ApiModel):
    """Privacy-safe structural snapshot suitable for issue reports."""

    export_version: int = 3
    generated_at: datetime
    safe_to_share: bool = True
    contains_rider_personal_data: bool = False
    event_id: UUID
    event_name: str
    event_date: date | datetime | None = None
    race_id: UUID
    race_description: str | None = None
    motoboard_id: UUID
    total_motos: int
    total_riders: int
    main_program_boundary: MainProgramBoundary
    schema_columns: list[RaceProgramSchemaColumn]
    classes: list[RaceProgramExportClass]
    slots: list[RaceProgramExportSlot]


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
    slot_key: str | None = None
    slot_class_ids: list[UUID] = Field(default_factory=list)
    slot_motogroup_ids: list[UUID] = Field(default_factory=list)
    navigation_message: str | None = None
    round_index: int | None = Field(default=None, ge=1, le=3)
    competition_stage: CompetitionStage = CompetitionStage.UNKNOWN
    scoring_method: ScoringMethod = ScoringMethod.UNKNOWN
    finalization_method: FinalizationMethod = FinalizationMethod.UNKNOWN
    updated_at: datetime | None = None
    source: str = "manual"
    active_graphic: ActiveGraphic = ActiveGraphic.CURRENT_MOTO


class CurrentMotoUpdate(ApiModel):
    moto_number: int = Field(ge=1)
    race_phase: RacePhase | None = None
    phase_label: str | None = None
    class_name: str | None = None
    minimum_moto: int | None = Field(default=None, ge=1)
    maximum_moto: int | None = Field(default=None, ge=1)
    motoboard_id: UUID | None = None
    class_id: UUID | None = None
    round_type_id: int | None = None
    round_id: UUID | None = None
    motogroup_id: UUID | None = None
    qualifier_motogroup_id: UUID | None = None
    slot_key: str | None = None
    slot_class_ids: list[UUID] | None = None
    slot_motogroup_ids: list[UUID] | None = None
    navigation_message: str | None = None
    round_index: int | None = Field(default=None, ge=1, le=3)
    competition_stage: CompetitionStage | None = None
    scoring_method: ScoringMethod | None = None
    finalization_method: FinalizationMethod | None = None
    active_graphic: ActiveGraphic | None = None


class LineupRider(ApiModel):
    """One rider row formatted for a gate-assignment graphic."""

    gate: int | None = None
    bike_number: str | int | None = None
    first_name: str
    last_name: str
    nickname: str | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    home_track: str | None = None


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
    competition_stage: CompetitionStage = CompetitionStage.UNKNOWN
    scoring_method: ScoringMethod = ScoringMethod.UNKNOWN
    finalization_method: FinalizationMethod = FinalizationMethod.UNKNOWN
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
    age: int | None = Field(default=None, ge=0, le=120)
    home_track: str | None = None


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
    competition_stage: CompetitionStage = CompetitionStage.UNKNOWN
    scoring_method: ScoringMethod = ScoringMethod.UNKNOWN
    finalization_method: FinalizationMethod = FinalizationMethod.UNKNOWN
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
