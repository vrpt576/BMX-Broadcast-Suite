"""Presentation-safe rider metadata formatting shared by broadcast overlays."""

from __future__ import annotations


def format_rider_metadata(age: int | None, home_track: str | None) -> str | None:
    """Return a compact subtitle, omitting absent values and empty separators."""
    details: list[str] = []
    if age is not None:
        details.append(f"Age {age}")
    track = (home_track or "").strip()
    if track:
        details.append(track)
    return " · ".join(details) or None
