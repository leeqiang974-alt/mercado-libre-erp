from datetime import datetime

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    id: int
    actor_type: str
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    before: dict
    after: dict
    created_at: datetime
