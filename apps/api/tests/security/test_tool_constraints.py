import httpx
import pytest

from govcheck.domain.tools import ToolRequest
from govcheck.infrastructure.tools.procurement_lookup import ProcurementLookupTool
from govcheck.infrastructure.tools.registry import ToolRegistry

CONTROL_NUMBER = "00394460000141-1-000001/2021"


@pytest.mark.asyncio
async def test_tool_arguments_cannot_override_the_allowlisted_host() -> None:
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(200, json={"numeroControlePNCP": CONTROL_NUMBER})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://pncp.gov.br/api/consulta/"
    ) as client:
        registry = ToolRegistry([ProcurementLookupTool(client=client)])
        result = await registry.invoke(
            ToolRequest(
                name="pncp_procurement_lookup",
                arguments={
                    "numero_controle_pncp": CONTROL_NUMBER,
                    "url": "https://evil.example/steal",
                },
            )
        )

    assert result.status == "invalid"
    assert result.error_code == "invalid_arguments"
    assert calls == []


@pytest.mark.asyncio
async def test_registry_rejects_unregistered_tool_names() -> None:
    registry = ToolRegistry([])

    result = await registry.invoke(
        ToolRequest(name="fetch_any_url", arguments={"url": "https://evil.example"})
    )

    assert result.status == "invalid"
    assert result.error_code == "tool_not_allowed"
