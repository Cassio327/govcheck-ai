from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

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
    return JSONResponse(
        status_code=200,
        content={"status": "ready", "checks": {"database": "configured"}},
    )
