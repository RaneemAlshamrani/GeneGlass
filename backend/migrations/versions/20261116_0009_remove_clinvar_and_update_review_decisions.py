"""Remove ClinVar storage and replace specialist result options.

Revision ID: 20261116_0009
Revises: 74db28d59f99
"""

from alembic import op
import sqlalchemy as sa


revision = "20261116_0009"
down_revision = "74db28d59f99"
branch_labels = None
depends_on = None


old_decision = sa.Enum(
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
transition_decision = sa.Enum(
    "pending",
    "approved",
    "rejected",
    "needs_more_data",
    "positive",
    "negative",
    "not_detected",
    "heterozygous",
    "homozygous",
    "inconclusive",
    name="review_decision",
    native_enum=False,
    create_constraint=True,
)
new_decision = sa.Enum(
    "pending",
    "not_detected",
    "heterozygous",
    "homozygous",
    "inconclusive",
    name="review_decision",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.alter_column(
            "decision",
            existing_type=old_decision,
            type_=transition_decision,
            existing_nullable=False,
            existing_server_default="pending",
        )

    op.execute("UPDATE reviews SET decision = 'heterozygous' WHERE decision = 'positive'")
    op.execute("UPDATE reviews SET decision = 'not_detected' WHERE decision = 'negative'")
    op.execute("UPDATE reviews SET decision = 'inconclusive' WHERE decision IN ('approved', 'rejected', 'needs_more_data')")
    op.execute("UPDATE molecular_reports SET final_decision = 'heterozygous' WHERE final_decision = 'positive'")
    op.execute("UPDATE molecular_reports SET final_decision = 'not_detected' WHERE final_decision = 'negative'")

    with op.batch_alter_table("reviews") as batch_op:
        batch_op.alter_column(
            "decision",
            existing_type=transition_decision,
            type_=new_decision,
            existing_nullable=False,
            existing_server_default="pending",
        )

    op.execute("DELETE FROM audit_events WHERE action = 'analysis.clinvar_refreshed'")
    op.drop_table("external_annotations")
    op.drop_table("candidate_variants")


def downgrade() -> None:
    op.create_table(
        "candidate_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("reference_accession", sa.String(length=50), nullable=False),
        sa.Column("transcript_position", sa.Integer(), nullable=True),
        sa.Column("coding_position", sa.Integer(), nullable=True),
        sa.Column("genomic_position", sa.Integer(), nullable=True),
        sa.Column("reference_allele", sa.String(length=10), nullable=False),
        sa.Column("observed_allele", sa.String(length=10), nullable=False),
        sa.Column("hgvs", sa.String(length=150), nullable=False),
        sa.Column("ab1_base_number", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("phred_quality", sa.Integer(), nullable=True),
        sa.Column("review_status", sa.String(length=30), server_default="Needs Review", nullable=False),
        sa.Column("lookup_eligible", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("analysis_id", "hgvs", name="uq_candidate_variant_analysis_hgvs"),
    )
    op.create_index("ix_candidate_variants_analysis_id", "candidate_variants", ["analysis_id"])
    op.create_table(
        "external_annotations",
        sa.Column("id", sa.Integer(), primary_key=True),
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
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_variant_id"], ["candidate_variants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("candidate_variant_id", "source", name="uq_external_annotation_candidate_source"),
    )
    op.create_index("ix_external_annotations_candidate_variant_id", "external_annotations", ["candidate_variant_id"])

    with op.batch_alter_table("reviews") as batch_op:
        batch_op.alter_column(
            "decision",
            existing_type=new_decision,
            type_=transition_decision,
            existing_nullable=False,
            existing_server_default="pending",
        )

    op.execute("UPDATE reviews SET decision = 'negative' WHERE decision = 'not_detected'")
    op.execute("UPDATE reviews SET decision = 'positive' WHERE decision IN ('heterozygous', 'homozygous')")
    op.execute("UPDATE reviews SET decision = 'needs_more_data' WHERE decision = 'inconclusive'")
    op.execute("UPDATE molecular_reports SET final_decision = 'negative' WHERE final_decision = 'not_detected'")
    op.execute("UPDATE molecular_reports SET final_decision = 'positive' WHERE final_decision IN ('heterozygous', 'homozygous')")
    op.execute("UPDATE molecular_reports SET final_decision = 'needs_more_data' WHERE final_decision = 'inconclusive'")

    with op.batch_alter_table("reviews") as batch_op:
        batch_op.alter_column(
            "decision",
            existing_type=transition_decision,
            type_=old_decision,
            existing_nullable=False,
            existing_server_default="pending",
        )
