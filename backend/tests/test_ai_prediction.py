"""API tests for the research-only JAK2 model prediction."""

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.init_db import initialize_database
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.models.analysis import Analysis, AnalysisStatus, QCStatus
from app.models.model_prediction import ModelPrediction
from app.schemas.auth import UserCreate
from app.services import model_predictions
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
            preliminary_result_json='{"found":true}',
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
            "model_version": "abc123def456",
            "model_artifact_sha256": "a" * 64,
            "research_use_only": True,
            "features": {"alignment_score": 0.99},
            "explanation": {
                "available": True,
                "method": "Tree SHAP",
                "target_class": "hetero",
                "base_value": 0.4,
                "output_value": 0.88,
                "contributions": [
                    {
                        "feature": "alignment_score",
                        "value": 0.99,
                        "impact": 0.48,
                        "direction": "toward_hetero",
                    }
                ],
            },
            "limitations": "Research use only",
        }

    monkeypatch.setattr(model_predictions, "predict_ab1", fake_prediction)
    monkeypatch.setattr(
        model_predictions,
        "get_model_identity",
        lambda: {
            "model_name": "GeneGlass Random Forest",
            "model_version": "abc123def456",
            "model_artifact_sha256": "a" * 64,
        },
    )

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
            pending_response = client.get(
                f"/api/analyses/{analysis_id}/ai-prediction",
                headers=owner_headers,
            )
            qc_decision_response = client.post(
                f"/api/analyses/{analysis_id}/preliminary-qc-decision",
                headers=owner_headers,
                json={"decision": "continue_analysis"},
            )
            response = client.get(
                f"/api/analyses/{analysis_id}/ai-prediction",
                headers=owner_headers,
            )
            repeated_response = client.get(
                f"/api/analyses/{analysis_id}/ai-prediction",
                headers=owner_headers,
            )
            list_response = client.get("/api/analyses", headers=owner_headers)
            dashboard_response = client.get(
                "/api/dashboard/summary", headers=owner_headers
            )
            refresh_response = client.post(
                f"/api/analyses/{analysis_id}/ai-prediction/refresh",
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

        assert pending_response.status_code == 409
        assert "pending" in pending_response.json()["detail"].lower()
        assert qc_decision_response.status_code == 200
        assert qc_decision_response.json()["decision"] == "continue_analysis"
        assert response.status_code == 200
        payload = response.json()
        assert payload["analysis_id"] == analysis_id
        assert payload["prediction"] == "hetero"
        assert payload["probabilities"] == {"negative": 0.12, "hetero": 0.88}
        assert payload["research_use_only"] is True
        assert payload["model_version"] == "abc123def456"
        assert payload["explanation"]["method"] == "Tree SHAP"
        assert payload["explanation"]["output_value"] == 0.88
        assert repeated_response.json()["prediction_id"] == payload["prediction_id"]
        list_prediction = list_response.json()["items"][0]["ai_prediction"]
        assert list_prediction["prediction"] == "hetero"
        assert dashboard_response.json()["positive"] == 1
        assert dashboard_response.json()["recent_analyses"][0][
            "ai_prediction"
        ]["prediction"] == "hetero"
        assert refresh_response.status_code == 200
        assert refresh_response.json()["prediction_id"] != payload["prediction_id"]
        assert observed == {"file_path": str(ab1_path), "qc_passed": True}
        assert other_response.status_code == 404
        with sessions() as session:
            assert len(session.query(ModelPrediction).all()) == 2
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
