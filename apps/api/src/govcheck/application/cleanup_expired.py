from collections.abc import Callable

from govcheck.domain.documents import utc_now
from govcheck.domain.repositories import UnitOfWork


class CleanupExpiredDocuments:
    def __init__(self, *, unit_of_work_factory: Callable[[], UnitOfWork]) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(self) -> int:
        async with self._unit_of_work_factory() as unit_of_work:
            deleted = await unit_of_work.documents.delete_expired(utc_now())
            await unit_of_work.commit()
            return deleted
