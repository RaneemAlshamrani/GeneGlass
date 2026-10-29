from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.db.init_db import initialize_database
from app.db.session import create_sqlite_engine
from app.models import Analysis, Review, User


def test_database_schema_and_foreign_keys(tmp_path: Path) -> None:
    test_engine = create_sqlite_engine(tmp_path / "test_geneglass.db")

    tables = initialize_database(test_engine)

    assert tables == ["analyses", "reviews", "users"]
    assert set(inspect(test_engine).get_table_names()) == {
        "users",
        "analyses",
        "reviews",
    }
    with test_engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

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
        session.commit()

        stored_analysis = session.scalar(select(Analysis))
        stored_review = session.scalar(select(Review))

        assert stored_analysis is not None
        assert stored_analysis.owner.email == "specialist@example.com"
        assert stored_analysis.gene == "JAK2"
        assert stored_analysis.target_variant == "V617F"
        assert stored_review is not None
        assert stored_review.analysis_id == stored_analysis.id

    test_engine.dispose()
