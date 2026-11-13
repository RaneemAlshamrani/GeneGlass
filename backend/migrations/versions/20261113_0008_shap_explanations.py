"""Store reproducible SHAP explanations with model predictions.

Revision ID: 20261113_0008
Revises: 20261113_0007
"""

from alembic import op
import sqlalchemy as sa

revision = "20261113_0008"
down_revision = "20261113_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_predictions") as batch_op:
        batch_op.add_column(
            sa.Column("explanation_json", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("model_predictions") as batch_op:
        batch_op.drop_column("explanation_json")
