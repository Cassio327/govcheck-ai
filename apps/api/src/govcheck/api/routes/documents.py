from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status

from govcheck.api.dependencies import AppServices, get_services, get_session_id
from govcheck.api.errors import APIError
from govcheck.api.schemas import DocumentResponse

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a procurement PDF",
    description="Extracts page-level PDF facts and builds a document-isolated retrieval index.",
)
async def upload_document(
    file: Annotated[UploadFile, File(description="Text-based public procurement PDF")],
    session_id: Annotated[str, Depends(get_session_id)],
    services: Annotated[AppServices, Depends(get_services)],
) -> DocumentResponse:
    content = await file.read(services.max_upload_bytes + 1)
    document = await services.ingest_document.execute(
        session_id,
        file.filename or "documento.pdf",
        content,
    )
    try:
        await services.index_document.execute(document.id)
        async with services.unit_of_work_factory() as unit_of_work:
            await unit_of_work.documents.update_status(document.id, "indexed")
            await unit_of_work.commit()
    except Exception:
        async with services.unit_of_work_factory() as unit_of_work:
            await unit_of_work.documents.update_status(document.id, "failed")
            await unit_of_work.commit()
        raise
    return DocumentResponse.model_validate(document.model_copy(update={"status": "indexed"}))


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Read owned document metadata",
)
async def get_document(
    document_id: UUID,
    session_id: Annotated[str, Depends(get_session_id)],
    services: Annotated[AppServices, Depends(get_services)],
) -> DocumentResponse:
    async with services.unit_of_work_factory() as unit_of_work:
        document = await unit_of_work.documents.get_owned(document_id, session_id)
    if document is None:
        raise APIError(404, "document_not_found", "Documento não encontrado nesta sessão.")
    return DocumentResponse.model_validate(document)
