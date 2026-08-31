"""/setup's Sqorz-only-mode additions: the mode banner (Change 1, same
requirement as /director) and the "I don't use RaceManager" path that
skips straight to Sqorz configuration without touching the ODBC/SQL cards.
"""

from __future__ import annotations

from connector.routes.setup import SETUP_HTML


def test_mode_banner_exists_with_a_recheck_button() -> None:
    assert 'id="mode-value"' in SETUP_HTML
    assert 'id="mode-reason"' in SETUP_HTML
    assert 'id="mode-recheck"' in SETUP_HTML
    assert "fetch('/api/mode'" in SETUP_HTML
    assert "fetch('/api/mode/recheck'" in SETUP_HTML
    assert "setInterval(loadMode" not in SETUP_HTML  # explicit re-check only, no timer


def test_recheck_shows_the_decision_before_and_after() -> None:
    assert "d.before" in SETUP_HTML
    assert "d.after" in SETUP_HTML
    assert "mode-recheck-detail" in SETUP_HTML


def test_skip_to_sqorz_link_exists_and_never_touches_the_sql_apis() -> None:
    """The skip path is purely a visual de-emphasis of the ODBC/SQL cards
    plus a scroll -- it must never call any of the SQL setup endpoints
    (those stay entirely operator-initiated elsewhere on the page)."""
    assert 'id="skip-to-sqorz"' in SETUP_HTML
    skip_handler = SETUP_HTML[
        SETUP_HTML.index("document.querySelector('#skip-to-sqorz')") :
        SETUP_HTML.index("loadStatus();")
    ]
    assert "/api/setup/sql" not in skip_handler
    assert "/api/setup/odbc" not in skip_handler


def test_skip_to_sqorz_marks_odbc_and_sql_cards_as_not_required() -> None:
    assert "document.querySelector('#odbc-card').classList.add('skipped')" in SETUP_HTML
    assert "document.querySelector('#sql-card').classList.add('skipped')" in SETUP_HTML
    assert "Not required for Sqorz-only mode" in SETUP_HTML


def test_skip_to_sqorz_scrolls_to_the_sqorz_card_not_a_duplicated_form() -> None:
    """No new Sqorz config form on this page -- reuses the existing one at
    /configuration rather than maintaining Sqorz settings in two places."""
    assert "sqorz-card" in SETUP_HTML
    assert "scrollIntoView" in SETUP_HTML
    assert 'href="/configuration"' in SETUP_HTML


def test_odbc_and_sql_cards_remain_fully_functional_when_not_skipped() -> None:
    """The skip path must be purely additive -- every existing setup id
    this project's own test_setup_route.py already exercises must still be
    present and untouched."""
    for identifier in (
        "odbc-install-bundled", "odbc-install-download",
        "auto-setup-btn", "admin-setup-btn", "verify-btn", "dba-generate-btn",
    ):
        assert f'id="{identifier}"' in SETUP_HTML
