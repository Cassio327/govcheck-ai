import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from govcheck.api.middleware.logging import log_security_event
from govcheck.api.middleware.request_id import get_request_id
from govcheck.domain.ingestion import IngestionError


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    request_id = get_request_id(request)
    return JSONResponse(
        status_code=status_code,
        headers={"X-Request-ID": request_id},
        content={"error": {"code": code, "message": message, "request_id": request_id}},
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, error: APIError) -> JSONResponse:
        return _response(request, error.status_code, error.code, error.message)

    @app.exception_handler(IngestionError)
    async def ingestion_error_handler(request: Request, error: IngestionError) -> JSONResponse:
        mapping = {
            "file_too_large": (413, "pdf_too_large"),
            "page_limit_exceeded": (422, "pdf_too_many_pages"),
            "encrypted_pdf": (422, "pdf_encrypted"),
            "ocr_required": (422, "pdf_ocr_required"),
            "invalid_pdf": (422, "pdf_invalid"),
        }
        status_code, code = mapping.get(error.code, (422, "pdf_invalid"))
        return _response(request, status_code, code, error.public_message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        del error
        return _response(
            request,
            422,
            "request_validation_error",
            "Os dados enviados não atendem ao contrato da API.",
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
        log_security_event(
            "http.request.exception",
            level=logging.ERROR,
            request_id=get_request_id(request),
            error_type=type(error).__name__,
        )
        return _response(
            request,
            500,
            "internal_server_error",
            "Ocorreu um erro interno. Tente novamente mais tarde.",
        )
