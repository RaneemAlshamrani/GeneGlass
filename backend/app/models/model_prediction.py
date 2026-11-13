"""Immutable, versioned outputs produced by the research AI model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class ModelPrediction(Base):
    """One append-only model run for an analysis."""

    __tablename__ = "model_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    prediction: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    negative_probability: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    hetero_probability: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    orientation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    features_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model_artifact_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    input_qc_status: Mapped[str] = mapped_column(String(30), nullable=False)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_use_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        index=True,
    )

    analysis: Mapped["Analysis"] = relationship(
        back_populates="model_predictions"
    )
