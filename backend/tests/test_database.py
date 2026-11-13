from pathlib import Path

from alembic import command
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.db.init_db import build_alembic_config, initialize_database
from app.db.session import create_sqlite_engine
from app.models import (
    Analysis,
    AuditEvent,
    CandidateVariant,
    ExternalAnnotation,
    ModelPrediction,
    MolecularReport,
    Review,
    User,
)


def test_database_schema_and_foreign_keys(tmp_path: Path) -> None:
    test_engine = create_sqlite_engine(tmp_path / "test_geneglass.db")

    tables = initialize_database(test_engine)

    assert tables == [
        "alembic_version",
        "analyses",
        "audit_events",
        "candidate_variants",
        "external_annotations",
        "model_predictions",
        "molecular_reports",
        "reviews",
        "users",
    ]
    assert set(inspect(test_engine).get_table_names()) == {
        "alembic_version",
        "users",
        "analyses",
        "audit_events",
        "candidate_variants",
        "external_annotations",
        "model_predictions",
        "molecular_reports",
        "reviews",
    }
    with test_engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert MigrationContext.configure(connection).get_current_revision() == (
            "20261113_0008"
        )

    command.check(build_alembic_config(test_engine))

    test_engine.dispose()


def test_existing_current_schema_is_stamped_without_data_loss(
    tmp_path: Path,
) -> None:
    test_engine = create_sqlite_engine(tmp_path / "legacy.db")
    Base.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        session.add(User(full_name="Legacy User", email="legacy@example.com"))
        session.commit()

    tables = initialize_database(test_engine)

    assert "alembic_version" in tables
    with Session(test_engine) as session:
        user = session.scalar(select(User).where(User.email == "legacy@example.com"))
        assert user is not None
        assert user.full_name == "Legacy User"
    with test_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == (
            "20261113_0008"
        )

    test_engine.dispose()


def test_migration_can_downgrade_and_upgrade_a_temporary_database(
    tmp_path: Path,
) -> None:
    test_engine = create_sqlite_engine(tmp_path / "round_trip.db")
    config = build_alembic_config(test_engine)
    command.upgrade(config, "head")

    command.downgrade(config, "base")
    tables_after_downgrade = set(inspect(test_engine).get_table_names())
    assert not (set(Base.metadata.tables) & tables_after_downgrade)

    command.upgrade(config, "head")
    assert set(Base.metadata.tables).issubset(
        set(inspect(test_engine).get_table_names())
    )

    test_engine.dispose()


def test_partial_legacy_schema_is_rejected(tmp_path: Path) -> None:
    test_engine = create_sqlite_engine(tmp_path / "partial_legacy.db")
    Base.metadata.tables["users"].create(test_engine)

    with pytest.raises(RuntimeError, match="does not match"):
        initialize_database(test_engine)

    assert "alembic_version" not in inspect(test_engine).get_table_names()
    test_engine.dispose()


def test_user_analysis_review_relationships(tmp_path: Path) -> None:
    test_engine = create_sqlite_engine(tmp_path / "relationships.db")
    initialize_database(test_engine)

    with Session(test_engine) as session:
        user = User(full_name="Test Specialist", email="specialist@example.com")
        session.add(user)
        session.flush()

        analysis = Analysis(
            user_id=user.id,
            original_file_name="sample.ab1",
        )
        session.add(analysis)
        session.flush()

        review = Review(
            analysis_id=analysis.id,
            reviewer_id=user.id,
            comment="Database relationship test",
        )
        session.add(review)
        session.add(MolecularReport(
            analysis_id=analysis.id,
            author_id=user.id,
            version=1,
            patient_name="Test Patient",
        ))
        session.add(AuditEvent(
            actor_id=user.id,
            analysis_id=analysis.id,
            action="analysis.review_created",
        ))
        candidate = CandidateVariant(
            analysis_id=analysis.id,
            reference_accession="NM_004972.4",
            transcript_position=2316,
            coding_position=1849,
            reference_allele="G",
            observed_allele="T",
            hgvs="NM_004972.4:c.1849G>T",
            ab1_base_number=101,
            direction="Forward",
            phred_quality=40,
            review_status="Research Candidate",
            lookup_eligible=True,
        )
        session.add(candidate)
        session.flush()
        session.add(ExternalAnnotation(
            candidate_variant_id=candidate.id,
            source="NCBI ClinVar",
            lookup_status="matched",
            source_record_id="14662",
            fetched_at=analysis.created_at,
        ))
        session.commit()

        stored_analysis = session.scalar(select(Analysis))
        stored_review = session.scalar(select(Review))
        stored_audit_event = session.scalar(select(AuditEvent))
        stored_report = session.scalar(select(MolecularReport))

        assert stored_analysis is not None
        assert stored_analysis.owner.email == "specialist@example.com"
        assert stored_analysis.gene == "JAK2"
        assert stored_analysis.target_variant == "V617F"
        assert stored_review is not None
        assert stored_review.analysis_id == stored_analysis.id
        assert stored_audit_event is not None
        assert stored_audit_event.actor.email == "specialist@example.com"
        assert stored_audit_event.analysis_id == stored_analysis.id
        assert stored_report is not None
        assert stored_report.analysis_id == stored_analysis.id
        assert stored_report.author.email == "specialist@example.com"
        assert stored_analysis.candidate_variants[0].hgvs == "NM_004972.4:c.1849G>T"
        assert stored_analysis.candidate_variants[0].external_annotations[0].source_record_id == "14662"

    test_engine.dispose()
