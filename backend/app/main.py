from datetime import datetime
from typing import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.sessions import SessionStore
from app.config import Settings


def create_app(settings: Settings | None = None, clock: Callable[[], datetime] = datetime.now) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Smile Dental voice assistant (rule-based brain)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.store = SessionStore(clock, seed=settings.seed_demo_data, max_sessions=settings.max_sessions)
    app.include_router(router)
    return app


app = create_app()
