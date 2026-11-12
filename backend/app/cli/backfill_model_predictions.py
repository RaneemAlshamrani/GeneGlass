"""Record the current model output for analyses created before persistence."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.db.init_db import initialize_database
from app.db.session import SessionLocal
from app.models.analysis import Analysis, AnalysisStatus
from app.services.audit import AuditAction, add_audit_event
from app.services.model_predictions import get_or_record_current_prediction


def main() -> None:
    initialize_database()
    created_count = 0
    reused_count = 0

    with SessionLocal() as session:
        analyses = session.scalars(
            select(Analysis)
            .where(Analysis.stored_file_path.is_not(None))
            .order_by(Analysis.id)
        ).all()

        for analysis in analyses:
            record, created = get_or_record_current_prediction(
                session, analysis
            )
            if created:
                if analysis.status in {
                    AnalysisStatus.PENDING,
                    AnalysisStatus.PROCESSING,
                }:
                    analysis.status = AnalysisStatus.COMPLETED
                add_audit_event(
                    session,
                    actor_id=analysis.user_id,
                    analysis_id=analysis.id,
                    action=AuditAction.AI_PREDICTION_CREATED,
                    details={
                        "prediction_id": record.id,
                        "status": record.status,
                        "prediction": record.prediction,
                        "model_version": record.model_version,
                        "research_use_only": True,
                        "backfill": True,
                    },
                )
                created_count += 1
            else:
                reused_count += 1
            if (
                analysis.status == AnalysisStatus.COMPLETED
                and analysis.completed_at is None
            ):
                analysis.completed_at = datetime.now(UTC)

        session.commit()

    print(
        "Model prediction backfill complete: "
        f"created={created_count}, reused={reused_count}."
    )


if __name__ == "__main__":
    main()
