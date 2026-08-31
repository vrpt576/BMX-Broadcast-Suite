"""Sqorz client: parsing the real payload shape, and never failing fatally."""

from __future__ import annotations

import json
from pathlib import Path

from connector.services.sqorz_service import (
    SqorzService,
    find_phase_blocks_by_searching_the_tree,
    parse_event_payload,
    parse_lan_by_searching_the_tree,
    parse_lan_phase_rank_detail,
    parse_lan_phase_summaries_order,
    parse_org_events_payload,
    plausible_finish,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sqorz"


def load_event_fixture() -> dict:
    return json.loads((FIXTURES / "hoosier_day3_event.json").read_text(encoding="utf-8"))


def load_org_fixture() -> dict:
    return json.loads((FIXTURES / "usabmx_org.json").read_text(encoding="utf-8"))


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
# Tree-search resilience fallback -- for when the guessed LAN shape is wrong
# ---------------------------------------------------------------------------


def test_tree_search_finds_a_competitor_nested_completely_differently_than_guessed() -> None:
    """Plate/name one level deeper than guessed, wrapped in an unexpected
    container key, time/result under a differently-named nested key --
    none of this matches parse_lan_phase_rank_detail's specific shape, but
    every field name itself is still the known vocabulary."""
    payload = {
        "raceData": {
            "riders": [
                {
                    "rider": {"plate": "9", "firstName": "ALEX", "lastName": "RIVERA"},
                    "results": [{"phaseCode": "M1", "time": "41.220", "result": 2}],
                }
            ]
        }
    }
    rows = parse_lan_by_searching_the_tree(payload, class_code="C1", class_name="Test Class")

    assert len(rows) == 1
    assert rows[0].last_name == "RIVERA"
    assert rows[0].plate == "9"
    assert rows[0].time_seconds == 41.220
    assert rows[0].result == 2
    assert rows[0].class_code == "C1"


def test_tree_search_still_handles_a_flat_shape() -> None:
    payload = [{"plate": "3", "lastName": "OKAFOR", "time": "50.0", "phaseCode": "M2"}]
    rows = parse_lan_by_searching_the_tree(payload, class_code=None, class_name=None)

    assert len(rows) == 1
    assert rows[0].phase_code == "M2"
    assert rows[0].time_seconds == 50.0


def test_tree_search_finds_nothing_in_a_genuinely_unrecognisable_shape() -> None:
    payload = {"foo": [{"bar": 1, "baz": "qux"}]}
    assert parse_lan_by_searching_the_tree(payload, class_code="C1", class_name="X") == []
    assert parse_lan_by_searching_the_tree(None, class_code="C1", class_name="X") == []
    assert parse_lan_by_searching_the_tree("not even a dict", class_code="C1", class_name="X") == []


def test_tree_search_never_confuses_result_with_race_position() -> None:
    """The one thing this must never do: attribute a value to the wrong
    field just because it's numeric. result (finish) and racePosition
    (starting gate) are never interchangeable -- see sqorz_matching.py."""
    payload = [
        {
            "plate": "1",
            "lastName": "NGUYEN",
            "phaseCode": "M1",
            "time": "45.0",
            "racePosition": 7,
            "result": 2,
            "rank": 1,
        }
    ]
    row = parse_lan_by_searching_the_tree(payload, class_code=None, class_name=None)[0]
    assert row.race_position == 7
    assert row.result == 2
    assert row.rank == 1


def test_tree_search_deduplicates_a_competitor_reachable_two_ways() -> None:
    """A dict that satisfies both "looks like a competitor" and "looks like
    a phase detail" (e.g. a flat row) must not produce the same row twice
    just because _walk_dicts visits it as both the competitor and its own
    detail."""
    payload = {"plate": "4", "lastName": "PARK", "phaseCode": "M1", "time": "48.5"}
    rows = parse_lan_by_searching_the_tree(payload, class_code=None, class_name=None)
    assert len(rows) == 1


def test_phase_block_tree_search_finds_pairs_in_an_unguessed_container() -> None:
    payload = {"summary": {"data": [{"classCode": "2204", "phaseBlockCode": "M1", "className": "11-12 Open"}]}}
    blocks = find_phase_blocks_by_searching_the_tree(payload)
    assert blocks == [{"classCode": "2204", "className": "11-12 Open", "phaseBlockCode": "M1"}]


def test_phase_block_tree_search_accepts_phase_code_as_a_stand_in() -> None:
    """UNVERIFIED which key name Sqorz's LAN API actually uses for this --
    phaseCode is accepted as a plausible alternative to phaseBlockCode."""
    payload = [{"classCode": "2204", "phaseCode": "M1"}]
    blocks = find_phase_blocks_by_searching_the_tree(payload)
    assert blocks == [{"classCode": "2204", "className": None, "phaseBlockCode": "M1"}]


def test_phase_block_tree_search_finds_nothing_in_an_unrecognisable_shape() -> None:
    assert find_phase_blocks_by_searching_the_tree({"nope": "nothing here"}) == []
    assert find_phase_blocks_by_searching_the_tree(None) == []


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
# LAN mode via SqorzService: fallback wiring, raw-response capture, and the
# distinction between "genuinely nothing racing yet" and "couldn't parse it"
# ---------------------------------------------------------------------------


def test_lan_mode_uses_the_tree_search_fallback_when_the_guessed_shape_fails(tmp_path) -> None:
    """End-to-end proof the fallback is actually wired in, not just tested
    in isolation: a shape parse_lan_phase_rank_detail can't handle, but
    parse_lan_by_searching_the_tree can, still produces real riders."""
    service = SqorzService(
        enabled=True,
        mode="lan",
        host="scoring",
        raw_response_file=tmp_path / "raw.json",
        clock=Clock(),
    )

    def fake_call_lan(func: str, args: list) -> object:
        if func == "getPhaseBlockSummaries":
            return {"phaseBlockSummaries": [{"classCode": "C1", "phaseBlockCode": "M1", "className": "Test"}]}
        return {
            "wrapper": {
                "rider": {"plate": "9", "firstName": "ALEX", "lastName": "RIVERA"},
                "detail": {"phaseCode": "M1", "time": "41.220", "result": 2},
            }
        }

    service._call_lan = fake_call_lan
    result = service.get_riders()

    assert result.reachable is True
    row = next(r for r in result.riders if r.last_name == "RIVERA")
    assert row.time_seconds == 41.220
    assert service.last_lan_parse_warning is None  # the fallback succeeded -- not a failure
    assert not tmp_path.joinpath("raw.json").exists()  # nothing to flag, nothing saved


def test_lan_mode_saves_the_raw_response_and_warns_when_nothing_parses(tmp_path) -> None:
    raw_file = tmp_path / "raw.json"
    service = SqorzService(
        enabled=True, mode="lan", host="scoring", raw_response_file=raw_file, clock=Clock()
    )

    def fake_call_lan(func: str, args: list) -> object:
        if func == "getPhaseBlockSummaries":
            return {"phaseBlockSummaries": [{"classCode": "C1", "phaseBlockCode": "M1"}]}
        # Real content, but nothing recognisable in it at all.
        return {"totallyUnexpectedShape": {"nested": ["stuff", 123, True]}}

    service._call_lan = fake_call_lan
    result = service.get_riders()

    assert result.reachable is True  # it DID respond -- this isn't a network failure
    assert result.riders == []
    assert service.last_lan_parse_warning is not None
    assert str(raw_file) in service.last_lan_parse_warning
    assert raw_file.exists()
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    assert saved["getPhaseBlockSummaries"] == {"phaseBlockSummaries": [{"classCode": "C1", "phaseBlockCode": "M1"}]}


def test_lan_mode_does_not_warn_when_there_is_genuinely_nothing_to_find(tmp_path) -> None:
    """Reachable, but no classes/blocks at all -- a normal state before an
    event starts, not a parsing failure. Must not be flagged the same way
    as an unrecognisable-but-non-empty response."""
    raw_file = tmp_path / "raw.json"
    service = SqorzService(
        enabled=True, mode="lan", host="scoring", raw_response_file=raw_file, clock=Clock()
    )
    service._call_lan = lambda func, args: {}

    result = service.get_riders()

    assert result.reachable is True
    assert result.riders == []
    assert service.last_lan_parse_warning is None
    assert not raw_file.exists()


def test_lan_mode_keeps_the_last_raw_response_in_memory_even_on_success(tmp_path) -> None:
    """last_raw_lan_response is for the live status page's "raw" link --
    must be populated whether parsing succeeded or not."""
    service = SqorzService(
        enabled=True,
        mode="lan",
        host="scoring",
        raw_response_file=tmp_path / "raw.json",
        clock=Clock(),
    )
    detail = {"competitors": [{"plate": "1", "lastName": "OK", "competitorRankDetails": [{"phaseCode": "M1", "time": "40.0"}]}]}
    service._call_lan = lambda func, args: (
        {"phaseBlockSummaries": [{"classCode": "C1", "phaseBlockCode": "M1"}]}
        if func == "getPhaseBlockSummaries"
        else detail
    )

    service.get_riders()

    assert service.last_raw_lan_response is not None
    assert "getPhaseBlockSummaries" in service.last_raw_lan_response


def test_lan_raw_response_save_is_best_effort_never_fatal(tmp_path) -> None:
    """A bad raw_response_file (e.g. a directory in the way) must degrade
    the save, never break Sqorz polling itself."""
    blocking_directory = tmp_path / "raw.json"
    blocking_directory.mkdir()  # a directory sitting where the file should go
    service = SqorzService(
        enabled=True, mode="lan", host="scoring", raw_response_file=blocking_directory, clock=Clock()
    )
    service._call_lan = lambda func, args: (
        {"phaseBlockSummaries": [{"classCode": "C1", "phaseBlockCode": "M1"}]}
        if func == "getPhaseBlockSummaries"
        else {"unrecognisable": True}
    )

    result = service.get_riders()  # must not raise

    assert result.reachable is True
    assert result.riders == []


# ---------------------------------------------------------------------------
# parse_lan_phase_summaries_order -- UNVERIFIED shape guess for getPhaseSummaries,
# the LAN-mode running-order source connector/services/sqorz_navigation_service.py
# treats as primary. Pure function tests only; wiring into _fetch_lan() is
# covered separately below.
# ---------------------------------------------------------------------------


def test_parse_phase_summaries_order_reads_the_guessed_container_key() -> None:
    payload = {
        "phaseSummaries": [
            {"classCode": "C1", "phaseCode": "M1"},
            {"classCode": "C1", "phaseCode": "M2"},
            {"classCode": "C2", "phaseCode": "M1"},
        ]
    }
    assert parse_lan_phase_summaries_order(payload) == [
        ("C1", "M1"),
        ("C1", "M2"),
        ("C2", "M1"),
    ]


def test_parse_phase_summaries_order_falls_back_to_tree_search() -> None:
    """A shape that doesn't match the guessed container key at all -- the
    same tree-search resilience getPhaseBlockSummaries's own fallback uses."""
    payload = {
        "wrapper": {"races": [{"classCode": "C1", "phaseBlockCode": "1F"}]}
    }
    assert parse_lan_phase_summaries_order(payload) == [("C1", "1F")]


def test_parse_phase_summaries_order_deduplicates_repeated_entries() -> None:
    payload = {"phaseSummaries": [{"classCode": "C1", "phaseCode": "M1"}] * 3}
    assert parse_lan_phase_summaries_order(payload) == [("C1", "M1")]


def test_parse_phase_summaries_order_returns_empty_for_unrecognisable_shape() -> None:
    assert parse_lan_phase_summaries_order({"totallyUnexpected": True}) == []
    assert parse_lan_phase_summaries_order(None) == []
    assert parse_lan_phase_summaries_order([1, 2, 3]) == []


def test_fetch_lan_populates_the_ordering_from_get_phase_summaries(tmp_path) -> None:
    service = SqorzService(
        enabled=True, mode="lan", host="scoring", raw_response_file=tmp_path / "raw.json", clock=Clock()
    )

    def fake_call_lan(func: str, args: list) -> object:
        if func == "getPhaseSummaries":
            return {"phaseSummaries": [{"classCode": "C1", "phaseCode": "M1"}]}
        if func == "getPhaseBlockSummaries":
            return {"phaseBlockSummaries": [{"classCode": "C1", "phaseBlockCode": "M1", "className": "Test"}]}
        return {"competitors": [{"plate": "1", "lastName": "OK", "competitorRankDetails": [{"phaseCode": "M1", "time": "40.0"}]}]}

    service._call_lan = fake_call_lan
    service.get_riders()

    assert service.last_phase_summaries_order == [("C1", "M1")]


def test_fetch_lan_ordering_failure_does_not_break_rider_time_fetching(tmp_path) -> None:
    """The whole point of isolating the getPhaseSummaries call in its own
    try/except: an older Sqorz install without it (or any other failure)
    must degrade ordering to "unverified this poll", never take rider times
    down with it."""
    service = SqorzService(
        enabled=True, mode="lan", host="scoring", raw_response_file=tmp_path / "raw.json", clock=Clock()
    )

    def fake_call_lan(func: str, args: list) -> object:
        if func == "getPhaseSummaries":
            raise ValueError("HTTP 404 -- function does not exist on this Sqorz version")
        if func == "getPhaseBlockSummaries":
            return {"phaseBlockSummaries": [{"classCode": "C1", "phaseBlockCode": "M1", "className": "Test"}]}
        return {"competitors": [{"plate": "1", "lastName": "OK", "competitorRankDetails": [{"phaseCode": "M1", "time": "40.0"}]}]}

    service._call_lan = fake_call_lan
    result = service.get_riders()

    assert result.reachable is True
    assert len(result.riders) == 1
    assert service.last_phase_summaries_order == []


# ---------------------------------------------------------------------------
# parse_org_events_payload / fetch_org_events -- the internet-mode event
# picker (Sqorz-only mode, Change 3). Tested against a real captured
# /json/org/{orgCode} response, not a guess.
# ---------------------------------------------------------------------------


def test_parse_org_events_reads_every_real_event() -> None:
    summaries = parse_org_events_payload(load_org_fixture())
    assert len(summaries) == 5
    names = {s.event_name for s in summaries}
    assert "Hoosier - Day 3" in names
    assert "Great Salt Lake National Day 2" in names


def test_parse_org_events_carries_the_real_event_id_and_date() -> None:
    summaries = parse_org_events_payload(load_org_fixture())
    day3 = next(s for s in summaries if s.event_name == "Hoosier - Day 3")
    assert day3.event_id == "6a8198e2d91badc23cb0c54f"
    assert day3.event_date == "2026-08-16"


def test_parse_org_events_skips_an_entry_missing_required_fields() -> None:
    payload = {"events": [{"eventName": "No ID"}, {"eventId": "e2", "eventName": "Has Both"}]}
    summaries = parse_org_events_payload(payload)
    assert [s.event_name for s in summaries] == ["Has Both"]


def test_parse_org_events_returns_empty_for_a_payload_with_no_events_key() -> None:
    assert parse_org_events_payload({}) == []


def test_fetch_org_events_without_an_org_code_returns_empty_not_an_error() -> None:
    service = SqorzService(enabled=True, mode="internet", org_code="")
    assert service.fetch_org_events() == []


def test_fetch_org_events_returns_real_parsed_events() -> None:
    service = SqorzService(enabled=True, mode="internet", org_code="usabmx")
    service._get_json = lambda url: load_org_fixture()
    events = service.fetch_org_events()
    assert len(events) == 5
    assert events[0].event_name == "Hoosier - Day 3"


def test_fetch_org_events_never_raises_on_a_network_failure() -> None:
    service = SqorzService(enabled=True, mode="internet", org_code="usabmx")

    def boom(url: str) -> dict:
        raise OSError("no route to host")

    service._get_json = boom
    assert service.fetch_org_events() == []


def test_fetch_org_events_calls_the_documented_org_url() -> None:
    service = SqorzService(enabled=True, mode="internet", org_code="usabmx")
    captured = {}

    def capture(url: str) -> dict:
        captured["url"] = url
        return load_org_fixture()

    service._get_json = capture
    service.fetch_org_events()
    assert captured["url"] == "https://our.sqorz.com/json/org/usabmx"


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
