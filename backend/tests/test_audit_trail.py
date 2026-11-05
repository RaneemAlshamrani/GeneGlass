"""Integration tests for immutable, owner-scoped audit events."""

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.init_db import initialize_database
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.models.analysis import Analysis
from app.models.audit import AuditEvent
from app.schemas.auth import UserCreate
from app.services.users import create_user


def test_audit_events_are_created_without_secrets_and_are_owner_scoped(
    tmp_path: Path,
) -> None:
    test_engine = create_sqlite_engine(tmp_path / "audit.db")
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
                full_name="Audit Specialist",
                email="audit@example.com",
                password="CorrectPassword123!",
                department="Genetics",
            ),
        )
        create_user(
            session,
            UserCreate(
                full_name="Other Specialist",
                email="audit-other@example.com",
                password="CorrectPassword123!",
            ),
        )
        analysis = Analysis(
            user_id=owner.id,
            original_file_name="audit-sample.ab1",
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
            login = client.post(
                "/api/auth/login",
                data={
                    "username": "audit@example.com",
                    "password": "CorrectPassword123!",
                },
            )
            headers = {
                "Authorization": f"Bearer {login.json()['access_token']}"
            }
            review = client.post(
                f"/api/analyses/{analysis_id}/reviews",
                headers=headers,
                json={
                    "decision": "needs_more_data",
                    "comment": "A repeat trace is required before acceptance.",
                },
            )
            profile = client.patch(
                "/api/users/me",
                headers=headers,
                json={
                    "full_name": "Audit Specialist Updated",
                    "email": "audit@example.com",
                    "department": "Molecular Genetics",
                },
            )
            password = client.post(
                "/api/auth/change-password",
                headers=headers,
                json={
                    "current_password": "CorrectPassword123!",
                    "new_password": "DifferentPassword123!",
                },
            )
            analysis_trail = client.get(
                f"/api/analyses/{analysis_id}/audit-events",
                headers=headers,
            )
            my_trail = client.get("/api/audit-events", headers=headers)

            other_login = client.post(
                "/api/auth/login",
                data={
                    "username": "audit-other@example.com",
                    "password": "CorrectPassword123!",
                },
            )
            other_headers = {
                "Authorization": (
                    f"Bearer {other_login.json()['access_token']}"
                )
            }
            hidden = client.get(
                f"/api/analyses/{analysis_id}/audit-events",
                headers=other_headers,
            )

        assert review.status_code == 201
        assert profile.status_code == 200
        assert password.status_code == 200
        assert analysis_trail.status_code == 200
        assert hidden.status_code == 404

        analysis_payload = analysis_trail.json()
        assert analysis_payload["event_count"] == 1
        assert analysis_payload["events"][0]["action"] == (
            "analysis.review_created"
        )
        assert analysis_payload["events"][0]["details"]["decision"] == (
            "needs_more_data"
        )

        actions = {event["action"] for event in my_trail.json()["events"]}
        assert {
            "auth.login_succeeded",
            "analysis.review_created",
            "user.profile_updated",
            "auth.password_changed",
        }.issubset(actions)

        with test_sessions() as session:
            events = session.scalars(select(AuditEvent)).all()
            serialized_details = " ".join(
                event.details_json or "" for event in events
            )
            assert "CorrectPassword123!" not in serialized_details
            assert "DifferentPassword123!" not in serialized_details
            assert "access_token" not in serialized_details
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()
