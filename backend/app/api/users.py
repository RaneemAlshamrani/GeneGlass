"""Profile endpoints for the authenticated user."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.analysis import Analysis, AnalysisStatus, QCStatus
from app.models.user import User
from app.schemas.profile import (
    ProfileResponse,
    ProfileStatisticsResponse,
    ProfileUpdate,
)

users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.patch("/me", response_model=ProfileResponse)
def update_my_profile(
    profile_data: ProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    """Update the signed-in user's profile."""

    email = str(profile_data.email).strip().lower()

    existing_user = session.scalar(
        select(User).where(
            User.email == email,
            User.id != current_user.id,
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already in use.",
        )

    current_user.full_name = profile_data.full_name.strip()
    current_user.email = email
    current_user.department = (
        profile_data.department.strip()
        if profile_data.department
        and profile_data.department.strip()
        else None
    )

    try:
        session.commit()
        session.refresh(current_user)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not update profile because the email is already in use.",
        )

    return current_user


@users_router.get(
    "/me/statistics",
    response_model=ProfileStatisticsResponse,
)
def read_my_profile_statistics(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ProfileStatisticsResponse:
    """Return analysis statistics belonging to the signed-in user."""

    total_analyses = session.scalar(
        select(func.count(Analysis.id)).where(
            Analysis.user_id == current_user.id
        )
    ) or 0

    completed_analyses = session.scalar(
        select(func.count(Analysis.id)).where(
            Analysis.user_id == current_user.id,
            Analysis.status == AnalysisStatus.COMPLETED,
        )
    ) or 0

    needs_review = session.scalar(
        select(func.count(Analysis.id)).where(
            Analysis.user_id == current_user.id,
            Analysis.qc_status == QCStatus.NEEDS_REVIEW,
        )
    ) or 0

    return ProfileStatisticsResponse(
        total_analyses=total_analyses,
        completed_analyses=completed_analyses,
        needs_review=needs_review,
    )