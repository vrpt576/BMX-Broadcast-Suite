import json
from pathlib import Path

import pytest

from connector.services.theme_service import ThemeNotFoundError, ThemeService


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


def test_unknown_theme_raises(tmp_path: Path) -> None:
    with pytest.raises(ThemeNotFoundError):
        ThemeService(tmp_path).get("missing")
