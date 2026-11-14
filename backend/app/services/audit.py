"""Helpers for adding privacy-conscious audit events to a transaction."""

import json
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


class AuditAction(StrEnum):
    LOGIN_SUCCEEDED = "auth.login_succeeded"
    PROFILE_UPDATED = "user.profile_updated"
    PASSWORD_CHANGED = "auth.password_changed"
    ANALYSIS_UPLOADED = "analysis.uploaded"
    QC_DECISION_RECORDED = "analysis.qc_decision_recorded"
    ANALYSIS_RECALCULATED = "analysis.preliminary_evidence_recalculated"
    AI_PREDICTION_CREATED = "analysis.ai_prediction_created"
    ANALYSIS_DELETED = "analysis.deleted"
    REPORT_DRAFT_SAVED = "analysis.report_draft_saved"
    REPORT_FINALIZED = "analysis.report_finalized"
    REVIEW_CREATED = "analysis.review_created"
    CLINVAR_REFRESHED = "analysis.clinvar_refreshed"


def add_audit_event(
    session: Session,
    *,
    actor_id: int,
    action: AuditAction,
    analysis_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add an event to the caller's transaction without committing it."""

    event = AuditEvent(
        actor_id=actor_id,
        analysis_id=analysis_id,
        action=action.value,
        details_json=(
            json.dumps(details, ensure_ascii=True, separators=(",", ":"))
            if details
            else None
        ),
    )
    session.add(event)
    return event
