import pytest


@pytest.mark.asyncio
async def test_cors_allows_the_configured_web_origin(api_client) -> None:
    response = await api_client.options(
        "/api/v1/documents",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-session-id",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "x-session-id" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.asyncio
async def test_cors_does_not_reflect_an_unknown_origin(api_client) -> None:
    response = await api_client.options(
        "/api/v1/documents",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-session-id",
        },
    )

    assert "access-control-allow-origin" not in response.headers
