"""FastAPI app: `uvicorn app.main:app --reload` from the backend folder."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.store import CallStore
from app.config import load_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(store: CallStore | None = None) -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="Brightside Dental voice receptionist", version="1.0.0")
    app.state.store = store or CallStore(max_calls=settings.max_calls)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    return app


app = create_app()
