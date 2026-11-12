"""Editable molecular-report drafts and immutable finalized revisions."""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.user import User


class MolecularReport(TimestampMixin, Base):
    __tablename__ = "molecular_reports"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id",
            "version",
            name="uq_molecular_reports_analysis_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True
    )
    patient_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    medical_record_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    physician_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    report_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    received_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    submitted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    clinical_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    specimen_type: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Peripheral Blood"
    )
    final_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)
    normal_control_file_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    normal_control_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    analysis: Mapped["Analysis"] = relationship(
        back_populates="molecular_reports"
    )
    author: Mapped["User"] = relationship(
        back_populates="molecular_reports",
        foreign_keys=[author_id],
    )
