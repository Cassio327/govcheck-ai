import asyncio
from datetime import timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from govcheck.api.middleware.rate_limit import RateLimitMiddleware, SlidingWindowRateLimiter
from govcheck.api.middleware.request_id import RequestIdMiddleware
from govcheck.application.analysis.graph import AnalysisAlreadyRunning
from govcheck.domain.documents import AnalysisJob, utc_now
from tests.fixtures.pdf_factory import make_text_pdf


@pytest.mark.asyncio
async def test_rate_limit_returns_a_typed_429_and_isolates_session_budgets() -> None:
    application = FastAPI()
    application.add_middleware(
        RateLimitMiddleware,
        session_limiter=SlidingWindowRateLimiter(limit=2, window_seconds=60, max_keys=100),
        client_limiter=SlidingWindowRateLimiter(limit=10, window_seconds=60, max_keys=100),
    )
    application.add_middleware(RequestIdMiddleware)

    @application.get("/api/v1/check")
    async def check() -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        first = await client.get("/api/v1/check", headers={"X-Session-ID": "session-a"})
        second = await client.get("/api/v1/check", headers={"X-Session-ID": "session-a"})
        limited = await client.get("/api/v1/check", headers={"X-Session-ID": "session-a"})
        another_session = await client.get("/api/v1/check", headers={"X-Session-ID": "session-b"})

    assert first.status_code == second.status_code == another_session.status_code == 200
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]
    assert limited.headers["X-Request-ID"]
    assert limited.json()["error"]["code"] == "rate_limit_exceeded"
    assert limited.json()["error"]["request_id"] == limited.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_rotating_session_ids_cannot_bypass_the_client_budget() -> None:
    application = FastAPI()
    application.add_middleware(
        RateLimitMiddleware,
        session_limiter=SlidingWindowRateLimiter(limit=10, window_seconds=60, max_keys=100),
        client_limiter=SlidingWindowRateLimiter(limit=2, window_seconds=60, max_keys=100),
    )
    application.add_middleware(RequestIdMiddleware)

    @application.get("/api/v1/check")
    async def check() -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=application, client=("203.0.113.10", 1234)),
        base_url="http://test",
    ) as client:
        first = await client.get("/api/v1/check", headers={"X-Session-ID": "rotated-a"})
        second = await client.get("/api/v1/check", headers={"X-Session-ID": "rotated-b"})
        limited = await client.get("/api/v1/check", headers={"X-Session-ID": "rotated-c"})

    assert first.status_code == second.status_code == 200
    assert limited.status_code == 429
    assert limited.headers["X-RateLimit-Scope"] == "client"


@pytest.mark.asyncio
async def test_key_capacity_rejects_new_keys_without_resetting_active_budgets() -> None:
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, max_keys=2)

    assert (await limiter.check("active-a", now=10)).allowed is True
    assert (await limiter.check("active-b", now=10)).allowed is True
    assert (await limiter.check("attacker-c", now=11)).allowed is False
    assert (await limiter.check("active-a", now=11)).allowed is False


@pytest.mark.asyncio
async def test_concurrent_analysis_starts_allow_only_one_active_job_per_session(
    api_services,
) -> None:
    content = make_text_pdf(["Prazo final em 13 de novembro."])
    first_document = await api_services.ingest_document.execute("one-session", "first.pdf", content)
    second_document = await api_services.ingest_document.execute(
        "one-session", "second.pdf", content
    )

    outcomes = await asyncio.gather(
        api_services.analysis.start("one-session", first_document.id),
        api_services.analysis.start("one-session", second_document.id),
        return_exceptions=True,
    )

    jobs = [outcome for outcome in outcomes if not isinstance(outcome, BaseException)]
    rejected = [outcome for outcome in outcomes if isinstance(outcome, AnalysisAlreadyRunning)]
    assert len(jobs) == 1
    assert len(rejected) == 1

    await api_services.analysis.run(jobs[0])
    next_job = await api_services.analysis.start("one-session", second_document.id)
    assert next_job.status == "running"


@pytest.mark.asyncio
async def test_stale_active_job_is_failed_before_a_new_analysis_starts(api_services) -> None:
    document = await api_services.ingest_document.execute(
        "stale-session",
        "stale.pdf",
        make_text_pdf(["Documento público para análise."]),
    )
    stale_job = AnalysisJob(
        document_id=document.id,
        session_id=document.session_id,
        status="running",
        created_at=utc_now() - timedelta(minutes=11),
    )
    async with api_services.unit_of_work_factory() as unit_of_work:
        await unit_of_work.events.add_job(stale_job)
        await unit_of_work.commit()

    replacement = await api_services.analysis.start(document.session_id, document.id)

    assert replacement.status == "running"
    assert replacement.id != stale_job.id
