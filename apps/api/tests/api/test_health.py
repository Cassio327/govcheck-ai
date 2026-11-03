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
