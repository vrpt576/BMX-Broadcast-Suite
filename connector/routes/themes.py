"""Overlay theme discovery API."""

from typing import Any

from fastapi import APIRouter, HTTPException

from connector.config import APPLICATION_ROOT, get_settings
from connector.services.theme_service import ThemeNotFoundError, ThemeService

router = APIRouter(prefix="/themes", tags=["themes"])


def get_theme_service() -> ThemeService:
    settings = get_settings()
    return ThemeService(
        settings.theme_dir,
        bundled_root=APPLICATION_ROOT / "themes",
    )


@router.get("")
def list_themes() -> list[dict[str, Any]]:
    return get_theme_service().list()


@router.get("/{slug}")
def get_theme(slug: str) -> dict[str, Any]:
    try:
        return get_theme_service().get(slug)
    except ThemeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Theme not found.") from exc
