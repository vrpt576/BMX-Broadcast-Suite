"""No hardened setting may crash BBS at startup -- blank, absent, or garbage.

BBS_SQORZ_POLL_SECONDS='' (exactly what .env.example ships, and exactly what
ConfigurationService.save() writes when a field is cleared) crashed BBS at
import time before FastAPI even loaded (see connector/config.py's history).
That was one instance of a whole class of bug: every non-str setting
(bool/int/float/int|None/Path) has no valid parse of the empty string, and a
typo'd non-blank value is exactly as real a risk as a blank one. Originally
fixed for the Sqorz settings; then extended to BBS_SQL_PORT and the other
numeric/boolean settings a fresh .env can realistically leave empty --
BBS_SQL_PORT specifically because a named SQL instance connection
(`BBS_SQL_INSTANCE`, e.g. HOST\\USABMX) is documented as requiring
BBS_SQL_PORT to be left blank (see connector/config.py's `sql_server`
property), which is exactly the shape that used to crash.

connector/main.py calls `settings = get_settings()` at module import time,
before the FastAPI app object even exists -- so a Settings() construction
that raises IS "the whole connector going down", not just a degraded
feature. Proving Settings(_env_file=...) never raises for any of these
inputs is therefore the precise test for "RaceManager, the Director, and the
existing overlays must still come up" -- nothing else in main.py's
module-level code depends on any one of these fields' values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from connector.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / "connector" / ".env.example"

# Non-Sqorz settings hardened the same way, on top of every BBS_SQORZ_* key
# (discovered directly from .env.example below). Named explicitly, rather
# than auto-discovered like the Sqorz keys, because this is a deliberately
# narrow list -- other pre-existing settings have the identical fragility
# (see connector/config.py's history) but were left alone on purpose.
HARDENED_NON_SQORZ_KEYS = (
    "BBS_SQL_PORT",
    "BBS_SQL_CONNECT_TIMEOUT",
    "BBS_SQL_QUERY_TIMEOUT",
    "BBS_APP_PORT",
    "BBS_SQL_ENCRYPT",
    "BBS_SQL_TRUST_SERVER_CERTIFICATE",
    "BBS_LOG_RETENTION_DAYS",
    "BBS_REMOTE_CONTROL_ENABLED",
    "BBS_REMOTE_ADMIN_ENABLED",
    "BBS_CURRENT_MOTO_DEFAULT",
)


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
HARDENED_KEYS = SQORZ_KEYS + list(HARDENED_NON_SQORZ_KEYS)


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


def test_every_hardened_non_sqorz_key_is_actually_shipped_in_env_example() -> None:
    """Guards HARDENED_NON_SQORZ_KEYS against drift -- if .env.example ever
    renames or drops one of these lines, this fails loudly instead of the
    parametrised test below silently exercising a key that doesn't exist."""
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    shipped = {line.split("=", 1)[0] for line in text.splitlines() if "=" in line}
    for key in HARDENED_NON_SQORZ_KEYS:
        assert key in shipped, f"{key} is no longer in connector/.env.example"


@pytest.mark.parametrize("key", HARDENED_KEYS)
@pytest.mark.parametrize(
    "state,replacement",
    [("blank", ""), ("absent", None), ("garbage", "not-a-real-value###")],
)
def test_every_hardened_setting_survives_blank_absent_and_garbage(
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
        ("sql_port", 1433),
        ("sql_connect_timeout", 2),
        ("sql_query_timeout", 5),
        ("app_port", 8000),
        ("sql_encrypt", True),
        ("sql_trust_server_certificate", True),
        ("log_retention_days", 14),
        ("remote_control_enabled", False),
        ("remote_admin_enabled", False),
        ("current_moto_default", 1),
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
        ("sql_port", 1433),
        ("sql_connect_timeout", 2),
        ("sql_query_timeout", 5),
        ("app_port", 8000),
        ("sql_encrypt", True),
        ("sql_trust_server_certificate", True),
        ("log_retention_days", 14),
        ("remote_control_enabled", False),
        ("remote_admin_enabled", False),
        ("current_moto_default", 1),
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


def test_a_blank_sql_port_still_connects_by_named_instance_not_port() -> None:
    """The actual reason BBS_SQL_PORT is hardened at all: BBS_SQL_INSTANCE
    (e.g. HOST\\USABMX) is documented to require a blank BBS_SQL_PORT, and
    that must both (a) not crash Settings() -- covered above -- and (b)
    still produce an instance-based, not port-based, connection string.
    sql_server's own instance-vs-port precedence is untouched by the
    fallback validator; this only proves the two compose correctly."""
    settings = Settings(_env_file=None, sql_host="hostx", sql_instance="USABMX", sql_port="")

    assert settings.sql_port == 1433  # the validator's fallback -- irrelevant below
    assert settings.sql_server == "hostx\\USABMX"
    assert ",1433" not in settings.sql_server
    assert ",1433" not in settings.connection_string
