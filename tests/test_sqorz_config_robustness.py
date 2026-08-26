"""No Sqorz setting may crash BBS at startup -- blank, absent, or garbage.

BBS_SQORZ_POLL_SECONDS='' (exactly what .env.example ships, and exactly what
ConfigurationService.save() writes when a field is cleared) crashed BBS at
import time before FastAPI even loaded (see connector/config.py's history).
That was one instance of a whole class of bug: every non-str Sqorz setting
(bool/int/float/int|None/Path) has no valid parse of the empty string, and a
typo'd non-blank value is exactly as real a risk as a blank one.

connector/main.py calls `settings = get_settings()` at module import time,
before the FastAPI app object even exists -- so a Settings() construction
that raises IS "the whole connector going down", not just a degraded Sqorz
feature. Proving Settings(_env_file=...) never raises for any of these
inputs is therefore the precise test for "RaceManager, the Director, and the
existing overlays must still come up" -- nothing else in main.py's
module-level code depends on a Sqorz field's value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from connector.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / "connector" / ".env.example"


def _sqorz_keys() -> list[str]:
    """Every BBS_SQORZ_* key actually shipped in .env.example -- so a future
    setting added to that file is automatically covered here without anyone
    having to remember to update this list by hand."""
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    return [
        line.split("=", 1)[0]
        for line in text.splitlines()
        if line.startswith("BBS_SQORZ_")
    ]


SQORZ_KEYS = _sqorz_keys()


def _example_with(key: str, replacement: str | None) -> str:
    """The real, complete .env.example, with just `key`'s line blanked,
    garbled, or removed entirely (replacement=None) -- the realistic shape
    of what actually goes wrong: one bad line in an otherwise-normal file,
    not a totally empty one."""
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if line.startswith(key + "="):
            if replacement is not None:
                out.append(f"{key}={replacement}")
            # replacement is None -> line dropped entirely (key absent)
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def test_sqorz_keys_were_actually_found() -> None:
    """Guards the whole module against a silent no-op if .env.example ever
    stops shipping any BBS_SQORZ_* lines -- the parametrised test below
    would otherwise just quietly collect zero cases."""
    assert len(SQORZ_KEYS) >= 9


@pytest.mark.parametrize("key", SQORZ_KEYS)
@pytest.mark.parametrize(
    "state,replacement",
    [("blank", ""), ("absent", None), ("garbage", "not-a-real-value###")],
)
def test_every_shipped_sqorz_setting_survives_blank_absent_and_garbage(
    tmp_path: Path, key: str, state: str, replacement: str | None
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(_example_with(key, replacement), encoding="utf-8")

    Settings(_env_file=env_file)  # must not raise, for any key or state


# ---------------------------------------------------------------------------
# Targeted checks: blank/absent falls back to the field's own declared
# default, and a genuinely unparseable garbage value both falls back AND
# prints a clear, startup-time warning naming the setting.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,default",
    [
        ("sqorz_enabled", False),
        ("sqorz_port", 4343),
        ("sqorz_poll_seconds", None),
        ("sqorz_timeout_seconds", 2.0),
        ("sqorz_class_alias_file", Path("data/sqorz_class_aliases.json")),
    ],
)
def test_blank_falls_back_to_the_declared_default(field: str, default: object) -> None:
    assert getattr(Settings(_env_file=None, **{field: ""}), field) == default


@pytest.mark.parametrize(
    "field,default",
    [
        ("sqorz_enabled", False),
        ("sqorz_port", 4343),
        ("sqorz_poll_seconds", None),
        ("sqorz_timeout_seconds", 2.0),
    ],
)
def test_garbage_falls_back_to_the_default_and_warns_by_name(
    field: str, default: object, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = Settings(_env_file=None, **{field: "not-a-real-value###"})

    assert getattr(settings, field) == default
    warning = capsys.readouterr().err
    assert f"BBS_{field.upper()}" in warning
    assert "not-a-real-value###" in warning


def test_blank_sqorz_class_alias_file_does_not_silently_become_the_current_directory() -> None:
    """Path("") == Path(".") -- before the fallback validator, a blank
    BBS_SQORZ_CLASS_ALIAS_FILE would have pointed the alias store at the
    entire runtime root directory instead of a JSON file. Doesn't crash
    startup (Path accepts any string), which is exactly why this needed its
    own check rather than relying on the generic "no exception" test above."""
    settings = Settings(_env_file=None, sqorz_class_alias_file="")
    assert settings.sqorz_class_alias_file == Path("data/sqorz_class_aliases.json")


class TestSqorzModeFallback:
    def test_blank_falls_back_to_internet(self) -> None:
        assert Settings(_env_file=None, sqorz_mode="").sqorz_mode == "internet"

    def test_unrecognised_value_falls_back_to_internet_and_warns(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        settings = Settings(_env_file=None, sqorz_mode="not-a-real-value###")

        assert settings.sqorz_mode == "internet"
        warning = capsys.readouterr().err
        assert "BBS_SQORZ_MODE" in warning
        assert "not-a-real-value###" in warning

    def test_recognised_value_is_case_and_whitespace_insensitive(self) -> None:
        assert Settings(_env_file=None, sqorz_mode=" LAN ").sqorz_mode == "lan"
        assert Settings(_env_file=None, sqorz_mode="File").sqorz_mode == "file"


def test_a_real_value_still_coerces_correctly_for_every_fragile_field() -> None:
    """The fallback validators must not interfere with legitimate values --
    only blank/unparseable input should ever be touched."""
    settings = Settings(
        _env_file=None,
        sqorz_enabled="true",
        sqorz_port="9999",
        sqorz_poll_seconds="7",
        sqorz_timeout_seconds="3.5",
        sqorz_class_alias_file="custom/aliases.json",
    )
    assert settings.sqorz_enabled is True
    assert settings.sqorz_port == 9999
    assert settings.sqorz_poll_seconds == 7
    assert settings.sqorz_timeout_seconds == 3.5
    assert settings.sqorz_class_alias_file == Path("custom/aliases.json")


def test_whitespace_padded_numeric_values_still_parse() -> None:
    """A pasted value with surrounding whitespace -- explicitly called out
    as a real-world "garbage" shape -- must still parse as the intended
    number, not be treated as unparseable."""
    assert Settings(_env_file=None, sqorz_port=" 4343 ").sqorz_port == 4343
