"""Sqorz client: parsing the real payload shape, and never failing fatally."""

from __future__ import annotations

import json
from pathlib import Path

from connector.services.sqorz_service import (
    SqorzService,
    parse_event_payload,
    parse_lan_phase_rank_detail,
    plausible_finish,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sqorz"


def load_event_fixture() -> dict:
    return json.loads((FIXTURES / "hoosier_day3_event.json").read_text(encoding="utf-8"))


class Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# ---------------------------------------------------------------------------
# Parsing the real internet event payload
# ---------------------------------------------------------------------------


def test_parses_every_class_rank_and_phase_detail_from_the_real_fixture() -> None:
    payload = load_event_fixture()
    rows = parse_event_payload(payload)

    assert rows
    # 6 classes were kept, at most 6 competitors each, at most 4 phases each.
    assert len(rows) <= 6 * 6 * 4

    murfin_moto1 = next(
        row
        for row in rows
        if row.last_name == "MURFIN" and row.phase_code == "M1"
    )
    assert murfin_moto1.class_code == "2204"
    assert murfin_moto1.class_name == "11-12 Open"
    assert murfin_moto1.plate == "20"
    assert murfin_moto1.first_name == "RACYN"
    assert murfin_moto1.time_seconds == 47.529
    assert murfin_moto1.time_raw == "47.529"
    assert murfin_moto1.race_position == 7
    assert murfin_moto1.rank == 1
    assert murfin_moto1.result == 1


def test_a_real_status_code_parses_as_the_raw_int_not_a_finish_position() -> None:
    """result=100400 -- confirmed live on Bryson Adams' M1 row -- is an
    internal Sqorz status code, not a finish. Parsing keeps the raw value
    (nothing here decides what it means); plausible_finish() is what turns
    it into a hidden value at display time."""
    payload = load_event_fixture()
    rows = parse_event_payload(payload)

    adams_moto1 = next(
        row for row in rows if row.last_name == "ADAMS" and row.phase_code == "M1"
    )
    assert adams_moto1.result == 100400
    assert plausible_finish(adams_moto1.result) is None


def test_a_phase_with_no_recorded_time_parses_to_none_not_an_exception() -> None:
    payload = load_event_fixture()
    rows = parse_event_payload(payload)

    murfin_moto2 = next(
        row
        for row in rows
        if row.last_name == "MURFIN" and row.phase_code == "M2"
    )
    assert murfin_moto2.time_seconds is None
    assert murfin_moto2.time_raw is None
    # Still has a rank even with no time -- that's the real, common shape.
    assert murfin_moto2.rank == 7


def test_malformed_or_missing_structure_never_raises() -> None:
    assert parse_event_payload({}) == []
    assert parse_event_payload({"classRanks": None}) == []
    assert parse_event_payload({"classRanks": "not a list"}) == []
    assert parse_event_payload(
        {"classRanks": [{"competitorRankSummaries": [{"competitorRankDetails": "nope"}]}]}
    ) == []
    assert parse_event_payload(
        {"classRanks": [{"competitorRankSummaries": [{"competitorRankDetails": [{"phaseCode": None}]}]}]}
    ) == []


def test_time_string_parsing_handles_malformed_values() -> None:
    payload = {
        "classRanks": [
            {
                "classCode": "X",
                "className": "Test",
                "competitorRankSummaries": [
                    {
                        "plate": "9",
                        "firstName": "A",
                        "lastName": "B",
                        "competitorRankDetails": [
                            {"phaseCode": "M1", "time": "not-a-number"},
                            {"phaseCode": "M2", "time": ""},
                            {"phaseCode": "M3", "time": None},
                            {"phaseCode": "1F", "time": 45.1},
                        ],
                    }
                ],
            }
        ]
    }
    rows = {row.phase_code: row for row in parse_event_payload(payload)}
    assert rows["M1"].time_seconds is None
    assert rows["M2"].time_seconds is None
    assert rows["M3"].time_seconds is None
    assert rows["1F"].time_seconds == 45.1


# ---------------------------------------------------------------------------
# plausible_finish -- the only thing allowed to turn `result` into a display
# ---------------------------------------------------------------------------


def test_plausible_finish_passes_through_a_real_placed_finish() -> None:
    for position in range(1, 9):
        assert plausible_finish(position) == position


def test_plausible_finish_hides_none() -> None:
    assert plausible_finish(None) is None


def test_plausible_finish_hides_out_of_range_status_codes() -> None:
    # 100400 and 103000 both confirmed live on withdrawn/no-show riders;
    # 0 and 9 are included as boundary cases a real BMX moto never produces
    # (8 riders max per race).
    for status in (0, 9, 100400, 103000, -1):
        assert plausible_finish(status) is None


# ---------------------------------------------------------------------------
# LAN parsing -- defensive against an undocumented, possibly-different shape
# ---------------------------------------------------------------------------


def test_lan_parsing_tolerates_completely_unknown_shapes() -> None:
    assert parse_lan_phase_rank_detail(None, class_code="X", class_name="Y") == []
    assert parse_lan_phase_rank_detail({}, class_code="X", class_name="Y") == []
    assert parse_lan_phase_rank_detail([1, 2, 3], class_code="X", class_name="Y") == []
    assert parse_lan_phase_rank_detail({"unexpected": "shape"}, class_code="X", class_name="Y") == []


def test_lan_parsing_extracts_a_nested_shape_matching_the_internet_api() -> None:
    payload = {
        "competitors": [
            {
                "plate": "5",
                "firstName": "PAT",
                "lastName": "SMITH",
                "competitorRankDetails": [
                    {"phaseCode": "M1", "time": "40.1", "rank": 2, "result": 1}
                ],
            }
        ]
    }
    rows = parse_lan_phase_rank_detail(payload, class_code="C1", class_name="Test Class")
    assert len(rows) == 1
    assert rows[0].last_name == "SMITH"
    assert rows[0].time_seconds == 40.1
    assert rows[0].class_code == "C1"
    assert rows[0].result == 1


def test_lan_parsing_extracts_a_flat_shape() -> None:
    payload = [
        {"plate": "6", "firstName": "JO", "lastName": "LEE", "time": "39.5", "result": 3}
    ]
    rows = parse_lan_phase_rank_detail(payload, class_code="C2", class_name="Flat Class")
    assert len(rows) == 1
    assert rows[0].time_seconds == 39.5
    assert rows[0].result == 3


# ---------------------------------------------------------------------------
# SqorzService: disabled/unreachable never fails, throttled polling, cache
# ---------------------------------------------------------------------------


def test_disabled_returns_empty_without_any_network_call() -> None:
    class ExplodingClock:
        def __call__(self):
            raise AssertionError("disabled Sqorz must not even check the clock")

    service = SqorzService(enabled=False, clock=ExplodingClock())
    result = service.get_riders()
    assert result.riders == []
    assert result.reachable is False
    assert result.error is None


def test_unreachable_internet_mode_returns_no_riders_never_raises() -> None:
    service = SqorzService(
        enabled=True,
        mode="internet",
        event_id="does-not-exist",
        host="",
        timeout_seconds=0.01,
        clock=Clock(),
    )

    def boom(url: str) -> dict:
        raise OSError("connection refused")

    service._get_json = boom

    result = service.get_riders()
    assert result.riders == []
    assert result.reachable is False
    assert "connection refused" in (result.error or "")


def test_missing_configuration_degrades_instead_of_raising() -> None:
    service = SqorzService(enabled=True, mode="internet", event_id="", clock=Clock())
    result = service.get_riders()
    assert result.riders == []
    assert result.reachable is False
    assert result.error


def test_a_good_fetch_is_cached_and_served_without_refetching_before_the_interval() -> None:
    clock = Clock()
    payload = load_event_fixture()
    calls = {"count": 0}

    service = SqorzService(enabled=True, mode="internet", event_id="abc", poll_seconds=10, clock=clock)

    def fake_get_json(url: str) -> dict:
        calls["count"] += 1
        return payload

    service._get_json = fake_get_json

    first = service.get_riders()
    assert calls["count"] == 1
    assert first.riders
    assert first.reachable is True
    assert first.stale is False

    clock.advance(2)  # inside the poll interval
    second = service.get_riders()
    assert calls["count"] == 1  # not refetched yet
    assert second.riders == first.riders


def test_stale_cache_is_served_and_flagged_when_sqorz_goes_unreachable() -> None:
    clock = Clock()
    payload = load_event_fixture()
    attempt = {"count": 0}

    service = SqorzService(enabled=True, mode="internet", event_id="abc", poll_seconds=10, clock=clock)

    def flaky_get_json(url: str) -> dict:
        attempt["count"] += 1
        if attempt["count"] == 1:
            return payload
        raise OSError("network down")

    service._get_json = flaky_get_json

    first = service.get_riders()
    assert first.riders and first.reachable is True

    clock.advance(11)  # past the poll interval -- triggers a refetch
    second = service.get_riders()
    assert second.riders == first.riders  # last-known-good served
    assert second.reachable is False
    assert second.error

    clock.advance(50)  # well past poll_seconds * 3
    third = service.get_riders()
    assert third.stale is True


# ---------------------------------------------------------------------------
# File/replay mode -- same parsing pipeline as internet mode, no network
# ---------------------------------------------------------------------------


def test_file_mode_replays_a_real_saved_payload(tmp_path) -> None:
    saved = tmp_path / "demo-event.json"
    saved.write_text(json.dumps(load_event_fixture()), encoding="utf-8")

    service = SqorzService(enabled=True, mode="file", file_path=str(saved), clock=Clock())
    result = service.get_riders()

    assert result.reachable is True
    assert result.error is None
    murfin_moto1 = next(
        row for row in result.riders if row.last_name == "MURFIN" and row.phase_code == "M1"
    )
    assert murfin_moto1.time_seconds == 47.529


def test_file_mode_goes_through_the_identical_parser_as_internet_mode(tmp_path) -> None:
    saved = tmp_path / "demo-event.json"
    saved.write_text(json.dumps(load_event_fixture()), encoding="utf-8")

    file_service = SqorzService(enabled=True, mode="file", file_path=str(saved), clock=Clock())
    internet_service = SqorzService(enabled=True, mode="internet", event_id="x", clock=Clock())
    internet_service._get_json = lambda url: load_event_fixture()

    assert file_service.get_riders().riders == internet_service.get_riders().riders


def test_file_mode_missing_path_configured_degrades_instead_of_raising() -> None:
    service = SqorzService(enabled=True, mode="file", file_path="", clock=Clock())
    result = service.get_riders()
    assert result.riders == []
    assert result.reachable is False
    assert result.error


def test_file_mode_nonexistent_file_degrades_instead_of_raising(tmp_path) -> None:
    service = SqorzService(
        enabled=True, mode="file", file_path=str(tmp_path / "does-not-exist.json"), clock=Clock()
    )
    result = service.get_riders()
    assert result.riders == []
    assert result.reachable is False
    assert "does-not-exist" in (result.error or "")


def test_file_mode_malformed_json_degrades_instead_of_raising(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    service = SqorzService(enabled=True, mode="file", file_path=str(bad), clock=Clock())
    result = service.get_riders()
    assert result.riders == []
    assert result.reachable is False
    assert result.error
