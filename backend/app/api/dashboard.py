
"""Dashboard summary endpoint."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.analysis import (
    Analysis,
    AnalysisStatus,
    QCStatus,
)
from app.models.user import User
from app.services.model_predictions import latest_prediction_map

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@dashboard_router.get("/summary")
def get_dashboard_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    """Return data-driven statistics for the signed-in user."""

    user_filter = Analysis.user_id == current_user.id

    total_analyses = session.scalar(
        select(func.count(Analysis.id)).where(user_filter)
    ) or 0

    owned_analyses = session.scalars(
        select(Analysis).where(user_filter)
    ).all()
    prediction_by_analysis = latest_prediction_map(
        session, (analysis.id for analysis in owned_analyses)
    )
    completed_analyses = sum(
        analysis.status == AnalysisStatus.COMPLETED
        for analysis in owned_analyses
    )
    positive = sum(
        prediction.prediction == "hetero"
        for prediction in prediction_by_analysis.values()
    )
    negative = sum(
        prediction.prediction == "negative"
        for prediction in prediction_by_analysis.values()
    )
    needs_review = sum(
        prediction.status == "Needs Review"
        for prediction in prediction_by_analysis.values()
    )
    awaiting_prediction = total_analyses - len(prediction_by_analysis)

    qc_passed = session.scalar(
        select(func.count(Analysis.id)).where(
            user_filter,
            Analysis.qc_status == QCStatus.PASSED,
        )
    ) or 0

    qc_evaluated = session.scalar(
        select(func.count(Analysis.id)).where(
            user_filter,
            Analysis.qc_status.in_(
                [QCStatus.PASSED, QCStatus.NEEDS_REVIEW, QCStatus.FAILED]
            ),
        )
    ) or 0

    qc_success_rate = (
        round(qc_passed / qc_evaluated * 100, 1)
        if qc_evaluated
        else 0.0
    )

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    activity_last_7_days = session.scalar(
        select(func.count(Analysis.id)).where(
            user_filter,
            Analysis.created_at >= seven_days_ago,
        )
    ) or 0

    gene_rows = session.execute(
        select(Analysis.gene, func.count(Analysis.id))
        .where(user_filter)
        .group_by(Analysis.gene)
    ).all()

    gene_distribution = {
        "JAK2": 0,
    }

    for gene, count in gene_rows:
        normalized_gene = (gene or "").strip().upper()
        if normalized_gene in gene_distribution:
            gene_distribution[normalized_gene] = count

    recent_rows = session.scalars(
        select(Analysis)
        .where(user_filter)
        .order_by(Analysis.created_at.desc())
        .limit(5)
    ).all()

    recent_prediction_by_analysis = latest_prediction_map(
        session, (analysis.id for analysis in recent_rows)
    )
    recent_analyses = []
    for analysis in recent_rows:
        prediction = recent_prediction_by_analysis.get(analysis.id)
        recent_analyses.append({
            "id": analysis.id,
            "file_name": analysis.original_file_name,
            "gene": analysis.gene,
            "target_variant": analysis.target_variant,
            "status": analysis.status.value,
            "qc_status": analysis.qc_status.value,
            "v617f_detected": analysis.v617f_detected,
            "ai_prediction": (
                {
                    "status": prediction.status,
                    "prediction": prediction.prediction,
                    "negative_probability": prediction.negative_probability,
                    "hetero_probability": prediction.hetero_probability,
                    "model_name": prediction.model_name,
                    "model_version": prediction.model_version,
                    "created_at": prediction.created_at.isoformat(),
                    "research_use_only": prediction.research_use_only,
                }
                if prediction
                else None
            ),
            "created_at": (
                analysis.created_at.isoformat()
                if analysis.created_at
                else None
            ),
        })

    return {
        "total_analyses": total_analyses,
        "completed_analyses": completed_analyses,
        "positive": positive,
        "negative": negative,
        "needs_review": needs_review,
        "awaiting_prediction": awaiting_prediction,
        "qc_success_rate": qc_success_rate,
        "activity_last_7_days": activity_last_7_days,
        "gene_distribution": gene_distribution,
        "recent_analyses": recent_analyses,
    }
