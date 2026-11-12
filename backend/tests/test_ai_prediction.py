"""API tests for the research-only JAK2 model prediction."""

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.init_db import initialize_database
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.models.analysis import Analysis, AnalysisStatus, QCStatus
from app.schemas.auth import UserCreate
from app.services import ai_predictor
from app.services.users import create_user


def test_ai_prediction_returns_owner_scoped_research_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = create_sqlite_engine(tmp_path / "ai_prediction.db")
    initialize_database(engine)
    sessions = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    ab1_path = tmp_path / "sample.ab1"
    ab1_path.write_bytes(b"ABIF-test")

    with sessions() as session:
        owner = create_user(
            session,
            UserCreate(
                full_name="Model Specialist",
                email="model@example.com",
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
            original_file_name="sample.ab1",
            stored_file_path=str(ab1_path),
            status=AnalysisStatus.COMPLETED,
            qc_status=QCStatus.PASSED,
            gene="JAK2",
            target_variant="V617F",
        )
        session.add(analysis)
        session.commit()
        analysis_id = analysis.id

    observed: dict[str, object] = {}

    def fake_prediction(file_path: str, *, qc_passed: bool) -> dict:
        observed.update(file_path=file_path, qc_passed=qc_passed)
        return {
            "status": "Hetero",
            "prediction": "hetero",
            "probabilities": {"negative": 0.12, "hetero": 0.88},
            "reason": None,
            "orientation": "Reverse",
            "model_name": "GeneGlass Random Forest",
            "research_use_only": True,
        }

    monkeypatch.setattr(ai_predictor, "predict_ab1", fake_prediction)

    def override_get_db() -> Generator[Session, None, None]:
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            owner_login = client.post(
                "/api/auth/login",
                data={
                    "username": "model@example.com",
                    "password": "CorrectPassword123!",
                },
            )
            owner_headers = {
                "Authorization": f"Bearer {owner_login.json()['access_token']}"
            }
            response = client.get(
                f"/api/analyses/{analysis_id}/ai-prediction",
                headers=owner_headers,
            )

            other_login = client.post(
                "/api/auth/login",
                data={
                    "username": "other@example.com",
                    "password": "CorrectPassword123!",
                },
            )
            other_response = client.get(
                f"/api/analyses/{analysis_id}/ai-prediction",
                headers={
                    "Authorization": f"Bearer {other_login.json()['access_token']}"
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["analysis_id"] == analysis_id
        assert payload["prediction"] == "hetero"
        assert payload["probabilities"] == {"negative": 0.12, "hetero": 0.88}
        assert payload["research_use_only"] is True
        assert observed == {"file_path": str(ab1_path), "qc_passed": True}
        assert other_response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
