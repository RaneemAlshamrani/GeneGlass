"""Add Positive and Negative specialist-review outcomes.

Revision ID: 20261113_0007
Revises: 20261112_0006
"""

from alembic import op
import sqlalchemy as sa

revision = "20261113_0007"
down_revision = "20261112_0006"
branch_labels = None
depends_on = None

old_decision = sa.Enum(
    "pending",
    "approved",
    "rejected",
    "needs_more_data",
    name="review_decision",
    native_enum=False,
    create_constraint=True,
)
new_decision = sa.Enum(
    "pending",
    "approved",
    "rejected",
    "needs_more_data",
    "positive",
    "negative",
    name="review_decision",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.alter_column(
            "decision",
            existing_type=old_decision,
            type_=new_decision,
            existing_nullable=False,
            existing_server_default="pending",
        )


def downgrade() -> None:
    op.execute("UPDATE reviews SET decision = 'approved' WHERE decision = 'positive'")
    op.execute("UPDATE reviews SET decision = 'rejected' WHERE decision = 'negative'")
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.alter_column(
            "decision",
            existing_type=new_decision,
            type_=old_decision,
            existing_nullable=False,
            existing_server_default="pending",
        )
