"""Mode resolution: whether BBS is running against RaceManager, Sqorz-only,
or neither -- and why. Pure-function tests only; the caching/invalidation
behaviour (get_operating_mode() in connector/dependencies.py, cleared by
ConfigurationService.save() and by the explicit "Re-check" route) is covered
in test_configuration_service.py and test_mode_route.py respectively, since
that behaviour depends on those modules, not this one.
"""

from __future__ import annotations

import pytest

from connector.services.operating_mode_service import (
    OperatingMode,
    check_racemanager_reachable,
    resolve_operating_mode,
)


# ---------------------------------------------------------------------------
# resolve_operating_mode -- override first, then RaceManager, then Sqorz,
# then neither. Order matters: this is the exact precedence the design note
# specifies and the whole rest of 1.3.2 depends on.
# ---------------------------------------------------------------------------


def test_racemanager_reachable_wins_by_default() -> None:
    decision = resolve_operating_mode(
        racemanager_reachable=True, sqorz_enabled=False, force_sqorz_only=False
    )
    assert decision.mode is OperatingMode.RACEMANAGER
    assert "RaceManager" in decision.reason


def test_racemanager_reachable_still_wins_even_if_sqorz_is_also_configured() -> None:
    """A working RaceManager install is never second-guessed just because
    Sqorz also happens to be configured -- RaceManager is the common case
    and must not silently lose to Sqorz."""
    decision = resolve_operating_mode(
        racemanager_reachable=True, sqorz_enabled=True, force_sqorz_only=False
    )
    assert decision.mode is OperatingMode.RACEMANAGER


def test_unreachable_racemanager_with_sqorz_enabled_falls_to_sqorz_only() -> None:
    decision = resolve_operating_mode(
        racemanager_reachable=False, sqorz_enabled=True, force_sqorz_only=False
    )
    assert decision.mode is OperatingMode.SQORZ_ONLY
    assert "Sqorz" in decision.reason


def test_neither_racemanager_nor_sqorz_is_unavailable() -> None:
    decision = resolve_operating_mode(
        racemanager_reachable=False, sqorz_enabled=False, force_sqorz_only=False
    )
    assert decision.mode is OperatingMode.UNAVAILABLE
    assert "/setup" in decision.reason


def test_force_sqorz_only_overrides_a_reachable_racemanager() -> None:
    """The one explicit override this design calls for: a track with both
    RaceManager and Sqorz configured that wants Sqorz-only anyway. An
    operator's explicit choice always wins over automatic detection."""
    decision = resolve_operating_mode(
        racemanager_reachable=True, sqorz_enabled=True, force_sqorz_only=True
    )
    assert decision.mode is OperatingMode.SQORZ_ONLY
    assert "explicitly enabled" in decision.reason


def test_force_sqorz_only_without_sqorz_enabled_does_not_force_anything() -> None:
    """The override can't force BBS into a mode that has nothing configured
    to run -- force_sqorz_only_mode=true with sqorz_enabled=false must fall
    through to ordinary detection rather than landing on a nonsensical
    "Sqorz-only, no Sqorz configured" state."""
    decision = resolve_operating_mode(
        racemanager_reachable=True, sqorz_enabled=False, force_sqorz_only=True
    )
    assert decision.mode is OperatingMode.RACEMANAGER


def test_force_sqorz_only_without_sqorz_enabled_and_no_racemanager_is_unavailable() -> None:
    decision = resolve_operating_mode(
        racemanager_reachable=False, sqorz_enabled=False, force_sqorz_only=True
    )
    assert decision.mode is OperatingMode.UNAVAILABLE


@pytest.mark.parametrize(
    "racemanager_reachable,sqorz_enabled,force_sqorz_only",
    [
        (True, False, False),
        (True, True, False),
        (False, True, False),
        (False, False, False),
        (True, True, True),
        (True, False, True),
        (False, False, True),
    ],
)
def test_reason_is_always_a_non_empty_plain_language_string(
    racemanager_reachable: bool, sqorz_enabled: bool, force_sqorz_only: bool
) -> None:
    decision = resolve_operating_mode(
        racemanager_reachable=racemanager_reachable,
        sqorz_enabled=sqorz_enabled,
        force_sqorz_only=force_sqorz_only,
    )
    assert isinstance(decision.reason, str)
    assert decision.reason.strip()


# ---------------------------------------------------------------------------
# check_racemanager_reachable -- never raises, regardless of what the
# database throws
# ---------------------------------------------------------------------------


class _FakeDatabaseOk:
    def fetch_one(self, query: str):
        return {"ok": 1}


class _FakeDatabaseRaises:
    def fetch_one(self, query: str):
        raise RuntimeError("connection refused")


def test_reachable_database_returns_true() -> None:
    assert check_racemanager_reachable(_FakeDatabaseOk()) is True


def test_unreachable_database_returns_false_not_an_exception() -> None:
    assert check_racemanager_reachable(_FakeDatabaseRaises()) is False


def test_a_database_that_raises_something_unusual_still_does_not_propagate() -> None:
    """An unreachable database, missing driver, or blank configuration are
    all just "not reachable right now" from mode resolution's point of view
    -- the specific exception type must never leak out of this function."""

    class _FakeDatabaseRaisesOddly:
        def fetch_one(self, query: str):
            raise ValueError("not even a connection-shaped error")

    assert check_racemanager_reachable(_FakeDatabaseRaisesOddly()) is False
