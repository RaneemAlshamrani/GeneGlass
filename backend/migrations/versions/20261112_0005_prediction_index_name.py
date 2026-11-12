"""Align the model artifact index name with SQLAlchemy metadata.

Revision ID: 20261112_0005
Revises: 20261112_0004
Create Date: 2026-11-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261112_0005"
down_revision: Union[str, Sequence[str], None] = "20261112_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_model_predictions_artifact", table_name="model_predictions")
    op.create_index(
        "ix_model_predictions_model_artifact_sha256",
        "model_predictions",
        ["model_artifact_sha256"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_model_predictions_model_artifact_sha256",
        table_name="model_predictions",
    )
    op.create_index(
        "ix_model_predictions_artifact",
        "model_predictions",
        ["model_artifact_sha256"],
    )
