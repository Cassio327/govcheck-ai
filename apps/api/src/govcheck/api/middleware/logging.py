import json
import logging
import time
from collections.abc import Mapping, Sequence
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from govcheck.api.middleware.request_id import get_request_id

SECURITY_LOGGER = logging.getLogger("govcheck.security")
REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "body",
    "content",
    "cookie",
    "document",
    "file",
    "password",
    "pdf",
    "prompt",
    "secret",
    "session",
    "text",
    "token",
)
ALLOWED_LOG_FIELDS = frozenset(
    {
        "duration_ms",
        "error_type",
        "method",
        "provider_error_code",
        "provider_status",
        "request_id",
        "route",
        "status_code",
    }
)


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).casefold().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def redact_sensitive(value: Any, *, key: object | None = None) -> Any:
    if key is not None and _is_sensitive_key(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_sensitive(item_value, key=item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, bytes | bytearray | memoryview):
        return f"<{len(value)} bytes>"
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [redact_sensitive(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return f"<{type(value).__name__}>"


def log_security_event(event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    allowed_fields = {key: value for key, value in fields.items() if key in ALLOWED_LOG_FIELDS}
    payload = redact_sensitive({"event": event, **allowed_fields})
    SECURITY_LOGGER.log(
        level,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
    )


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "<unmatched>"


def _internal_error_response(request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        headers={"X-Request-ID": request_id},
        content={
            "error": {
                "code": "internal_server_error",
                "message": "Ocorreu um erro interno. Tente novamente mais tarde.",
                "request_id": request_id,
            }
        },
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started = time.perf_counter()
        request_id = get_request_id(request)
        try:
            response = await call_next(request)
        except Exception as error:
            log_security_event(
                "http.request.completed",
                level=logging.ERROR,
                request_id=request_id,
                method=request.method,
                route=_route_template(request),
                status_code=500,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                error_type=type(error).__name__,
            )
            # Handle unexpected application errors inside the request middleware.
            # Starlette's outer ServerErrorMiddleware intentionally re-raises after
            # sending its response, which can expose exception messages in server
            # logs. Returning the public envelope here keeps those messages private.
            return _internal_error_response(request_id)
        log_security_event(
            "http.request.completed",
            request_id=request_id,
            method=request.method,
            route=_route_template(request),
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return response
