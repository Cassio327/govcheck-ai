from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from govcheck.config import Settings, get_settings

router = APIRouter(tags=["operations"])


@router.get("/health", summary="Process liveness")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Dependency readiness")
async def ready(settings: Annotated[Settings, Depends(get_settings)]) -> JSONResponse:
    if not settings.database_url:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": {"database": "missing"}},
        )

    engine = None
    try:
        engine = create_async_engine(
            settings.database_url,
            connect_args={"timeout": 3} if settings.database_url.startswith("sqlite") else {},
            pool_pre_ping=True,
        )
        async with engine.connect() as connection:
            # A reachable database alone is insufficient: the application schema
            # must also be present for uploads to succeed.
            await connection.execute(text("SELECT id FROM documents LIMIT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": {"database": "unavailable"}},
        )
    finally:
        if engine is not None:
            await engine.dispose()

    return JSONResponse(
        status_code=200,
        content={"status": "ready", "checks": {"database": "available"}},
    )
