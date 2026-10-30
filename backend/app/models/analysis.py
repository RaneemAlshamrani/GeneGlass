
"""JAK2 analysis records and workflow state."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.review import Review
    from app.models.user import User


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class QCStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class Analysis(TimestampMixin, Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    original_file_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    stored_file_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    file_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    gene: Mapped[str] = mapped_column(
        String(50), nullable=False, default="JAK2"
    )
    target_variant: Mapped[str] = mapped_column(
        String(50), nullable=False, default="V617F"
    )

    status: Mapped[AnalysisStatus] = mapped_column(
        SqlEnum(
            AnalysisStatus,
            name="analysis_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=AnalysisStatus.PENDING,
        server_default=AnalysisStatus.PENDING.value,
        index=True,
    )

    qc_status: Mapped[QCStatus] = mapped_column(
        SqlEnum(
            QCStatus,
            name="qc_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=QCStatus.PENDING,
        server_default=QCStatus.PENDING.value,
    )

    # Quality control metrics
    sequence_length: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    cleaned_sequence_length: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    average_quality: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    minimum_quality: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    maximum_quality: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    low_quality_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    low_quality_percentage: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    retained_percentage: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    quality_assessment: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    # Variant detection fields - reserved for the later module
    v617f_detected: Mapped[bool | None] = mapped_column(nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )

    owner: Mapped["User"] = relationship(back_populates="analyses")

    reviews: Mapped[list["Review"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
