"""Add editable molecular report revisions.

Revision ID: 20261112_0006
Revises: 20261112_0005
Create Date: 2026-11-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261112_0006"
down_revision: Union[str, Sequence[str], None] = "20261112_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "molecular_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("patient_name", sa.String(length=200), nullable=True),
        sa.Column("medical_record_number", sa.String(length=100), nullable=True),
        sa.Column("gender", sa.String(length=30), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("physician_name", sa.String(length=200), nullable=True),
        sa.Column("report_number", sa.String(length=100), nullable=True),
        sa.Column("received_date", sa.Date(), nullable=True),
        sa.Column("submitted_date", sa.Date(), nullable=True),
        sa.Column("clinical_history", sa.Text(), nullable=True),
        sa.Column(
            "specimen_type",
            sa.String(length=100),
            nullable=False,
            server_default="Peripheral Blood",
        ),
        sa.Column("final_decision", sa.String(length=20), nullable=True),
        sa.Column("interpretation", sa.Text(), nullable=True),
        sa.Column("normal_control_file_path", sa.String(length=500), nullable=True),
        sa.Column("normal_control_sha256", sa.String(length=64), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint(
            "analysis_id",
            "version",
            name="uq_molecular_reports_analysis_version",
        ),
    )
    op.create_index(
        "ix_molecular_reports_analysis_id",
        "molecular_reports",
        ["analysis_id"],
    )
    op.create_index(
        "ix_molecular_reports_author_id",
        "molecular_reports",
        ["author_id"],
    )
    op.create_index(
        "ix_molecular_reports_status",
        "molecular_reports",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_molecular_reports_status", table_name="molecular_reports")
    op.drop_index("ix_molecular_reports_author_id", table_name="molecular_reports")
    op.drop_index("ix_molecular_reports_analysis_id", table_name="molecular_reports")
    op.drop_table("molecular_reports")
