"""Response schemas for read-only audit history."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.user import UserRole


class AuditEventResponse(BaseModel):
    id: int
    action: str
    actor_id: int
    actor_name: str
    actor_role: UserRole
    analysis_id: int | None
    details: dict[str, Any]
    created_at: datetime


class AuditTrailResponse(BaseModel):
    event_count: int
    events: list[AuditEventResponse]
