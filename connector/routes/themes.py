"""Overlay theme discovery API."""

from typing import Any

from fastapi import APIRouter, HTTPException

from connector.services.theme_service import ThemeNotFoundError, ThemeService

router = APIRouter(prefix="/themes", tags=["themes"])
service = ThemeService()


@router.get("")
def list_themes() -> list[dict[str, Any]]:
    return service.list()


@router.get("/{slug}")
def get_theme(slug: str) -> dict[str, Any]:
    try:
        return service.get(slug)
    except ThemeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Theme not found.") from exc
