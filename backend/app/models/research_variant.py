"""Research-only candidate variants and cached external annotations."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class CandidateVariant(TimestampMixin, Base):
    """A non-diagnostic SNV candidate observed in an aligned AB1 base call."""

    __tablename__ = "candidate_variants"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id",
            "hgvs",
            name="uq_candidate_variant_analysis_hgvs",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reference_accession: Mapped[str] = mapped_column(String(50), nullable=False)
    transcript_position: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    coding_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    genomic_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_allele: Mapped[str] = mapped_column(String(10), nullable=False)
    observed_allele: Mapped[str] = mapped_column(String(10), nullable=False)
    hgvs: Mapped[str] = mapped_column(String(150), nullable=False)
    ab1_base_number: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    phred_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Needs Review",
        server_default="Needs Review",
    )
    lookup_eligible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    analysis: Mapped["Analysis"] = relationship(
        back_populates="candidate_variants"
    )
    external_annotations: Mapped[list["ExternalAnnotation"]] = relationship(
        back_populates="candidate_variant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ExternalAnnotation(TimestampMixin, Base):
    """A cached research annotation returned by an approved external source."""

    __tablename__ = "external_annotations"
    __table_args__ = (
        UniqueConstraint(
            "candidate_variant_id",
            "source",
            name="uq_external_annotation_candidate_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_variant_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    lookup_status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    accession: Mapped[str | None] = mapped_column(String(50), nullable=True)
    accession_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    variant_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    canonical_spdi: Mapped[str | None] = mapped_column(String(150), nullable=True)
    classifications_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    candidate_variant: Mapped["CandidateVariant"] = relationship(
        back_populates="external_annotations"
    )
