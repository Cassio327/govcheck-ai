from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response

from govcheck.api.dependencies import AppServices, get_services, get_session_id
from govcheck.api.errors import APIError
from govcheck.application.render_report import DocumentNotAccessible

router = APIRouter(prefix="/api/v1/documents", tags=["reports"])


@router.get(
    "/{document_id}/report",
    summary="Export an auditable preliminary report",
    description=(
        "Separates uploaded-PDF facts, model interpretations, and external public-source checks."
    ),
)
async def export_report(
    document_id: UUID,
    session_id: Annotated[str, Depends(get_session_id)],
    services: Annotated[AppServices, Depends(get_services)],
    format: Annotated[Literal["markdown", "json"], Query()] = "markdown",
) -> Response:
    try:
        report = await services.report.execute(session_id, document_id)
    except DocumentNotAccessible as error:
        raise APIError(
            404, "document_not_found", "Documento não encontrado nesta sessão."
        ) from error
    if format == "json":
        return JSONResponse(report.json_payload)
    return Response(
        report.markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="govcheck-{document_id}.md"'},
    )
