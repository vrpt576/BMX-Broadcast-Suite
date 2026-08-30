"""Local defaults and explicit remote access policy coverage."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from connector.config import Settings
from connector.security import evaluate_http_access


def decide(
    settings: Settings,
    *,
    method: str = "GET",
    path: str = "/api/current",
    host: str = "192.0.2.44",
    headers: dict[str, str] | None = None,
):
    return evaluate_http_access(
        settings,
        method=method,
        path=path,
        client_host=host,
        headers=headers or {},
    )


def test_default_bind_and_cors_are_local_only() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_host == "127.0.0.1"
    assert settings.remote_control_enabled is False
    assert settings.remote_admin_enabled is False
    assert settings.cors_origin_list == [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]


def test_legacy_cors_wildcard_is_narrowed_instead_of_trusted() -> None:
    settings = Settings(_env_file=None, cors_origins="*")

    assert "*" not in settings.cors_origin_list
    assert settings.cors_origin_list == [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]


def test_remote_read_only_graphics_data_remains_available() -> None:
    decision = decide(Settings(_env_file=None), path="/api/lineup/current")

    assert decision.allowed is True


def test_local_director_mutation_remains_backwards_compatible() -> None:
    decision = decide(
        Settings(_env_file=None),
        method="POST",
        path="/api/current/next",
        host="127.0.0.1",
    )

    assert decision.allowed is True


def test_remote_mutation_is_rejected_by_default() -> None:
    decision = decide(
        Settings(_env_file=None),
        method="POST",
        path="/api/current/next",
    )

    assert decision.allowed is False
    assert decision.status_code == 403
    assert "disabled" in decision.detail


def test_remote_control_requires_the_configured_token() -> None:
    settings = Settings(
        _env_file=None,
        remote_control_enabled=True,
        control_token="track-control-secret",
    )

    missing = decide(settings, method="POST", path="/api/current/next")
    wrong = decide(
        settings,
        method="POST",
        path="/api/current/next",
        headers={"x-bbs-control-token": "wrong"},
    )
    allowed = decide(
        settings,
        method="POST",
        path="/api/current/next",
        headers={"x-bbs-control-token": "track-control-secret"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert allowed.allowed is True


def test_remote_configuration_requires_separate_admin_opt_in() -> None:
    control_only = Settings(
        _env_file=None,
        remote_control_enabled=True,
        control_token="control",
    )
    configured = Settings(
        _env_file=None,
        remote_admin_enabled=True,
        admin_token="admin-secret",
    )

    rejected = decide(
        control_only,
        method="PUT",
        path="/api/configuration",
        headers={"x-bbs-control-token": "control"},
    )
    allowed = decide(
        configured,
        method="PUT",
        path="/api/configuration",
        headers={"x-bbs-admin-token": "admin-secret"},
    )

    assert rejected.status_code == 403
    assert allowed.allowed is True


def test_sensitive_remote_reads_require_admin_token_but_public_theme_config_does_not() -> None:
    settings = Settings(
        _env_file=None,
        remote_admin_enabled=True,
        admin_token="admin-secret",
    )

    diagnostics = decide(settings, path="/api/diagnostics")
    authorized = decide(
        settings,
        path="/api/diagnostics",
        headers={"authorization": "Bearer admin-secret"},
    )
    public_theme = decide(settings, path="/api/configuration/public")

    assert diagnostics.status_code == 401
    assert authorized.allowed is True
    assert public_theme.allowed is True


def test_remote_theme_lookup_is_public_but_theme_mutation_is_not() -> None:
    """Regression test for the bend-bmx LAN theme bug.

    Overlays fetch `/api/themes/{slug}` client-side from whatever host the
    overlay page itself was loaded from (see lineup.py's applyTheme()). If a
    GET there required the admin token like the mutating endpoints do, every
    non-loopback client — any LAN OBS machine, any browser other than one on
    the BBS host — would get a 403, silently keep the overlay's bundled
    default colors, and it would look like the custom theme "only works on
    127.0.0.1".
    """
    settings = Settings(_env_file=None)

    list_themes = decide(settings, path="/api/themes")
    get_theme = decide(settings, path="/api/themes/bend-bmx")
    save_theme = decide(settings, method="PUT", path="/api/themes/bend-bmx")
    reset_theme = decide(settings, method="POST", path="/api/themes/bend-bmx/reset")

    assert list_themes.allowed is True
    assert get_theme.allowed is True
    assert save_theme.allowed is False
    assert save_theme.status_code == 403
    assert reset_theme.allowed is False
    assert reset_theme.status_code == 403


def test_untrusted_cors_origin_is_not_accepted() -> None:
    settings = Settings(_env_file=None)
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type", "X-BBS-Control-Token"],
    )

    @app.get("/value")
    def value():
        return {"ok": True}

    response = TestClient(app).options(
        "/value",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_setup_wizard_is_loopback_only_even_with_a_valid_admin_token() -> None:
    """The Setup wizard (Part 1 prerequisite install, Part 2 SQL account
    creation) runs system-level installs and creates database accounts --
    unlike every other admin path, no token can ever substitute for being
    on the BBS host itself."""
    settings = Settings(
        _env_file=None,
        remote_admin_enabled=True,
        admin_token="admin-secret",
    )

    remote_with_valid_token = decide(
        settings,
        method="POST",
        path="/api/setup/sql/admin-setup",
        headers={"x-bbs-admin-token": "admin-secret"},
    )
    remote_read_only = decide(settings, method="GET", path="/api/setup/status")
    remote_with_bearer_token = decide(
        settings,
        method="POST",
        path="/api/setup/odbc/install",
        headers={"authorization": "Bearer admin-secret"},
    )

    assert remote_with_valid_token.allowed is False
    assert remote_with_valid_token.status_code == 403
    assert remote_read_only.allowed is False
    assert remote_with_bearer_token.allowed is False


def test_setup_wizard_works_locally_with_no_token_at_all() -> None:
    settings = Settings(_env_file=None)  # remote admin not even enabled

    local_read = decide(settings, method="GET", path="/api/setup/status", host="127.0.0.1")
    local_write = decide(
        settings, method="POST", path="/api/setup/sql/admin-setup", host="127.0.0.1"
    )

    assert local_read.allowed is True
    assert local_write.allowed is True
