from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.db.models import Base
from app.db.seed import seed

router = APIRouter(prefix="/api/test", tags=["test"])

@router.post("/reset", status_code=status.HTTP_200_OK, summary="Reset test database")
async def reset_db(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """Reset the test database to a clean state.

    This endpoint is only enabled when `APP_ENV` is set to ``test``.
    It drops all tables, recreates the schema, and runs the idempotent seed
    script to populate fake appointments.
    """
    if settings.environment != "test":
        raise HTTPException(status_code=403, detail="Test reset endpoint is disabled in non-test environments")

    # Drop all tables and recreate schema
    await session.run_sync(Base.metadata.drop_all)
    await session.run_sync(Base.metadata.create_all)

    # Seed fake data
    await seed(session)
    return {"status": "reset"}
