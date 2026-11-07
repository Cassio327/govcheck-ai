from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from govcheck.api.dependencies import AppServices, get_services, get_session_id
from govcheck.api.errors import APIError
from govcheck.api.schemas import ChatAnswerResponse, ChatRequest
from govcheck.application.chat_with_document import DocumentNotAccessible

router = APIRouter(prefix="/api/v1/documents", tags=["chat"])


@router.post(
    "/{document_id}/chat",
    response_model=ChatAnswerResponse,
    summary="Ask a grounded question about one PDF",
    description="Returns model interpretation only when supported by cited PDF excerpts.",
)
async def chat_with_document(
    document_id: UUID,
    body: ChatRequest,
    session_id: Annotated[str, Depends(get_session_id)],
    services: Annotated[AppServices, Depends(get_services)],
) -> ChatAnswerResponse:
    try:
        answer = await services.chat.execute(session_id, document_id, body.question)
    except DocumentNotAccessible as error:
        raise APIError(
            404, "document_not_found", "Documento não encontrado nesta sessão."
        ) from error
    return ChatAnswerResponse.model_validate(answer, from_attributes=True)
