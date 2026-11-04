"""End-to-end tests for authenticated AB1 uploads."""

from collections.abc import Generator
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.init_db import initialize_database
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.models.analysis import Analysis
from app.api import analyses as analyses_api
from app.schemas.auth import UserCreate
from app.services.storage import ab1_storage
from app.services.users import create_user
from app.services.variant_detector import (
    JAK2_V617F_REFERENCE_INDEX,
    load_jak2_reference,
)


def build_synthetic_sequencing_data() -> tuple[dict, dict]:
    reference = load_jak2_reference()
    start = JAK2_V617F_REFERENCE_INDEX - 100
    sequence = reference[start : JAK2_V617F_REFERENCE_INDEX + 101]
    quality_scores = [40] * len(sequence)
    base_positions = [index * 2 for index in range(len(sequence))]
    trace_length = base_positions[-1] + 2
    channels = {base: [5] * trace_length for base in "ACGT"}
    for index, base in enumerate(sequence):
        channels[base][base_positions[index]] = 1000

    return (
        {"sequence": sequence, "quality_scores": quality_scores},
        {
            "sequence": sequence,
            "quality_scores": quality_scores,
            "base_positions": base_positions,
            "channels": channels,
        },
    )


def test_duplicate_ab1_upload_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    test_engine = create_sqlite_engine(tmp_path / "analysis_api.db")
    initialize_database(test_engine)
    test_sessions = sessionmaker(
        bind=test_engine,
        class_=Session,
        expire_on_commit=False,
    )

    with test_sessions() as session:
        create_user(
            session,
            UserCreate(
                full_name="Upload Specialist",
                email="upload@example.com",
                password="CorrectPassword123!",
            ),
        )

    def override_get_db() -> Generator[Session, None, None]:
        with test_sessions() as session:
            yield session

    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(ab1_storage, "UPLOAD_ROOT", upload_root)
    sequencing_data, chromatogram_data = build_synthetic_sequencing_data()
    monkeypatch.setattr(
        analyses_api,
        "read_ab1_file",
        lambda _path: sequencing_data,
    )
    monkeypatch.setattr(
        analyses_api,
        "read_chromatogram",
        lambda _path: chromatogram_data,
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/api/auth/login",
                data={
                    "username": "upload@example.com",
                    "password": "CorrectPassword123!",
                },
            )
            assert login_response.status_code == 200
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            file_bytes = b"ABIF" + b"synthetic-test-data"
            first_response = client.post(
                "/api/analyses",
                headers=headers,
                files={
                    "file": (
                        "sample.ab1",
                        BytesIO(file_bytes),
                        "application/octet-stream",
                    )
                },
            )

            duplicate_response = client.post(
                "/api/analyses",
                headers=headers,
                files={
                    "file": (
                        "duplicate.ab1",
                        BytesIO(file_bytes),
                        "application/octet-stream",
                    )
                },
            )

        assert first_response.status_code == 201
        first_data = first_response.json()
        assert "v617f_detected" not in first_data
        assert first_data["preliminary_target_analysis"]["found"] is True
        assert first_data["preliminary_target_analysis"]["reference_evidence"]["variation_id"] == 14662
        assert "classification remains pending" in first_data["message"]
        assert duplicate_response.status_code == 409
        assert "already uploaded" in duplicate_response.json()["detail"]

        with test_sessions() as session:
            count = session.scalar(select(func.count()).select_from(Analysis))
            assert count == 1
            analysis = session.scalar(select(Analysis))
            assert analysis is not None
            assert analysis.v617f_detected is None
            assert analysis.preliminary_result_json is not None

        stored_files = list(upload_root.rglob("*.ab1"))
        assert len(stored_files) == 1
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()
