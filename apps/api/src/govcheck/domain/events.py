from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from govcheck.domain.documents import DomainModel, utc_now


class StreamEvent(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    sequence: int = Field(ge=1)
    event_type: str
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=utc_now)
