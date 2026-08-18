from connector.routes.themes import THEMES_HTML
from connector.security import evaluate_http_access
from connector.config import Settings


def test_theme_manager_offers_safe_editing_and_default_restore() -> None:
    assert "/api/themes/" in THEMES_HTML
    assert "Restore default settings" in THEMES_HTML
    assert "The bundled default is protected" in THEMES_HTML
    assert "default_theme=current" in THEMES_HTML


def test_remote_theme_administration_requires_an_admin_token() -> None:
    settings = Settings(_env_file=None, remote_admin_enabled=True, admin_token="admin-secret")

    denied = evaluate_http_access(
        settings, method="PUT", path="/api/themes/night-race", client_host="192.0.2.44", headers={}
    )
    allowed = evaluate_http_access(
        settings,
        method="PUT",
        path="/api/themes/night-race",
        client_host="192.0.2.44",
        headers={"x-bbs-admin-token": "admin-secret"},
    )

    assert denied.status_code == 401
    assert allowed.allowed
