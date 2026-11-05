"""Create the current GeneGlass schema.

Revision ID: 20261105_0001
Revises:
Create Date: 2026-11-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261105_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def timestamp_columns() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=150), nullable=True),
        sa.Column(
            "role",
            sa.Enum(
                "specialist",
                "reviewer",
                "admin",
                name="user_role",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="specialist",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("original_file_name", sa.String(length=255), nullable=False),
        sa.Column("stored_file_path", sa.String(length=500), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column("gene", sa.String(length=50), nullable=False),
        sa.Column("target_variant", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "completed",
                "failed",
                name="analysis_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "qc_status",
            sa.Enum(
                "pending",
                "passed",
                "needs_review",
                "failed",
                name="qc_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("sequence_length", sa.Integer(), nullable=True),
        sa.Column("cleaned_sequence_length", sa.Integer(), nullable=True),
        sa.Column("average_quality", sa.Float(), nullable=True),
        sa.Column("minimum_quality", sa.Integer(), nullable=True),
        sa.Column("maximum_quality", sa.Integer(), nullable=True),
        sa.Column("low_quality_count", sa.Integer(), nullable=True),
        sa.Column("low_quality_percentage", sa.Float(), nullable=True),
        sa.Column("retained_percentage", sa.Float(), nullable=True),
        sa.Column("quality_assessment", sa.String(length=20), nullable=True),
        sa.Column("v617f_detected", sa.Boolean(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("preliminary_result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analyses_file_sha256", "analyses", ["file_sha256"])
    op.create_index("ix_analyses_status", "analyses", ["status"])
    op.create_index("ix_analyses_user_id", "analyses", ["user_id"])

    op.create_table(
        "candidate_variants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("reference_accession", sa.String(length=50), nullable=False),
        sa.Column("transcript_position", sa.Integer(), nullable=False),
        sa.Column("coding_position", sa.Integer(), nullable=True),
        sa.Column("reference_allele", sa.String(length=10), nullable=False),
        sa.Column("observed_allele", sa.String(length=10), nullable=False),
        sa.Column("hgvs", sa.String(length=150), nullable=False),
        sa.Column("ab1_base_number", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("phred_quality", sa.Integer(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=30),
            server_default="Needs Review",
            nullable=False,
        ),
        sa.Column(
            "lookup_eligible",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "analysis_id",
            "hgvs",
            name="uq_candidate_variant_analysis_hgvs",
        ),
    )
    op.create_index(
        "ix_candidate_variants_analysis_id",
        "candidate_variants",
        ["analysis_id"],
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "needs_more_data",
                name="review_decision",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reviews_analysis_id", "reviews", ["analysis_id"])
    op.create_index("ix_reviews_reviewer_id", "reviews", ["reviewer_id"])

    op.create_table(
        "external_annotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_variant_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("lookup_status", sa.String(length=20), nullable=False),
        sa.Column("source_record_id", sa.String(length=50), nullable=True),
        sa.Column("accession", sa.String(length=50), nullable=True),
        sa.Column("accession_version", sa.String(length=60), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("variant_type", sa.String(length=100), nullable=True),
        sa.Column("canonical_spdi", sa.String(length=150), nullable=True),
        sa.Column("classifications_json", sa.Text(), nullable=True),
        sa.Column("conditions_json", sa.Text(), nullable=True),
        sa.Column("review_status", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["candidate_variant_id"],
            ["candidate_variants.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_variant_id",
            "source",
            name="uq_external_annotation_candidate_source",
        ),
    )
    op.create_index(
        "ix_external_annotations_candidate_variant_id",
        "external_annotations",
        ["candidate_variant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_annotations_candidate_variant_id",
        table_name="external_annotations",
    )
    op.drop_table("external_annotations")
    op.drop_index("ix_reviews_reviewer_id", table_name="reviews")
    op.drop_index("ix_reviews_analysis_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index(
        "ix_candidate_variants_analysis_id",
        table_name="candidate_variants",
    )
    op.drop_table("candidate_variants")
    op.drop_index("ix_analyses_user_id", table_name="analyses")
    op.drop_index("ix_analyses_status", table_name="analyses")
    op.drop_index("ix_analyses_file_sha256", table_name="analyses")
    op.drop_table("analyses")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
