"""Privacy and structure coverage for the race-program diagnostic export."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService
from connector.services.race_program_export_service import RaceProgramExportService
from database import queries
from tests.test_round_aware_program import (
    BOARD_ID,
    FakeDatabase,
    next_main_rows,
    split_class_rows,
)

EVENT_ID = UUID("10000000-0000-0000-0000-000000000001")
RACE_ID = UUID("10000000-0000-0000-0000-000000000002")


class ExportDatabase(FakeDatabase):
    def fetch_one(self, query: str, params=None):
        if query == queries.EVENT_BY_MOTOBOARD:
            assert list(params or []) == [BOARD_ID]
        return {
            "event_id": EVENT_ID,
            "event_name": "Fixture State Race",
            "location": "Fixture Track",
            "date_begin": datetime(2025, 5, 31),
            "date_end": datetime(2025, 5, 31),
            "race_id": RACE_ID,
            "race_description": "Fixture Race",
            "motoboard_id": BOARD_ID,
            "total_motos": 56,
            "total_riders": 253,
            "updated_at": datetime(2025, 5, 31, 18, 0),
        }

    def fetch_all(self, query: str, params=None):
        if query == queries.PROGRAM_STRUCTURE_SCHEMA_COLUMNS:
            return [
                {
                    "table_schema": "MB",
                    "table_name": "Rounds",
                    "column_name": "Round_Type_ID",
                    "data_type": "int",
                    "ordinal_position": 6,
                },
                {
                    "table_schema": "MB",
                    "table_name": "Rounds",
                    "column_name": "Moto_Number_First",
                    "data_type": "int",
                    "ordinal_position": 7,
                },
            ]
        return super().fetch_all(query, params)


def fixture_rows() -> list[dict[str, object]]:
    rows = split_class_rows()
    # A second Main shares displayed moto 30.  IDs and names are fixture-only;
    # no production rider data belongs in regression fixtures.
    rows.extend(
        {
            **item,
            "moto_number": 30,
            "round_moto_number_first": 30,
            "round_moto_number_last": 30,
            "round_motogroup_count": 1,
        }
        for item in next_main_rows()
    )
    for item in rows:
        item.setdefault("round_moto_number_first", item["moto_number"])
        item.setdefault("round_moto_number_last", item["moto_number"])
        item.setdefault("round_motogroup_count", 1)
    return rows


def test_export_contains_structure_and_combined_slot_without_rider_data() -> None:
    database = ExportDatabase(fixture_rows())
    service = RaceProgramExportService(
        database,
        EventService(database),
        MotoboardService(database),
    )

    result = service.export(BOARD_ID)

    assert result.safe_to_share is True
    assert result.contains_rider_personal_data is False
    assert result.event_id == EVENT_ID
    assert result.motoboard_id == BOARD_ID
    assert result.schema_columns[0].column_name == "Round_Type_ID"
    assert any(
        slot.phase.value == "main"
        and slot.displayed_moto == 30
        and slot.combined
        and len(slot.class_ids) == 2
        for slot in result.slots
    )
    split_class = next(
        item for item in result.classes if item.class_name == "12 Intermediate"
    )
    assert split_class.classification.inferred_phase.value == "main"
    assert split_class.classification.has_transfer_markers is True
    assert split_class.stages[0].round_moto_number_first == 30

    payload = json.dumps(result.model_dump(mode="json"), sort_keys=True).lower()
    for forbidden in (
        "first_name",
        "last_name",
        "nickname",
        "bike_number",
        "sponsor",
        "rider_id",
        "motogroup_rider_id",
        "password",
        "connection_string",
    ):
        assert forbidden not in payload


def test_program_query_captures_confirmed_round_structure_metadata() -> None:
    assert "ro.Moto_Number_First AS round_moto_number_first" in queries.MOTO_RIDERS
    assert "ro.Moto_Number_Last AS round_moto_number_last" in queries.MOTO_RIDERS
    assert "ro.Motogroup_Count AS round_motogroup_count" in queries.MOTO_RIDERS


def test_schema_query_is_static_and_limited_to_structure_tables() -> None:
    query = queries.PROGRAM_STRUCTURE_SCHEMA_COLUMNS
    assert "INFORMATION_SCHEMA.COLUMNS" in query
    assert "Race_Riders" not in query
    assert "Motogroup_Riders" not in query
    assert "Registration" not in query
    assert "SELECT *" not in query.upper()
