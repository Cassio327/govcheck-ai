import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from govcheck.domain.tools import ToolRequest
from govcheck.infrastructure.tools.procurement_lookup import ProcurementLookupTool
from govcheck.infrastructure.tools.registry import ToolRegistry

FIXTURES = Path(__file__).parents[2] / "fixtures" / "http"
CONTROL_NUMBER = "00394460000141-1-000001/2021"


@pytest.mark.asyncio
async def test_lookup_returns_sanitized_official_provenance() -> None:
    payload = json.loads((FIXTURES / "pncp_procurement_success.json").read_text())

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/consulta/v1/orgaos/00394460000141/compras/2021/1"
        assert "authorization" not in request.headers
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://pncp.gov.br/api/consulta/"
    ) as client:
        result = await ProcurementLookupTool(client=client).execute(
            {"numero_controle_pncp": CONTROL_NUMBER}
        )

    assert result.status == "verified"
    assert result.source_url == (
        "https://pncp.gov.br/api/consulta/v1/orgaos/00394460000141/compras/2021/1"
    )
    assert result.data["numeroControlePNCP"] == CONTROL_NUMBER
    assert result.data["objetoCompra"] == "Aquisição de material de expediente"
    assert "campoNaoPersistido" not in result.data
    assert result.error_code is None


@pytest.mark.asyncio
async def test_lookup_maps_not_found_without_retry() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://pncp.gov.br/api/consulta/"
    ) as client:
        result = await ProcurementLookupTool(client=client).execute(
            {"numero_controle_pncp": CONTROL_NUMBER}
        )

    assert result.status == "not_found"
    assert result.error_code == "procurement_not_found"
    assert calls == 1


@pytest.mark.asyncio
async def test_lookup_rejects_malformed_success_payload() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"objetoCompra": "sem identificador"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://pncp.gov.br/api/consulta/"
    ) as client:
        result = await ProcurementLookupTool(client=client).execute(
            {"numero_controle_pncp": CONTROL_NUMBER}
        )

    assert result.status == "unavailable"
    assert result.error_code == "malformed_response"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "error_code"),
    [("timeout", "timeout"), ("rate_limit", "rate_limited")],
)
async def test_lookup_bounds_retries_for_transient_failures(failure, error_code) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("slow upstream", request=request)
        return httpx.Response(429)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://pncp.gov.br/api/consulta/"
    ) as client:
        result = await ProcurementLookupTool(
            client=client,
            max_retries=1,
            backoff_seconds=0,
        ).execute({"numero_controle_pncp": CONTROL_NUMBER})

    assert result.status == "unavailable"
    assert result.error_code == error_code
    assert calls == 2


@pytest.mark.asyncio
async def test_lookup_rejects_an_invalid_control_number_before_http() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ProcurementLookupTool(client=client).execute(
            {"numero_controle_pncp": "../../segredo"}
        )

    assert result.status == "invalid"
    assert result.error_code == "invalid_control_number"
    assert calls == 0


class MemoryToolRuns:
    def __init__(self):
        self.items = []

    async def add(self, tool_run):
        self.items.append(tool_run)


class MemoryUnitOfWork:
    def __init__(self):
        self.tools = MemoryToolRuns()
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_registry_persists_sanitized_tool_provenance() -> None:
    payload = json.loads((FIXTURES / "pncp_procurement_success.json").read_text())

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    unit_of_work = MemoryUnitOfWork()
    document_id = uuid4()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://pncp.gov.br/api/consulta/"
    ) as client:
        registry = ToolRegistry(
            [ProcurementLookupTool(client=client)],
            unit_of_work_factory=lambda: unit_of_work,
        )
        result = await registry.invoke(
            ToolRequest(
                name="pncp_procurement_lookup",
                arguments={"numero_controle_pncp": CONTROL_NUMBER},
            ),
            document_id=document_id,
        )

    assert result.status == "verified"
    assert unit_of_work.committed is True
    assert len(unit_of_work.tools.items) == 1
    persisted = unit_of_work.tools.items[0]
    assert persisted.document_id == document_id
    assert persisted.request == {"numero_controle_pncp": CONTROL_NUMBER}
    assert persisted.status == "verified"
