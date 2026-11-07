import asyncio
import re
from collections.abc import Mapping
from typing import Any

import httpx

from govcheck.domain.tools import ToolResult

CONTROL_NUMBER_PATTERN = re.compile(
    r"^(?P<cnpj>[A-Z0-9]{14})-1-(?P<sequence>[0-9]{6})/(?P<year>[0-9]{4})$"
)
OFFICIAL_BASE_URL = "https://pncp.gov.br/api/consulta/"
SAFE_RESPONSE_FIELDS = {
    "numeroControlePNCP",
    "numeroCompra",
    "anoCompra",
    "processo",
    "objetoCompra",
    "modalidadeNome",
    "situacaoCompraNome",
    "dataAberturaProposta",
    "dataEncerramentoProposta",
}


class ProcurementLookupTool:
    name = "pncp_procurement_lookup"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 1,
        backoff_seconds: float = 0.1,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        self._client = client or httpx.AsyncClient(
            base_url=OFFICIAL_BASE_URL,
            timeout=httpx.Timeout(5.0),
            headers={"Accept": "application/json"},
        )
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds

    def sanitize_arguments(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        value = arguments.get("numero_controle_pncp")
        return {"numero_controle_pncp": value} if isinstance(value, str) else {}

    async def execute(self, arguments: Mapping[str, Any]) -> ToolResult:
        if set(arguments) != {"numero_controle_pncp"}:
            return ToolResult(status="invalid", error_code="invalid_arguments")
        raw_control_number = arguments.get("numero_controle_pncp")
        if not isinstance(raw_control_number, str):
            return ToolResult(status="invalid", error_code="invalid_control_number")
        control_number = raw_control_number.strip().upper()
        match = CONTROL_NUMBER_PATTERN.fullmatch(control_number)
        if match is None:
            return ToolResult(status="invalid", error_code="invalid_control_number")

        cnpj = match.group("cnpj")
        year = int(match.group("year"))
        sequence = int(match.group("sequence"))
        path = f"v1/orgaos/{cnpj}/compras/{year}/{sequence}"

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.get(path)
            except httpx.TimeoutException:
                if attempt < self._max_retries:
                    await self._backoff(attempt)
                    continue
                return ToolResult(status="unavailable", error_code="timeout")
            except httpx.HTTPError:
                return ToolResult(status="unavailable", error_code="network_error")

            source_url = str(response.request.url)
            if response.status_code == 404:
                return ToolResult(
                    status="not_found",
                    source_url=source_url,
                    error_code="procurement_not_found",
                )
            if response.status_code in {400, 422}:
                return ToolResult(
                    status="invalid",
                    source_url=source_url,
                    error_code="upstream_rejected_identifier",
                )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < self._max_retries:
                    await self._backoff(attempt)
                    continue
                error_code = "rate_limited" if response.status_code == 429 else "upstream_error"
                return ToolResult(
                    status="unavailable",
                    source_url=source_url,
                    error_code=error_code,
                )
            if response.status_code != 200:
                return ToolResult(
                    status="unavailable",
                    source_url=source_url,
                    error_code="unexpected_status",
                )

            try:
                payload = response.json()
            except ValueError:
                return ToolResult(
                    status="unavailable",
                    source_url=source_url,
                    error_code="malformed_response",
                )
            if not isinstance(payload, dict) or payload.get("numeroControlePNCP") != control_number:
                return ToolResult(
                    status="unavailable",
                    source_url=source_url,
                    error_code="malformed_response",
                )
            sanitized = {key: payload[key] for key in SAFE_RESPONSE_FIELDS if key in payload}
            return ToolResult(
                status="verified",
                source_url=source_url,
                data=sanitized,
            )

        raise RuntimeError("unreachable retry state")

    async def _backoff(self, attempt: int) -> None:
        if self._backoff_seconds > 0:
            await asyncio.sleep(self._backoff_seconds * (2**attempt))
