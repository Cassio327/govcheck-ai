import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, status
from fastapi.responses import StreamingResponse

from govcheck.api.dependencies import AppServices, get_services, get_session_id
from govcheck.api.errors import APIError
from govcheck.api.schemas import AnalysisJobResponse, FindingResponse
from govcheck.application.analysis.graph import DocumentNotAccessible

router = APIRouter(prefix="/api/v1/documents", tags=["analysis"])


@router.post(
    "/{document_id}/analysis",
    response_model=AnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start evidence-checked structured analysis",
    description=(
        "Runs extraction, allowlisted external validation, evidence criticism, and synthesis. "
        "Unavailable external checks stay explicit."
    ),
)
async def start_analysis(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    session_id: Annotated[str, Depends(get_session_id)],
    services: Annotated[AppServices, Depends(get_services)],
) -> AnalysisJobResponse:
    try:
        job = await services.analysis.start(session_id, document_id)
    except DocumentNotAccessible as error:
        raise APIError(
            404, "document_not_found", "Documento não encontrado nesta sessão."
        ) from error
    background_tasks.add_task(services.analysis.run, job)
    return AnalysisJobResponse.model_validate(job)


@router.get(
    "/{document_id}/events",
    summary="Replay analysis progress as Server-Sent Events",
    response_class=StreamingResponse,
)
async def analysis_events(
    document_id: UUID,
    session_id: Annotated[str, Depends(get_session_id)],
    services: Annotated[AppServices, Depends(get_services)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    try:
        after = int(last_event_id or 0)
    except ValueError as error:
        raise APIError(400, "invalid_event_id", "Last-Event-ID deve ser um inteiro.") from error
    async with services.unit_of_work_factory() as unit_of_work:
        document = await unit_of_work.documents.get_owned(document_id, session_id)
        if document is None:
            raise APIError(404, "document_not_found", "Documento não encontrado nesta sessão.")
        job = await unit_of_work.events.latest_job_for_document(document_id, session_id)
        if job is None:
            raise APIError(404, "analysis_not_found", "Nenhuma análise foi iniciada.")
        events = await unit_of_work.events.list_after(job.id, after)

    async def stream():
        for event in events:
            data = json.dumps(event.payload, ensure_ascii=False, separators=(",", ":"))
            yield f"id: {event.sequence}\nevent: {event.event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/{document_id}/findings",
    response_model=list[FindingResponse],
    summary="List typed findings with evidence status",
)
async def list_findings(
    document_id: UUID,
    session_id: Annotated[str, Depends(get_session_id)],
    services: Annotated[AppServices, Depends(get_services)],
) -> list[FindingResponse]:
    async with services.unit_of_work_factory() as unit_of_work:
        document = await unit_of_work.documents.get_owned(document_id, session_id)
        if document is None:
            raise APIError(404, "document_not_found", "Documento não encontrado nesta sessão.")
        findings = await unit_of_work.findings.list_for_document(document_id)
    return [FindingResponse.model_validate(item, from_attributes=True) for item in findings]
