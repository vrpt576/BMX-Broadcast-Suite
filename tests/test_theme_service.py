import json
from pathlib import Path

import pytest

from connector.services.theme_service import ThemeNotFoundError, ThemeService, ThemeValidationError


def test_default_theme_is_always_available(tmp_path: Path) -> None:
    theme = ThemeService(tmp_path).get("default")
    assert theme["slug"] == "default"
    assert theme["colors"]["primary"]


def test_custom_theme_merges_with_defaults(tmp_path: Path) -> None:
    folder = tmp_path / "my-track"
    folder.mkdir()
    (folder / "theme.json").write_text(
        json.dumps({"name": "My Track", "slug": "my-track", "colors": {"primary": "#123456"}}),
        encoding="utf-8",
    )
    theme = ThemeService(tmp_path).get("my-track")
    assert theme["colors"]["primary"] == "#123456"
    assert theme["colors"]["panel_text"] == "#ffffff"
    assert theme["colors"]["row_even"]
    assert theme["colors"]["warning_text"] == "#ffffff"


def test_unknown_theme_raises(tmp_path: Path) -> None:
    with pytest.raises(ThemeNotFoundError):
        ThemeService(tmp_path).get("missing")


def test_expanded_color_palette_is_available(tmp_path: Path) -> None:
    colors = ThemeService(tmp_path).get("default")["colors"]
    expected = {
        "primary", "primary_text", "secondary", "secondary_text",
        "panel", "panel_alt", "panel_text", "muted_text", "header_panel",
        "row_odd", "row_even", "gate", "gate_text", "plate",
        "divider", "shadow", "warning", "warning_text",
    }
    assert expected.issubset(colors)


def test_theme_editor_saves_a_validated_custom_theme(tmp_path: Path) -> None:
    service = ThemeService(tmp_path)

    saved = service.save(
        "night-race",
        {"name": "Night Race", "colors": {"primary": "#123456"}},
    )

    assert saved["slug"] == "night-race"
    assert service.get("night-race")["colors"]["primary"] == "#123456"
    assert (tmp_path / "night-race" / "theme.json").is_file()


def test_theme_editor_rejects_unknown_settings_and_preserves_existing_theme(tmp_path: Path) -> None:
    service = ThemeService(tmp_path)
    service.save("night-race", {"name": "Night Race", "colors": {"primary": "#123456"}})

    with pytest.raises(ThemeValidationError, match="Unsupported"):
        service.save("night-race", {"colors": {"untrusted_css": "url(x)"}})

    assert service.get("night-race")["colors"]["primary"] == "#123456"


def test_theme_editor_reset_restores_defaults_without_deleting_the_theme(tmp_path: Path) -> None:
    service = ThemeService(tmp_path)
    service.save("night-race", {"name": "Night Race", "colors": {"primary": "#123456"}})

    reset = service.reset("night-race")

    assert reset["name"] == "Night Race"
    assert reset["colors"]["primary"] == DEFAULT_PRIMARY
    assert service.get("night-race")["slug"] == "night-race"


DEFAULT_PRIMARY = "#f3b61f"


def test_theme_editor_preserves_unknown_legacy_properties(tmp_path: Path) -> None:
    folder = tmp_path / "legacy"
    folder.mkdir()
    (folder / "theme.json").write_text(
        json.dumps(
            {
                "name": "Legacy",
                "slug": "legacy",
                "colors": {"primary": "#111111", "legacy_border": "#222222"},
                "typography": {"font_family": "Arial", "legacy_weight": "700"},
                "logo_position": "top-left",
            }
        ),
        encoding="utf-8",
    )

    ThemeService(tmp_path).save("legacy", {"name": "Updated", "colors": {"primary": "#333333"}})

    saved = json.loads((folder / "theme.json").read_text(encoding="utf-8"))
    assert saved["colors"]["legacy_border"] == "#222222"
    assert saved["typography"]["legacy_weight"] == "700"
    assert saved["logo_position"] == "top-left"


def test_theme_editor_explains_invalid_css_color(tmp_path: Path) -> None:
    with pytest.raises(ThemeValidationError, match="CSS color"):
        ThemeService(tmp_path).save("night-race", {"colors": {"primary": "url(script)"}})


def test_theme_reset_preserves_unknown_legacy_properties(tmp_path: Path) -> None:
    folder = tmp_path / "legacy"
    folder.mkdir()
    (folder / "theme.json").write_text(
        json.dumps(
            {
                "name": "Legacy",
                "slug": "legacy",
                "colors": {"primary": "#111111", "legacy_border": "#222222"},
                "logo_position": "top-left",
            }
        ),
        encoding="utf-8",
    )

    ThemeService(tmp_path).reset("legacy")

    saved = json.loads((folder / "theme.json").read_text(encoding="utf-8"))
    assert saved["colors"]["primary"] == DEFAULT_PRIMARY
    assert saved["colors"]["legacy_border"] == "#222222"
    assert saved["logo_position"] == "top-left"
