"""Shared lookup for analyses owned by an authenticated user."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import Analysis


def get_owned_analysis(session: Session, analysis_id: int, user_id: int) -> Analysis:
    """Return a user's analysis or the same 404 for missing and foreign IDs."""
    analysis = session.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == user_id,
        )
    )
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    return analysis
