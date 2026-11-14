"""Specialist decisions made before AI prediction."""

from enum import Enum

from sqlalchemy import Enum as SqlEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class QCDecision(str, Enum):
    CONTINUE_ANALYSIS = "continue_analysis"
    REQUEST_REPEAT = "request_repeat"


class PreliminaryQCDecision(TimestampMixin, Base):
    __tablename__ = "preliminary_qc_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)

    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    decision: Mapped[QCDecision] = mapped_column(
        SqlEnum(
            QCDecision,
            name="preliminary_qc_decision",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [
                item.value for item in enum
            ],
        ),
        nullable=False,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )