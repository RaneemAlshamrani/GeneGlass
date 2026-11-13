"""Tests for owner-scoped deletion from analysis History."""

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api import analyses as analyses_api
from app.db.init_db import initialize_database
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.models.analysis import Analysis
from app.models.audit import AuditEvent
from app.models.molecular_report import MolecularReport
from app.schemas.auth import UserCreate
from app.services.users import create_user


def test_owner_can_delete_analysis_files_but_other_user_cannot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = create_sqlite_engine(tmp_path / "delete.db")
    initialize_database(engine)
    sessions = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    upload_root = tmp_path / "uploads"
    with sessions() as session:
        owner = create_user(
            session,
            UserCreate(
                full_name="Delete Owner",
                email="delete-owner@example.com",
                password="CorrectPassword123!",
            ),
        )
        create_user(
            session,
            UserCreate(
                full_name="Other User",
                email="delete-other@example.com",
                password="CorrectPassword123!",
            ),
        )
        owner_dir = upload_root / f"user_{owner.id}"
        owner_dir.mkdir(parents=True)
        patient_path = owner_dir / "patient.ab1"
        control_path = owner_dir / "control.ab1"
        patient_path.write_bytes(b"ABIF-patient")
        control_path.write_bytes(b"ABIF-control")
        analysis = Analysis(
            user_id=owner.id,
            original_file_name="patient.ab1",
            stored_file_path=str(patient_path),
        )
        session.add(analysis)
        session.flush()
        session.add(
            MolecularReport(
                analysis_id=analysis.id,
                author_id=owner.id,
                version=1,
                status="finalized",
                final_decision="negative",
                normal_control_file_path=str(control_path),
            )
        )
        session.commit()
        analysis_id = analysis.id

    def override_get_db() -> Generator[Session, None, None]:
        with sessions() as session:
            yield session

    monkeypatch.setattr(analyses_api, "UPLOAD_ROOT", upload_root)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            owner_login = client.post(
                "/api/auth/login",
                data={
                    "username": "delete-owner@example.com",
                    "password": "CorrectPassword123!",
                },
            )
            other_login = client.post(
                "/api/auth/login",
                data={
                    "username": "delete-other@example.com",
                    "password": "CorrectPassword123!",
                },
            )
            owner_headers = {
                "Authorization": f"Bearer {owner_login.json()['access_token']}"
            }
            other_headers = {
                "Authorization": f"Bearer {other_login.json()['access_token']}"
            }

            hidden = client.delete(
                f"/api/analyses/{analysis_id}",
                headers=other_headers,
            )
            assert hidden.status_code == 404
            assert patient_path.exists()
            assert control_path.exists()

            deleted = client.delete(
                f"/api/analyses/{analysis_id}",
                headers=owner_headers,
            )
            missing = client.get(
                f"/api/analyses/{analysis_id}",
                headers=owner_headers,
            )

        assert deleted.status_code == 200
        assert deleted.json() == {"id": analysis_id, "status": "deleted"}
        assert missing.status_code == 404
        assert not patient_path.exists()
        assert not control_path.exists()

        with sessions() as session:
            assert session.get(Analysis, analysis_id) is None
            assert session.scalar(
                select(MolecularReport).where(
                    MolecularReport.analysis_id == analysis_id
                )
            ) is None
            event = session.scalar(
                select(AuditEvent).where(
                    AuditEvent.action == "analysis.deleted"
                )
            )
            assert event is not None
            assert event.analysis_id is None
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
