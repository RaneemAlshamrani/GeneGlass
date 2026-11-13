"""API tests for the short molecular-report workflow."""

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api import reports as reports_api
from app.db.init_db import initialize_database
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.models.analysis import Analysis
from app.models.molecular_report import MolecularReport
from app.schemas.auth import UserCreate
from app.services.users import create_user


def test_report_is_finalized_versioned_and_owner_scoped(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = create_sqlite_engine(tmp_path / "reports.db")
    initialize_database(engine)
    sessions = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )
    patient_path = tmp_path / "patient.ab1"
    patient_path.write_bytes(b"ABIF-patient")

    with sessions() as session:
        owner = create_user(
            session,
            UserCreate(
                full_name="Report Specialist",
                email="report@example.com",
                password="CorrectPassword123!",
            ),
        )
        create_user(
            session,
            UserCreate(
                full_name="Other Specialist",
                email="other@example.com",
                password="CorrectPassword123!",
            ),
        )
        analysis = Analysis(
            user_id=owner.id,
            original_file_name="patient.ab1",
            stored_file_path=str(patient_path),
        )
        session.add(analysis)
        session.commit()
        owner_id = owner.id
        analysis_id = analysis.id

    async def fake_save_control(upload, user_id: int):
        assert user_id == owner_id
        control_path = tmp_path / "normal-control.ab1"
        control_path.write_bytes(await upload.read())
        await upload.close()
        return control_path, "a" * 64

    monkeypatch.setattr(reports_api, "save_ab1_file", fake_save_control)
    monkeypatch.setattr(
        reports_api,
        "read_chromatogram",
        lambda _path: {"sequence": "ACAT"},
    )
    monkeypatch.setattr(
        reports_api,
        "find_jak2_v617f_position",
        lambda _sequence: {"found": True},
    )
    monkeypatch.setattr(
        reports_api,
        "build_molecular_report_pdf",
        lambda report, _analysis, _author: (
            b"%PDF-1.4\n"
            + f"decision={report.final_decision}".encode()
        ),
    )

    def override_get_db() -> Generator[Session, None, None]:
        with sessions() as session:
            yield session

    form = {
        "patient_name": "Test Patient",
        "medical_record_number": "MRN-001",
        "gender": "Female",
        "date_of_birth": "1990-01-02",
        "physician_name": "Dr. Example",
        "report_number": "GG-001",
        "received_date": "2026-11-11",
        "submitted_date": "2026-11-12",
        "clinical_history": "Research case",
        "specimen_type": "Peripheral Blood",
        "interpretation": "Specialist-confirmed positive result.",
    }

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            owner_login = client.post(
                "/api/auth/login",
                data={
                    "username": "report@example.com",
                    "password": "CorrectPassword123!",
                },
            )
            owner_headers = {
                "Authorization": f"Bearer {owner_login.json()['access_token']}"
            }
            awaiting = client.get(
                "/api/analyses",
                headers=owner_headers,
            )
            blocked = client.put(
                f"/api/analyses/{analysis_id}/report",
                headers=owner_headers,
                data=form,
            )
            positive_review = client.post(
                f"/api/analyses/{analysis_id}/reviews",
                headers=owner_headers,
                json={
                    "decision": "positive",
                    "comment": "Specialist confirms a Positive JAK2 V617F decision.",
                },
            )
            ready = client.get(
                f"/api/analyses/{analysis_id}",
                headers=owner_headers,
            )
            saved = client.put(
                f"/api/analyses/{analysis_id}/report",
                headers=owner_headers,
                data=form,
                files={
                    "normal_control": (
                        "normal-control.ab1",
                        b"ABIF-control",
                        "application/octet-stream",
                    )
                },
            )
            finalized = client.post(
                f"/api/analyses/{analysis_id}/report/finalize",
                headers=owner_headers,
            )
            archived = client.get(
                "/api/analyses",
                headers=owner_headers,
            )
            pdf = client.get(
                f"/api/analyses/{analysis_id}/report.pdf",
                headers=owner_headers,
            )

            negative_review = client.post(
                f"/api/analyses/{analysis_id}/reviews",
                headers=owner_headers,
                json={
                    "decision": "negative",
                    "comment": "Specialist confirms a Negative JAK2 V617F decision.",
                },
            )
            second_form = {
                **form,
                "interpretation": "Specialist-confirmed negative result.",
            }
            revised = client.put(
                f"/api/analyses/{analysis_id}/report",
                headers=owner_headers,
                data=second_form,
            )

            other_login = client.post(
                "/api/auth/login",
                data={
                    "username": "other@example.com",
                    "password": "CorrectPassword123!",
                },
            )
            hidden = client.get(
                f"/api/analyses/{analysis_id}/report",
                headers={
                    "Authorization": (
                        f"Bearer {other_login.json()['access_token']}"
                    )
                },
            )

        assert blocked.status_code == 409
        assert awaiting.status_code == 200
        assert awaiting.json()["items"][0]["report"] == {
            "status": "awaiting_decision",
            "decision": None,
            "version": None,
            "download_url": None,
        }
        assert positive_review.status_code == 201
        assert ready.status_code == 200
        assert ready.json()["report"]["status"] == "ready_to_create"
        assert ready.json()["report"]["decision"] == "positive"
        assert saved.status_code == 200
        assert saved.json()["report"]["normal_control_uploaded"] is True
        assert finalized.status_code == 200
        assert finalized.json()["report"]["status"] == "finalized"
        assert archived.status_code == 200
        archived_report = archived.json()["items"][0]["report"]
        assert archived_report["status"] == "finalized"
        assert archived_report["decision"] == "positive"
        assert archived_report["version"] == 1
        assert archived_report["download_url"].endswith("report.pdf?version=1")
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF-1.4")
        assert b"decision=positive" in pdf.content
        assert negative_review.status_code == 201
        assert revised.status_code == 200
        assert revised.json()["report"]["version"] == 2
        assert revised.json()["report"]["status"] == "draft"
        assert revised.json()["report"]["final_decision"] == "negative"
        assert hidden.status_code == 404

        with sessions() as session:
            reports = session.scalars(
                select(MolecularReport).order_by(MolecularReport.version)
            ).all()
            assert [(item.version, item.status) for item in reports] == [
                (1, "finalized"),
                (2, "draft"),
            ]
            assert reports[0].final_decision == "positive"
            assert (
                reports[1].normal_control_file_path
                == reports[0].normal_control_file_path
            )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
