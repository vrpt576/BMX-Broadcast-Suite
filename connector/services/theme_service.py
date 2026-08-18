"""Load track-agnostic visual themes for BBS overlays."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_THEME_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_CSS_COLOR = re.compile(r"^(?:#[0-9a-fA-F]{3,8}|rgba?\([0-9.,%\s]+\)|[a-zA-Z]+)$")
_TEXT_TRANSFORMS = {"none", "uppercase", "lowercase", "capitalize"}

DEFAULT_THEME: dict[str, Any] = {
    "name": "BBS Neutral",
    "slug": "default",
    "colors": {
        "primary": "#f3b61f",
        "primary_text": "#101820",
        "secondary": "#d98b13",
        "secondary_text": "#101820",
        "panel": "#101820",
        "panel_alt": "#1b2733",
        "panel_text": "#ffffff",
        "muted_text": "#d8dde3",
        "header_panel": "#101820",
        "row_odd": "rgba(16,24,32,.96)",
        "row_even": "rgba(27,39,51,.96)",
        "gate": "#f3b61f",
        "gate_text": "#101820",
        "plate": "#f3b61f",
        "divider": "rgba(255,255,255,.18)",
        "shadow": "rgba(0,0,0,.45)",
        "warning": "#7f1d1d",
        "warning_text": "#ffffff",
    },
    "typography": {
        "font_family": "Arial, Helvetica, sans-serif",
        "text_transform": "uppercase",
    },
}


class ThemeNotFoundError(LookupError):
    """Raised when a requested overlay theme does not exist."""


class ThemeValidationError(ValueError):
    """Raised when a theme editor payload is unsafe or incomplete."""


class ThemeService:
    def __init__(
        self,
        root: Path = Path("themes"),
        *,
        bundled_root: Path | None = None,
    ) -> None:
        self.root = root
        self.bundled_root = bundled_root

    def list(self) -> list[dict[str, Any]]:
        themes: dict[str, dict[str, Any]] = {"default": DEFAULT_THEME}
        roots = [self.bundled_root, self.root]
        for root in roots:
            if root is None or not root.exists():
                continue
            for path in sorted(root.glob("*/theme.json")):
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
        candidates = [self.root / normalized / "theme.json"]
        if self.bundled_root is not None:
            candidates.append(self.bundled_root / normalized / "theme.json")
        for path in candidates:
            if path.is_file():
                return self._load_file(path)
        raise ThemeNotFoundError(normalized)

    def save(self, slug: str, value: dict[str, Any]) -> dict[str, Any]:
        """Validate and atomically save a custom theme without touching bundled files."""
        normalized = self._normalized_slug(slug)
        if normalized == "default":
            raise ThemeValidationError("The bundled default theme cannot be overwritten.")
        theme = self._validate_editor_value(normalized, value)
        path = self.root / normalized / "theme.json"
        theme = self._preserve_unknown_properties(theme, self._existing_raw(normalized))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(theme, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        return theme

    def _existing_raw(self, slug: str) -> dict[str, Any]:
        candidates = [self.root / slug / "theme.json"]
        if self.bundled_root is not None:
            candidates.append(self.bundled_root / slug / "theme.json")
        for path in candidates:
            if not path.is_file():
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                return value
        return {}

    @staticmethod
    def _preserve_unknown_properties(
        theme: dict[str, Any], existing: dict[str, Any]
    ) -> dict[str, Any]:
        """Keep legacy/custom settings that the editor does not understand."""
        result = json.loads(json.dumps(theme))
        for key, value in existing.items():
            if key not in {"name", "slug", "colors", "typography"}:
                result[key] = value
        for section in ("colors", "typography"):
            raw = existing.get(section)
            if not isinstance(raw, dict):
                continue
            supported = set(DEFAULT_THEME[section])
            result[section].update(
                {key: value for key, value in raw.items() if key not in supported}
            )
        return result

    def reset(self, slug: str) -> dict[str, Any]:
        """Restore a custom theme's supported settings to BBS defaults."""
        normalized = self._normalized_slug(slug)
        if normalized == "default":
            return json.loads(json.dumps(DEFAULT_THEME))
        existing = self.get(normalized)
        return self.save(normalized, {"name": existing["name"]})

    @staticmethod
    def _normalized_slug(slug: str) -> str:
        normalized = slug.strip().lower()
        if not _THEME_NAME.fullmatch(normalized):
            raise ThemeValidationError("Use lowercase letters, numbers, hyphens, or underscores.")
        return normalized

    @classmethod
    def _validate_editor_value(cls, slug: str, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ThemeValidationError("A theme must be an object.")
        name = value.get("name", slug)
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            raise ThemeValidationError("Theme name must be 1 to 80 characters.")
        result = json.loads(json.dumps(DEFAULT_THEME))
        result.update({"name": name.strip(), "slug": slug})
        for section in ("colors", "typography"):
            supplied = value.get(section, {})
            if not isinstance(supplied, dict):
                raise ThemeValidationError(f"{section.title()} must be an object.")
            unknown = set(supplied) - set(result[section])
            if unknown:
                raise ThemeValidationError(f"Unsupported {section} setting: {sorted(unknown)[0]}.")
            for key, item in supplied.items():
                if not isinstance(item, str) or not item.strip() or len(item) > 160:
                    raise ThemeValidationError(f"{key} must be a short, non-empty value.")
                normalized = item.strip()
                if section == "colors" and not _CSS_COLOR.fullmatch(normalized):
                    raise ThemeValidationError(f"{key} must be a CSS color value.")
                if section == "typography" and key == "font_family" and any(
                    character in normalized for character in ";{}<>"
                ):
                    raise ThemeValidationError("Font family contains unsupported characters.")
                if section == "typography" and key == "text_transform" and normalized not in _TEXT_TRANSFORMS:
                    raise ThemeValidationError("Text transform must be none, uppercase, lowercase, or capitalize.")
                result[section][key] = normalized
        return result

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
        merged["colors"].update(
            {key: item for key, item in colors.items() if key in merged["colors"]}
        )
        merged["typography"].update(
            {key: item for key, item in typography.items() if key in merged["typography"]}
        )
        return merged
