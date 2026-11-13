"""API tests for the append-only specialist review workflow."""

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.init_db import initialize_database
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.models.analysis import Analysis
from app.models.review import Review
from app.schemas.auth import UserCreate
from app.services.users import create_user


def test_specialist_review_history_is_append_only_and_owner_scoped(
    tmp_path: Path,
) -> None:
    test_engine = create_sqlite_engine(tmp_path / "reviews.db")
    initialize_database(test_engine)
    test_sessions = sessionmaker(
        bind=test_engine,
        class_=Session,
        expire_on_commit=False,
    )

    with test_sessions() as session:
        owner = create_user(
            session,
            UserCreate(
                full_name="Review Specialist",
                email="reviewer@example.com",
                password="CorrectPassword123!",
            ),
        )
        create_user(
            session,
            UserCreate(
                full_name="Different Specialist",
                email="other@example.com",
                password="CorrectPassword123!",
            ),
        )
        analysis = Analysis(
            user_id=owner.id,
            original_file_name="review-sample.ab1",
            result_summary="Preliminary evidence only",
        )
        session.add(analysis)
        session.commit()
        analysis_id = analysis.id

    def override_get_db() -> Generator[Session, None, None]:
        with test_sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            owner_login = client.post(
                "/api/auth/login",
                data={
                    "username": "reviewer@example.com",
                    "password": "CorrectPassword123!",
                },
            )
            owner_headers = {
                "Authorization": (
                    f"Bearer {owner_login.json()['access_token']}"
                )
            }

            first = client.post(
                f"/api/analyses/{analysis_id}/reviews",
                headers=owner_headers,
                json={
                    "decision": "needs_more_data",
                    "comment": "Repeat sequencing is required for this region.",
                },
            )
            second = client.post(
                f"/api/analyses/{analysis_id}/reviews",
                headers=owner_headers,
                json={
                    "decision": "positive",
                    "comment": "The repeated trace supports a Positive JAK2 V617F decision.",
                },
            )
            history = client.get(
                f"/api/analyses/{analysis_id}/reviews",
                headers=owner_headers,
            )
            invalid = client.post(
                f"/api/analyses/{analysis_id}/reviews",
                headers=owner_headers,
                json={"decision": "pending", "comment": "Wait"},
            )

            other_login = client.post(
                "/api/auth/login",
                data={
                    "username": "other@example.com",
                    "password": "CorrectPassword123!",
                },
            )
            other_headers = {
                "Authorization": (
                    f"Bearer {other_login.json()['access_token']}"
                )
            }
            forbidden_history = client.get(
                f"/api/analyses/{analysis_id}/reviews",
                headers=other_headers,
            )

        assert first.status_code == 201
        assert second.status_code == 201
        assert invalid.status_code == 422
        assert forbidden_history.status_code == 404

        payload = history.json()
        assert history.status_code == 200
        assert payload["review_count"] == 2
        assert payload["latest_decision"] == "positive"
        assert [item["decision"] for item in payload["reviews"]] == [
            "positive",
            "needs_more_data",
        ]
        assert payload["reviews"][0]["reviewer_name"] == "Review Specialist"

        with test_sessions() as session:
            assert session.scalar(select(func.count()).select_from(Review)) == 2
            stored_analysis = session.get(Analysis, analysis_id)
            assert stored_analysis is not None
            assert stored_analysis.v617f_detected is None
            assert stored_analysis.result_summary == "Preliminary evidence only"
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()
