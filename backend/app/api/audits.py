"""Read-only audit-trail endpoints scoped to the signed-in user."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.analysis_access import get_owned_analysis
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.analysis import Analysis
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.audit import AuditEventResponse, AuditTrailResponse

audits_router = APIRouter(tags=["audit trail"])


def _serialize_event(event: AuditEvent) -> AuditEventResponse:
    details = {}
    if event.details_json:
        try:
            parsed = json.loads(event.details_json)
            if isinstance(parsed, dict):
                details = parsed
        except json.JSONDecodeError:
            details = {}
    return AuditEventResponse(
        id=event.id,
        action=event.action,
        actor_id=event.actor_id,
        actor_name=event.actor.full_name,
        actor_role=event.actor.role,
        analysis_id=event.analysis_id,
        details=details,
        created_at=event.created_at,
    )


@audits_router.get(
    "/audit-events",
    response_model=AuditTrailResponse,
)
def get_my_audit_events(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> AuditTrailResponse:
    """Return events performed by the user or attached to their analyses."""

    events = session.scalars(
        select(AuditEvent)
        .outerjoin(Analysis, AuditEvent.analysis_id == Analysis.id)
        .options(joinedload(AuditEvent.actor))
        .where(
            or_(
                AuditEvent.actor_id == current_user.id,
                Analysis.user_id == current_user.id,
            )
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    ).all()
    serialized = [_serialize_event(event) for event in events]
    return AuditTrailResponse(event_count=len(serialized), events=serialized)


@audits_router.get(
    "/analyses/{analysis_id}/audit-events",
    response_model=AuditTrailResponse,
)
def get_analysis_audit_events(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> AuditTrailResponse:
    """Return events for an analysis only when it belongs to the user."""

    get_owned_analysis(session, analysis_id, current_user.id)
    events = session.scalars(
        select(AuditEvent)
        .options(joinedload(AuditEvent.actor))
        .where(AuditEvent.analysis_id == analysis_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    ).all()
    serialized = [_serialize_event(event) for event in events]
    return AuditTrailResponse(event_count=len(serialized), events=serialized)
