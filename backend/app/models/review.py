"""Specialist reviews attached to completed or uncertain analyses."""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SqlEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.user import User


class ReviewDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_MORE_DATA = "needs_more_data"


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    decision: Mapped[ReviewDecision] = mapped_column(
        SqlEnum(
            ReviewDecision,
            name="review_decision",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=ReviewDecision.PENDING,
        server_default=ReviewDecision.PENDING.value,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis: Mapped["Analysis"] = relationship(back_populates="reviews")
    reviewer: Mapped["User"] = relationship(
        back_populates="reviews",
        foreign_keys=[reviewer_id],
    )
