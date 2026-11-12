import json
import logging
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import BackgroundTasks, FastAPI, Request, status
from httpx import ASGITransport, AsyncClient

from govcheck.api.errors import install_exception_handlers
from govcheck.api.middleware.logging import (
    RequestLoggingMiddleware,
    log_security_event,
    redact_sensitive,
)
from govcheck.api.middleware.request_id import RequestIdMiddleware
from govcheck.api.routes.analysis import run_analysis_in_background
from govcheck.domain.documents import AnalysisJob
from govcheck.domain.llm import LLMProviderError


def test_redaction_removes_nested_secrets_document_content_and_binary_data() -> None:
    payload = {
        "authorization": "Bearer bearer-secret",
        "groq_api_key": "provider-secret",
        "nested": {
            "document_text": "cláusula confidencial do edital",
            "pdf_bytes": b"%PDF-raw-private-content",
            "status": "failed",
        },
    }

    serialized = json.dumps(redact_sensitive(payload), ensure_ascii=False)

    assert "bearer-secret" not in serialized
    assert "provider-secret" not in serialized
    assert "cláusula confidencial" not in serialized
    assert "raw-private-content" not in serialized
    assert '"status": "failed"' in serialized


def test_structured_security_log_accepts_metadata_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="govcheck.security")

    log_security_event(
        "test.event",
        request_id="safe-request-id",
        status_code=500,
        details="cláusula privada que nunca deve entrar no log",
    )

    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "event": "test.event",
        "request_id": "safe-request-id",
        "status_code": 500,
    }


@pytest.mark.asyncio
async def test_exception_response_and_structured_logs_never_echo_request_secrets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    application = FastAPI()
    install_exception_handlers(application)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(RequestIdMiddleware)

    @application.post("/explode")
    async def explode(request: Request) -> None:
        body = await request.body()
        raise RuntimeError(f"provider-secret {body!r}")

    caplog.set_level(logging.INFO, logger="govcheck.security")
    transport = ASGITransport(app=application, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/explode",
            content=b"%PDF-clausula-privada",
            headers={
                "Authorization": "Bearer bearer-secret",
                "X-Request-ID": "<script>not-a-request-id</script>",
                "X-Session-ID": "private-session-id",
            },
        )

    assert response.status_code == 500
    request_id = response.headers["X-Request-ID"]
    assert UUID(request_id)
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "Ocorreu um erro interno. Tente novamente mais tarde.",
            "request_id": request_id,
        }
    }
    observable_output = response.text + caplog.text
    for secret in (
        "provider-secret",
        "bearer-secret",
        "clausula-privada",
        "private-session-id",
        "<script>",
    ):
        assert secret not in observable_output
    records = [json.loads(record.message) for record in caplog.records]
    assert any(
        record["event"] == "http.request.completed"
        and record["request_id"] == request_id
        and record["status_code"] == 500
        for record in records
    )


@pytest.mark.asyncio
async def test_background_analysis_failure_is_contained_and_redacted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class ExplodingAnalysis:
        async def run(self, job: AnalysisJob) -> None:
            del job
            raise RuntimeError("provider-secret documento-confidencial")

    application = FastAPI()

    @application.post("/background", status_code=status.HTTP_202_ACCEPTED)
    async def background(background_tasks: BackgroundTasks) -> dict[str, str]:
        background_tasks.add_task(
            run_analysis_in_background,
            ExplodingAnalysis(),
            AnalysisJob(document_id=UUID(int=1), session_id="private-session"),
        )
        return {"status": "accepted"}

    caplog.set_level(logging.INFO, logger="govcheck.security")
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=True),
        base_url="http://test",
    ) as client:
        response = await client.post("/background")

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert "provider-secret" not in caplog.text
    assert "documento-confidencial" not in caplog.text
    assert any(
        json.loads(record.message)
        == {
            "error_type": "RuntimeError",
            "event": "analysis.background.failed",
        }
        for record in caplog.records
    )


def test_production_logging_keeps_security_events_and_disables_access_logs() -> None:
    api_dir = Path(__file__).parents[2]
    configuration = json.loads((api_dir / "logging.json").read_text())
    security_logger = configuration["loggers"]["govcheck.security"]
    dockerfile = (api_dir / "Dockerfile").read_text()

    assert security_logger == {
        "handlers": ["security"],
        "level": "INFO",
        "propagate": False,
    }
    assert '"--log-config", "logging.json"' in dockerfile
    assert '"--no-access-log"' in dockerfile


@pytest.mark.asyncio
async def test_background_logs_only_safe_groq_failure_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailedProvider:
        async def run(self, job: AnalysisJob) -> None:
            del job
            raise LLMProviderError(
                "Provider could not process private document",
                code="rate_limited",
                status_code=429,
            )

    caplog.set_level(logging.ERROR, logger="govcheck.security")
    await run_analysis_in_background(
        FailedProvider(),
        AnalysisJob(document_id=UUID(int=1), session_id="secret-session"),
    )

    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "error_type": "LLMProviderError",
        "event": "analysis.background.failed",
        "provider_error_code": "rate_limited",
        "provider_status": 429,
    }
    assert "private document" not in caplog.text
    assert "secret-session" not in caplog.text
