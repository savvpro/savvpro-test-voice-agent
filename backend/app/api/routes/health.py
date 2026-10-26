"""Health-check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Return service health status and version.

    Used by load balancers, monitoring, and smoke tests.
    """
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version}
