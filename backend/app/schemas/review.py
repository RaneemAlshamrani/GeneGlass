"""Request and response schemas for specialist evidence reviews."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.review import ReviewDecision
from app.models.user import UserRole


class ReviewCreate(BaseModel):
    decision: ReviewDecision
    comment: str = Field(min_length=3, max_length=2000)

    @field_validator("decision")
    @classmethod
    def reject_pending_decision(
        cls,
        decision: ReviewDecision,
    ) -> ReviewDecision:
        if decision is ReviewDecision.PENDING:
            raise ValueError("A submitted review must contain a final review action")
        return decision

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, comment: str) -> str:
        normalized = comment.strip()
        if len(normalized) < 3:
            raise ValueError("Review comment must contain at least 3 characters")
        return normalized


class ReviewResponse(BaseModel):
    id: int
    analysis_id: int
    decision: ReviewDecision
    comment: str
    reviewer_id: int
    reviewer_name: str
    reviewer_role: UserRole
    created_at: datetime


class ReviewHistoryResponse(BaseModel):
    analysis_id: int
    latest_decision: ReviewDecision | None
    review_count: int
    reviews: list[ReviewResponse]
