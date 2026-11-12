from collections.abc import Callable, Sequence
from uuid import UUID

from govcheck.domain.analysis import ExternalValidation
from govcheck.domain.findings import ToolRun
from govcheck.domain.repositories import UnitOfWork
from govcheck.domain.tools import Tool, ToolRequest, ToolResult


class ToolRegistry:
    def __init__(
        self,
        tools: Sequence[Tool],
        *,
        unit_of_work_factory: Callable[[], UnitOfWork] | None = None,
    ) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self._unit_of_work_factory = unit_of_work_factory

    async def invoke(
        self,
        request: ToolRequest,
        *,
        document_id: UUID | None = None,
    ) -> ToolResult:
        tool = self._tools.get(request.name)
        if tool is None:
            return ToolResult(status="invalid", error_code="tool_not_allowed")
        result = await tool.execute(request.arguments)
        if document_id is not None and self._unit_of_work_factory is not None:
            run = ToolRun(
                document_id=document_id,
                name=request.name,
                status=result.status,
                request=tool.sanitize_arguments(request.arguments),
                source_url=result.source_url,
                checked_at=result.checked_at,
                data=result.data,
                error_code=result.error_code,
            )
            async with self._unit_of_work_factory() as unit_of_work:
                await unit_of_work.tools.add(run)
                await unit_of_work.commit()
        return result

    async def validate_identifier(
        self,
        identifier: str,
        *,
        document_id: UUID | None = None,
    ) -> ExternalValidation:
        result = await self.invoke(
            ToolRequest(
                name="pncp_procurement_lookup",
                arguments={"numero_controle_pncp": identifier},
            ),
            document_id=document_id,
        )
        return ExternalValidation(
            status=result.status,
            matches=True if result.status == "verified" else None,
            source_url=result.source_url,
            data=result.data,
            error_code=result.error_code,
        )
