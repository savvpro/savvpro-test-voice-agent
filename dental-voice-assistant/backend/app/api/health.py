"""GET /health and /api/health — health probes and system status."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    """Return ``{"status": "ok"}`` — used by Docker healthcheck."""
    return {"status": "ok"}


@router.get("/api/health", summary="Detailed system & voice status")
async def api_health(request: Request) -> dict[str, Any]:
    """Expose STT/TTS engine status and active call metrics."""
    stt = getattr(request.app.state, "stt", None)
    tts = getattr(request.app.state, "tts", None)
    active_calls = getattr(request.app.state, "active_calls", 0)
    return {
        "status": "ok",
        "stt_provider": settings.stt_provider,
        "tts_provider": settings.tts_provider,
        "stt_ready": stt is not None,
        "tts_ready": tts is not None,
        "active_calls": active_calls,
    }
