"""scripts/sqorz_probe.py: the standalone kit sent to an unfamiliar track.

This script deliberately has zero imports from connector/ or tests/ (it has
to run on a machine that's never cloned this repo) -- these tests import it
directly by path instead, and exercise it against the real mock LAN server
from scripts/sqorz_lan_mock.py for genuine end-to-end coverage.
"""

from __future__ import annotations

import importlib.util
import socket
import sys
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from sqorz_lan_mock import MockSqorzLanServer  # noqa: E402


def _load_probe():
    spec = importlib.util.spec_from_file_location("sqorz_probe", SCRIPTS_DIR / "sqorz_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_probe()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def mock_server() -> Iterator[MockSqorzLanServer]:
    server = MockSqorzLanServer(host="127.0.0.1", port=_free_port())
    server.start()
    try:
        yield server
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# End to end: real HTTP calls against the real mock, real files on disk
# ---------------------------------------------------------------------------


def test_end_to_end_writes_one_file_per_function_and_zips_the_folder(
    tmp_path: Path, mock_server: MockSqorzLanServer
) -> None:
    out_dir = tmp_path / "results"

    argv_backup = sys.argv
    sys.argv = [
        "sqorz_probe.py",
        "--host",
        mock_server.host,
        "--port",
        str(mock_server.port),
        "--out-dir",
        str(out_dir),
        "--no-header",
    ]
    try:
        exit_code = probe.main()
    finally:
        sys.argv = argv_backup

    assert exit_code == 0
    for func, _ in probe.FUNCTIONS:
        assert (out_dir / f"{func}.json").exists()

    zip_path = out_dir.with_suffix(".zip")
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as archive:
        names = {Path(name).name for name in archive.namelist() if name.endswith(".json")}
    assert names == {f"{func}.json" for func, _ in probe.FUNCTIONS}


def test_end_to_end_finds_real_data_in_at_least_one_response(
    tmp_path: Path, mock_server: MockSqorzLanServer
) -> None:
    """Not just "didn't crash" -- confirms the probe actually surfaces the
    real riders/classes the mock (built from the real Hoosier fixture)
    returns, via its own plain-English item counting."""
    argv_backup = sys.argv
    sys.argv = [
        "sqorz_probe.py",
        "--host",
        mock_server.host,
        "--port",
        str(mock_server.port),
        "--out-dir",
        str(tmp_path / "results"),
        "--no-header",
    ]
    try:
        exit_code = probe.main()
    finally:
        sys.argv = argv_backup

    assert exit_code == 0
    detail = (tmp_path / "results" / "getPhaseRankDetail.json").read_text(encoding="utf-8")
    assert "MURFIN" in detail.upper()


def test_an_unreachable_host_still_writes_and_zips_results(tmp_path: Path) -> None:
    """Nothing answering is itself useful information -- must still produce
    the zip (with empty/error files), never crash, and exit non-zero."""
    argv_backup = sys.argv
    sys.argv = [
        "sqorz_probe.py",
        "--host",
        "192.0.2.1",  # RFC 5737 TEST-NET-1 -- guaranteed unreachable
        "--port",
        "4343",
        "--timeout",
        "0.3",
        "--out-dir",
        str(tmp_path / "results"),
        "--no-header",
    ]
    try:
        exit_code = probe.main()
    finally:
        sys.argv = argv_backup

    assert exit_code == 1
    assert (tmp_path / "results").with_suffix(".zip").exists()


# ---------------------------------------------------------------------------
# Small helpers, in isolation
# ---------------------------------------------------------------------------


def test_count_items_reads_a_list_or_a_dict_wrapping_one() -> None:
    assert probe._count_items([1, 2, 3]) == 3
    assert probe._count_items({"phaseBlockSummaries": [1, 2]}) == 2
    assert probe._count_items({"nothing": "here"}) is None
    assert probe._count_items(None) is None


def test_friendly_failure_reason_covers_the_common_cases() -> None:
    assert "wrong address" in probe.friendly_failure_reason(
        {"http_status": None, "raw_text": "urlopen error timed out"}
    )
    assert "Couldn't connect" in probe.friendly_failure_reason(
        {"http_status": None, "raw_text": "connection refused"}
    )
    assert "doesn't seem to exist" in probe.friendly_failure_reason(
        {"http_status": 404, "raw_text": ""}
    )
    assert "HTTP 500" in probe.friendly_failure_reason({"http_status": 500, "raw_text": ""})


def test_detect_local_subnet_returns_a_slash_24_or_none() -> None:
    result = probe.detect_local_subnet()
    assert result is None or result.endswith(".0/24")


# ---------------------------------------------------------------------------
# Interactive prompt flow (double-click / no-args mode)
# ---------------------------------------------------------------------------


def test_prompt_for_host_returns_none_when_not_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Piped/non-interactive stdin must never hang on input() -- confirmed
    by exercising the real isatty() check, not a mock of it."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert probe.prompt_for_host(4343) is None


def test_prompt_for_host_uses_a_typed_ip_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "10.0.0.5")
    assert probe.prompt_for_host(4343) == "10.0.0.5"


def test_prompt_for_host_scans_when_nothing_typed(
    monkeypatch: pytest.MonkeyPatch, mock_server: MockSqorzLanServer
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    monkeypatch.setattr(probe, "detect_local_subnet", lambda: "127.0.0.0/24")

    found = probe.prompt_for_host(mock_server.port)

    assert found == mock_server.host


def test_prompt_for_host_falls_back_to_manual_entry_when_scan_finds_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["", "10.0.0.9"])  # first Enter (scan), then typed after scan finds nothing
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr(probe, "detect_local_subnet", lambda: "203.0.113.0/24")  # RFC 5737, empty

    assert probe.prompt_for_host(4343) == "10.0.0.9"
