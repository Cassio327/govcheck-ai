import asyncio
import json
from collections.abc import Callable

from govcheck.config import get_settings
from govcheck.domain.documents import utc_now
from govcheck.domain.repositories import UnitOfWork
from govcheck.infrastructure.db.session import SqlAlchemyUnitOfWork, build_session_factory


class CleanupExpiredDocuments:
    def __init__(self, *, unit_of_work_factory: Callable[[], UnitOfWork]) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(self) -> int:
        async with self._unit_of_work_factory() as unit_of_work:
            deleted = await unit_of_work.documents.delete_expired(utc_now())
            await unit_of_work.commit()
            return deleted


async def cleanup_database(database_url: str) -> int:
    session_factory = build_session_factory(database_url)

    def unit_of_work_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    try:
        return await CleanupExpiredDocuments(unit_of_work_factory=unit_of_work_factory).execute()
    finally:
        await session_factory.kw["bind"].dispose()


def main() -> None:
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for retention cleanup")
    deleted = asyncio.run(cleanup_database(database_url))
    print(json.dumps({"deleted_documents": deleted}))


if __name__ == "__main__":
    main()
