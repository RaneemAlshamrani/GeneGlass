"""Persistence helpers for versioned, research-only model outputs."""

from __future__ import annotations

import json
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.analysis import Analysis
from app.models.model_prediction import ModelPrediction
from app.services.ai_predictor import get_model_identity, predict_ab1


def serialize_prediction(record: ModelPrediction) -> dict:
    probabilities = None
    if (
        record.negative_probability is not None
        or record.hetero_probability is not None
    ):
        probabilities = {
            "negative": record.negative_probability,
            "hetero": record.hetero_probability,
        }

    features = None
    if record.features_json:
        try:
            features = json.loads(record.features_json)
        except json.JSONDecodeError:
            features = None

    return {
        "prediction_id": record.id,
        "analysis_id": record.analysis_id,
        "status": record.status,
        "prediction": record.prediction,
        "probabilities": probabilities,
        "reason": record.reason,
        "orientation": record.orientation,
        "features": features,
        "model_name": record.model_name,
        "model_version": record.model_version,
        "model_artifact_sha256": record.model_artifact_sha256,
        "research_use_only": record.research_use_only,
        "limitations": record.limitations,
        "created_at": record.created_at.isoformat(),
    }


def latest_prediction(
    session: Session,
    analysis_id: int,
) -> ModelPrediction | None:
    return session.scalar(
        select(ModelPrediction)
        .where(ModelPrediction.analysis_id == analysis_id)
        .order_by(ModelPrediction.id.desc())
        .limit(1)
    )


def latest_prediction_map(
    session: Session,
    analysis_ids: Iterable[int],
) -> dict[int, ModelPrediction]:
    ids = list(analysis_ids)
    if not ids:
        return {}

    latest_ids = (
        select(func.max(ModelPrediction.id))
        .where(ModelPrediction.analysis_id.in_(ids))
        .group_by(ModelPrediction.analysis_id)
    )
    records = session.scalars(
        select(ModelPrediction).where(ModelPrediction.id.in_(latest_ids))
    ).all()
    return {record.analysis_id: record for record in records}


def record_prediction(
    session: Session,
    analysis: Analysis,
) -> ModelPrediction:
    """Run the model and add one immutable result to the transaction."""

    result = predict_ab1(
        analysis.stored_file_path or "",
        qc_passed=(analysis.qc_status.value == "passed"),
    )
    probabilities = result.get("probabilities") or {}
    features = result.get("features")
    record = ModelPrediction(
        analysis_id=analysis.id,
        status=result["status"],
        prediction=result.get("prediction"),
        negative_probability=probabilities.get("negative"),
        hetero_probability=probabilities.get("hetero"),
        reason=result.get("reason"),
        orientation=result.get("orientation"),
        features_json=(
            json.dumps(features, ensure_ascii=True, separators=(",", ":"))
            if features is not None
            else None
        ),
        model_name=result["model_name"],
        model_version=result["model_version"],
        model_artifact_sha256=result["model_artifact_sha256"],
        input_qc_status=analysis.qc_status.value,
        limitations=result.get("limitations"),
        research_use_only=True,
    )
    session.add(record)
    session.flush()
    return record


def get_or_record_current_prediction(
    session: Session,
    analysis: Analysis,
) -> tuple[ModelPrediction, bool]:
    """Reuse the current artifact/QC result or append a new model run."""

    current = get_model_identity()
    latest = latest_prediction(session, analysis.id)
    if (
        latest is not None
        and latest.model_artifact_sha256 == current["model_artifact_sha256"]
        and latest.model_version == current["model_version"]
        and latest.input_qc_status == analysis.qc_status.value
    ):
        return latest, False
    return record_prediction(session, analysis), True
