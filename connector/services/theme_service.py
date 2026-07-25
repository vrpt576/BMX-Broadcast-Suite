"""Load track-agnostic visual themes for BBS overlays."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_THEME_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

DEFAULT_THEME: dict[str, Any] = {
    "name": "BBS Neutral",
    "slug": "default",
    "colors": {
        "primary": "#f3b61f",
        "primary_text": "#101820",
        "panel": "#101820",
        "panel_text": "#ffffff",
        "muted_text": "#d8dde3",
        "divider": "rgba(255,255,255,.18)",
        "shadow": "rgba(0,0,0,.45)",
    },
    "typography": {
        "font_family": "Arial, Helvetica, sans-serif",
        "text_transform": "uppercase",
    },
}


class ThemeNotFoundError(LookupError):
    """Raised when a requested overlay theme does not exist."""


class ThemeService:
    def __init__(self, root: Path = Path("themes")) -> None:
        self.root = root

    def list(self) -> list[dict[str, Any]]:
        themes: dict[str, dict[str, Any]] = {"default": DEFAULT_THEME}
        if self.root.exists():
            for path in sorted(self.root.glob("*/theme.json")):
                try:
                    theme = self._load_file(path)
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
                themes[theme["slug"]] = theme
        return list(themes.values())

    def get(self, slug: str) -> dict[str, Any]:
        normalized = slug.strip().lower()
        if not _THEME_NAME.fullmatch(normalized):
            raise ThemeNotFoundError(normalized)
        if normalized == "default":
            return DEFAULT_THEME
        path = self.root / normalized / "theme.json"
        if not path.is_file():
            raise ThemeNotFoundError(normalized)
        return self._load_file(path)

    @staticmethod
    def _load_file(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("theme must be a JSON object")
        slug = value.get("slug") or path.parent.name
        if not isinstance(slug, str) or not _THEME_NAME.fullmatch(slug):
            raise ValueError("invalid theme slug")
        colors = value.get("colors")
        typography = value.get("typography", {})
        if not isinstance(colors, dict) or not isinstance(typography, dict):
            raise ValueError("invalid theme structure")
        merged = json.loads(json.dumps(DEFAULT_THEME))
        merged.update({"name": value.get("name", slug), "slug": slug})
        merged["colors"].update(colors)
        merged["typography"].update(typography)
        return merged
