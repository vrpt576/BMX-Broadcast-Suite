"""LAN-mode request/response mechanics against a mock Sqorz LAN server.

Uses scripts/sqorz_lan_mock.py, whose response shapes are GUESSES (Sqorz has
never published the real LAN API's format -- see that module's docstring
and connector/services/sqorz_service.py's). What passing here proves: BBS
sends a correctly-shaped request (method, URL, content-type, JSON-array
body) and correctly handles a 200 response, a real socket timeout, and a
connection dropping mid-poll (last-known-good served and flagged stale, not
blanked). It does NOT prove BBS parses Smith Rock's real scoring computer's
actual response shape -- that is still unverified until confirmed on site
with scripts/sqorz_probe.py. Do not treat a pass here as LAN contract
verification.
"""

from __future__ import annotations

import socket
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sqorz_lan_mock import MockSqorzLanServer  # noqa: E402

from connector.services.sqorz_overlay_service import build_overlay_state
from connector.services.sqorz_service import SqorzService


class Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


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


def test_lan_mode_end_to_end_fetches_and_parses_real_looking_riders(
    mock_server: MockSqorzLanServer,
) -> None:
    service = SqorzService(
        enabled=True,
        mode="lan",
        host=mock_server.host,
        port=mock_server.port,
        timeout_seconds=2.0,
    )

    result = service.get_riders()

    assert result.reachable is True
    assert result.error is None
    assert result.riders
    murfin_moto1 = next(
        row for row in result.riders if row.last_name == "MURFIN" and row.phase_code == "M1"
    )
    assert murfin_moto1.time_seconds == 47.529


def test_lan_mode_end_to_end_renders_a_real_overlay_race(mock_server: MockSqorzLanServer) -> None:
    service = SqorzService(
        enabled=True,
        mode="lan",
        host=mock_server.host,
        port=mock_server.port,
        timeout_seconds=2.0,
    )

    state = build_overlay_state(service, class_name="11-12 Open", phase_code="M1")

    assert state.enabled is True
    assert state.reachable is True
    assert state.race is not None
    assert state.race.riders
    assert any(rider.last_name == "MURFIN" for rider in state.race.riders)


def test_a_real_socket_timeout_actually_fires(mock_server: MockSqorzLanServer) -> None:
    mock_server.delay_seconds = 3.0  # longer than BBS's own configured timeout below
    service = SqorzService(
        enabled=True,
        mode="lan",
        host=mock_server.host,
        port=mock_server.port,
        timeout_seconds=1.0,
    )

    started = time.monotonic()
    result = service.get_riders()
    elapsed = time.monotonic() - started

    assert result.reachable is False
    assert result.riders == []
    assert result.error
    # Nowhere near the mock's 3s delay -- proves the 1s timeout fired, not
    # that the mock happened to answer quickly.
    assert elapsed < 2.5


def test_the_overlay_holds_last_known_good_and_flags_stale_when_the_connection_drops_mid_poll(
    mock_server: MockSqorzLanServer,
) -> None:
    clock = Clock()
    service = SqorzService(
        enabled=True,
        mode="lan",
        host=mock_server.host,
        port=mock_server.port,
        timeout_seconds=1.0,
        poll_seconds=5.0,
        clock=clock,
    )

    first = service.get_riders()
    assert first.reachable is True
    assert first.riders

    mock_server.stop()  # simulates the scoring computer disappearing mid-event
    clock.advance(6)  # past poll_seconds -- the next call is due to refetch

    second = service.get_riders()
    assert second.reachable is False
    assert second.riders == first.riders  # last-known-good, never blanked
    assert second.error

    clock.advance(20)  # well past poll_seconds * 3
    third = service.get_riders()
    assert third.stale is True
    assert third.riders == first.riders

    state = build_overlay_state(service, class_name="11-12 Open", phase_code="M1")
    assert state.stale is True
    assert state.race is not None  # the overlay still has something to show
    assert state.race.riders
