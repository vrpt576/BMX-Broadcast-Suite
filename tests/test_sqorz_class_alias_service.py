"""Operator-editable Sqorz class aliases: local file, atomic, no cache."""

from __future__ import annotations

from pathlib import Path

from connector.services.sqorz_class_alias_service import SqorzClassAliasStore


def test_no_file_yet_returns_no_aliases(tmp_path: Path) -> None:
    store = SqorzClassAliasStore(tmp_path / "aliases.json")
    assert store.get_alias("11-12 Open") is None
    assert store.all_aliases() == {}


def test_set_then_get_round_trips(tmp_path: Path) -> None:
    store = SqorzClassAliasStore(tmp_path / "aliases.json")
    store.set_alias("11-12 Open", "2204")
    assert store.get_alias("11-12 Open") == "2204"
    assert store.all_aliases() == {"11-12 Open": "2204"}


def test_a_second_store_instance_sees_the_same_file_immediately(tmp_path: Path) -> None:
    """No in-memory cache -- an alias saved by one request is visible to
    the very next request without restarting BBS."""
    path = tmp_path / "aliases.json"
    SqorzClassAliasStore(path).set_alias("11-12 Open", "2204")

    fresh = SqorzClassAliasStore(path)
    assert fresh.get_alias("11-12 Open") == "2204"


def test_setting_none_or_blank_clears_the_alias(tmp_path: Path) -> None:
    store = SqorzClassAliasStore(tmp_path / "aliases.json")
    store.set_alias("11-12 Open", "2204")
    store.set_alias("11-12 Open", None)
    assert store.get_alias("11-12 Open") is None

    store.set_alias("13-14 Open", "2205")
    store.set_alias("13-14 Open", "   ")
    assert store.get_alias("13-14 Open") is None


def test_multiple_class_aliases_are_independent(tmp_path: Path) -> None:
    store = SqorzClassAliasStore(tmp_path / "aliases.json")
    store.set_alias("11-12 Open", "2204")
    store.set_alias("13-14 Open", "2205")
    assert store.all_aliases() == {"11-12 Open": "2204", "13-14 Open": "2205"}


def test_write_is_atomic_no_temp_file_left_behind(tmp_path: Path) -> None:
    path = tmp_path / "aliases.json"
    store = SqorzClassAliasStore(path)
    store.set_alias("11-12 Open", "2204")
    assert path.exists()
    assert not (tmp_path / f".{path.name}.tmp").exists()
