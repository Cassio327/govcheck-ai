from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from govcheck.infrastructure.db.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyEventRepository,
    SqlAlchemyFindingRepository,
)


def build_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        self.documents = SqlAlchemyDocumentRepository(self._session)
        self.findings = SqlAlchemyFindingRepository(self._session)
        self.events = SqlAlchemyEventRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        if exc is not None:
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of work has not been entered")
        await self._session.commit()

    async def rollback(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of work has not been entered")
        await self._session.rollback()
