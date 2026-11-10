import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from govcheck.config import Settings
from govcheck.main import app


@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_reports_missing_database() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"database": "missing"}}


def test_settings_reject_production_without_database_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL is required in production"):
        Settings(environment="production", database_url=None)


@pytest.mark.asyncio
async def test_ready_requires_migrated_schema(tmp_path) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from govcheck.config import get_settings
    from govcheck.infrastructure.db.base import Base
    from govcheck.infrastructure.db import models  # noqa: F401

    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ready.db'}"
    app.dependency_overrides[get_settings] = lambda: Settings(database_url=database_url)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            before = await client.get("/ready")
            assert before.status_code == 503
            assert before.json()["checks"]["database"] == "unavailable"

            engine = create_async_engine(database_url)
            try:
                async with engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
            finally:
                await engine.dispose()

            after = await client.get("/ready")
            assert after.status_code == 200
            assert after.json()["checks"]["database"] == "available"
    finally:
        app.dependency_overrides.pop(get_settings, None)
