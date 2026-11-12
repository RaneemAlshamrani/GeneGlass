"""Add immutable, versioned model prediction records.

Revision ID: 20261112_0004
Revises: 20261105_0003
Create Date: 2026-11-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261112_0004"
down_revision: Union[str, Sequence[str], None] = "20261105_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("prediction", sa.String(length=20), nullable=True),
        sa.Column("negative_probability", sa.Float(), nullable=True),
        sa.Column("hetero_probability", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("orientation", sa.String(length=20), nullable=True),
        sa.Column("features_json", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=150), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column(
            "model_artifact_sha256", sa.String(length=64), nullable=False
        ),
        sa.Column("input_qc_status", sa.String(length=30), nullable=False),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column(
            "research_use_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    op.create_index(
        "ix_model_predictions_analysis_id",
        "model_predictions",
        ["analysis_id"],
    )
    op.create_index(
        "ix_model_predictions_status", "model_predictions", ["status"]
    )
    op.create_index(
        "ix_model_predictions_prediction",
        "model_predictions",
        ["prediction"],
    )
    op.create_index(
        "ix_model_predictions_artifact",
        "model_predictions",
        ["model_artifact_sha256"],
    )
    op.create_index(
        "ix_model_predictions_created_at",
        "model_predictions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_model_predictions_created_at", table_name="model_predictions")
    op.drop_index("ix_model_predictions_artifact", table_name="model_predictions")
    op.drop_index("ix_model_predictions_prediction", table_name="model_predictions")
    op.drop_index("ix_model_predictions_status", table_name="model_predictions")
    op.drop_index("ix_model_predictions_analysis_id", table_name="model_predictions")
    op.drop_table("model_predictions")
