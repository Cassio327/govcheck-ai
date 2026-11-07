from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from govcheck.domain.documents import Document
from govcheck.domain.findings import ToolRun
from govcheck.infrastructure.db.base import Base
from govcheck.infrastructure.db.session import SqlAlchemyUnitOfWork


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_tool_repository_round_trips_sanitized_provenance(session_factory) -> None:
    document = Document(
        session_id="session-a",
        filename="edital.pdf",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    run = ToolRun(
        document_id=document.id,
        name="pncp_procurement_lookup",
        status="verified",
        request={"numero_controle_pncp": "00394460000141-1-000001/2021"},
        source_url="https://pncp.gov.br/api/consulta/v1/orgaos/00394460000141/compras/2021/1",
        data={"numeroControlePNCP": "00394460000141-1-000001/2021"},
    )
    async with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        await unit_of_work.documents.add(document, [])
        await unit_of_work.tools.add(run)
        await unit_of_work.commit()

    async with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        loaded = await unit_of_work.tools.list_for_document(document.id)

    assert loaded == [run]
