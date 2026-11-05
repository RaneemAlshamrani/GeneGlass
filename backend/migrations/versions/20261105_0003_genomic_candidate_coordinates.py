"""Add genomic coordinates to research candidates.

Revision ID: 20261105_0003
Revises: 20261105_0002
Create Date: 2026-11-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261105_0003"
down_revision: Union[str, Sequence[str], None] = "20261105_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("candidate_variants") as batch_op:
        batch_op.add_column(
            sa.Column("genomic_position", sa.Integer(), nullable=True)
        )
        batch_op.alter_column(
            "transcript_position",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM candidate_variants WHERE transcript_position IS NULL"
    )
    with op.batch_alter_table("candidate_variants") as batch_op:
        batch_op.alter_column(
            "transcript_position",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.drop_column("genomic_position")
