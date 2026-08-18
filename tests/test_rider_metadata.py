from connector.models import LineupRider, ResultRider
from connector.routes.lineup import LINEUP_OVERLAY_HTML
from connector.routes.results import RESULTS_HTML
from connector.services.rider_metadata import format_rider_metadata


def test_rider_metadata_formats_both_values() -> None:
    assert format_rider_metadata(9, "Bend BMX") == "Age 9 · Bend BMX"


def test_rider_metadata_formats_only_present_value() -> None:
    assert format_rider_metadata(9, None) == "Age 9"
    assert format_rider_metadata(None, "Aurora Valley BMX") == "Aurora Valley BMX"
    assert format_rider_metadata(None, "   ") is None
    assert format_rider_metadata(None, "") is None


def test_rider_metadata_keeps_long_track_names_as_text() -> None:
    track = "Northstar Metro BMX Championship Track"
    assert format_rider_metadata(14, track).endswith(track)


def test_rider_metadata_keeps_special_characters_as_plain_text() -> None:
    track = "Aurora <BMX> & Co."
    formatted = format_rider_metadata(7, track)
    assert formatted is not None
    assert formatted.startswith("Age 7 ")
    assert formatted.endswith(track)


def test_rider_api_models_serialize_optional_metadata() -> None:
    lineup = LineupRider(first_name="A", last_name="B", age=12, home_track="Bend BMX")
    result = ResultRider(first_name="A", last_name="B", age=None, home_track="Bend BMX")

    assert lineup.model_dump()["age"] == 12
    assert lineup.model_dump()["home_track"] == "Bend BMX"
    assert result.model_dump()["age"] is None


def test_broadcast_overlays_escape_rider_values_by_using_text_content() -> None:
    for overlay in (LINEUP_OVERLAY_HTML, RESULTS_HTML):
        assert "subtitle.textContent=metadata" in overlay or "subtitle.textContent=metadata;" in overlay
        assert "rider-meta" in overlay
        assert "Number.isInteger(rider.age)" in overlay
        assert "innerHTML" not in overlay
