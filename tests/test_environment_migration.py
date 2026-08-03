"""Configuration migration must preserve every existing operator value."""

from __future__ import annotations

import hashlib
from pathlib import Path

from connector.environment_migration import ensure_environment_defaults


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_existing_values_survive_and_missing_keys_are_appended(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    defaults = tmp_path / "defaults.env"
    target.write_text(
        "# Track-owned order and comments\n"
        "BBS_SQL_HOST=track-sql.example\n"
        "BBS_SQL_DATABASE=CUSTOM_RACE\n"
        "BBS_SQL_USER=operator_readonly\n"
        "BBS_SQL_PASSWORD=do-not-print-this-secret\n"
        "BBS_DEFAULT_THEME=track-theme\n"
        "BBS_APP_HOST=0.0.0.0\n"
        "BBS_ADMIN_TOKEN=existing-admin-secret\n",
        encoding="utf-8",
    )
    defaults.write_text(
        "BBS_SQL_HOST=localhost\n"
        "BBS_SQL_DATABASE=RACE\n"
        "BBS_SQL_USER=bbs_connector\n"
        "BBS_SQL_PASSWORD=replace-me\n"
        "BBS_DEFAULT_THEME=default\n"
        "BBS_APP_HOST=127.0.0.1\n"
        "BBS_ADMIN_TOKEN=\n"
        "BBS_REMOTE_ADMIN_ENABLED=false\n"
        "BBS_RESULTS_ROLL_STATE_FILE=data/results_roll.json\n",
        encoding="utf-8",
    )

    result = ensure_environment_defaults(target, defaults)
    content = target.read_text(encoding="utf-8")

    assert result.created is False
    assert result.added_keys == (
        "BBS_REMOTE_ADMIN_ENABLED",
        "BBS_RESULTS_ROLL_STATE_FILE",
    )
    assert "BBS_SQL_HOST=track-sql.example" in content
    assert "BBS_SQL_DATABASE=CUSTOM_RACE" in content
    assert "BBS_SQL_USER=operator_readonly" in content
    assert "BBS_SQL_PASSWORD=do-not-print-this-secret" in content
    assert "BBS_DEFAULT_THEME=track-theme" in content
    assert "BBS_APP_HOST=0.0.0.0" in content
    assert "BBS_ADMIN_TOKEN=existing-admin-secret" in content
    assert "BBS_REMOTE_ADMIN_ENABLED=false" in content
    assert "BBS_RESULTS_ROLL_STATE_FILE=data/results_roll.json" in content
    assert "replace-me" not in content
    assert "existing-admin-secret" not in repr(result)
    assert "do-not-print-this-secret" not in repr(result)


def test_reinstall_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    defaults = tmp_path / "defaults.env"
    target.write_text("BBS_SQL_PASSWORD=kept\n", encoding="utf-8")
    defaults.write_text(
        "BBS_SQL_PASSWORD=replace-me\nBBS_REMOTE_CONTROL_ENABLED=false\n",
        encoding="utf-8",
    )

    first = ensure_environment_defaults(target, defaults)
    first_hash = digest(target)
    second = ensure_environment_defaults(target, defaults)

    assert first.changed is True
    assert second.changed is False
    assert second.added_keys == ()
    assert digest(target) == first_hash


def test_missing_environment_is_created_from_packaged_defaults(tmp_path: Path) -> None:
    target = tmp_path / "protected" / ".env"
    defaults = tmp_path / "defaults.env"
    defaults.write_text("BBS_APP_PORT=8000\n", encoding="utf-8")

    result = ensure_environment_defaults(target, defaults)

    assert result.created is True
    assert target.read_text(encoding="utf-8") == "BBS_APP_PORT=8000\n"
