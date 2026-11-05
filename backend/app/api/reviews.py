"""Append-only specialist review workflow for saved analyses."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.analysis import Analysis
from app.models.review import Review
from app.models.user import User
from app.schemas.review import (
    ReviewCreate,
    ReviewHistoryResponse,
    ReviewResponse,
)
from app.services.audit import AuditAction, add_audit_event

reviews_router = APIRouter(prefix="/analyses", tags=["reviews"])


def _get_owned_analysis(
    session: Session,
    analysis_id: int,
    current_user: User,
) -> Analysis:
    analysis = session.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id,
        )
    )
    if analysis is None:
        # Do not reveal whether another user's analysis exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    return analysis


def _to_response(review: Review) -> ReviewResponse:
    return ReviewResponse(
        id=review.id,
        analysis_id=review.analysis_id,
        decision=review.decision,
        comment=review.comment or "",
        reviewer_id=review.reviewer_id,
        reviewer_name=review.reviewer.full_name,
        reviewer_role=review.reviewer.role,
        created_at=review.created_at,
    )


@reviews_router.get(
    "/{analysis_id}/reviews",
    response_model=ReviewHistoryResponse,
)
def get_review_history(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ReviewHistoryResponse:
    """Return the complete review history for an owned analysis."""

    _get_owned_analysis(session, analysis_id, current_user)
    reviews = session.scalars(
        select(Review)
        .options(joinedload(Review.reviewer))
        .where(Review.analysis_id == analysis_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
    ).all()
    serialized = [_to_response(review) for review in reviews]
    return ReviewHistoryResponse(
        analysis_id=analysis_id,
        latest_decision=(serialized[0].decision if serialized else None),
        review_count=len(serialized),
        reviews=serialized,
    )


@reviews_router.post(
    "/{analysis_id}/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    analysis_id: int,
    payload: ReviewCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ReviewResponse:
    """Append a specialist decision without changing mutation classification."""

    _get_owned_analysis(session, analysis_id, current_user)
    review = Review(
        analysis_id=analysis_id,
        reviewer_id=current_user.id,
        decision=payload.decision,
        comment=payload.comment,
    )
    try:
        session.add(review)
        session.flush()
        add_audit_event(
            session,
            actor_id=current_user.id,
            analysis_id=analysis_id,
            action=AuditAction.REVIEW_CREATED,
            details={
                "review_id": review.id,
                "decision": review.decision.value,
            },
        )
        session.commit()
        review = session.scalar(
            select(Review)
            .options(joinedload(Review.reviewer))
            .where(Review.id == review.id)
        )
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The specialist review could not be saved",
        ) from exc

    if review is None:  # Defensive; the committed row should always exist.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The saved specialist review could not be loaded",
        )
    return _to_response(review)
