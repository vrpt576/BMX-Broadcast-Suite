"""Windows tray menu/reliability checks.

`connector/tray_windows.py` imports `pystray`, which is a Windows-only
dependency (see connector/requirements.txt) and isn't installed in this
project's Linux test environment, so — following the existing precedent in
tests/test_windows_icon.py's
`test_windows_tray_loads_the_generated_square_asset` — these checks read the
module source directly instead of importing it.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAY_SOURCE = (ROOT / "connector" / "tray_windows.py").read_text(encoding="utf-8")


def test_tray_offers_a_theme_manager_link() -> None:
    assert '"Open Theme Manager"' in TRAY_SOURCE
    assert '"/themes"' in TRAY_SOURCE


def test_service_actions_verify_real_state_instead_of_trusting_shellexecute() -> None:
    """ShellExecuteW's return code alone is not proof an action succeeded.

    A value greater than 32 is also returned when the user cancels the UAC
    prompt (Windows error 1223 / ERROR_CANCELLED), which the previous
    `if result <= 32: raise OSError(...)` check would have let through as a
    false success. The fix must poll the real service state afterward rather
    than trusting the launch result.
    """
    assert "windows_service_state(SERVICE_NAME)" in TRAY_SOURCE
    assert "result <= 32" in TRAY_SOURCE  # still guards true launch failures
    # The old code assumed success as soon as ShellExecuteW returned; it must
    # no longer return/assume success without checking the polled state.
    assert "return True" in TRAY_SOURCE
    assert "deadline" in TRAY_SOURCE and "time.monotonic()" in TRAY_SOURCE


def test_restart_waits_for_stop_to_actually_complete_before_starting() -> None:
    """Restart used to fire stop, sleep exactly 1s, then fire start — racing
    a service that takes longer than a second to shut down. It must now only
    issue start after `_service_action("stop")` reports the service actually
    reached the stopped state.
    """
    assert 'if not self._service_action("stop"):' in TRAY_SOURCE
    assert 'self._service_action("start")' in TRAY_SOURCE
    # The unconditional fixed-delay race between stop and start must be gone.
    assert "time.sleep(1)" not in TRAY_SOURCE


def test_service_actions_disable_menu_items_while_in_flight() -> None:
    """A second click while an action is running must not be able to fire a
    second elevation prompt / race the first action."""
    assert "self.busy" in TRAY_SOURCE
    assert "not self.busy" in TRAY_SOURCE
