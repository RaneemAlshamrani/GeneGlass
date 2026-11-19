
"""Analysis upload, history, and detail endpoints."""

import json
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.analysis_access import get_owned_analysis
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.analysis import Analysis, AnalysisStatus, QCStatus
from app.models.model_prediction import ModelPrediction
from app.models.molecular_report import MolecularReport
from app.models.review import Review, ReviewDecision
from app.models.preliminary_qc_decision import PreliminaryQCDecision, QCDecision
from pydantic import BaseModel, Field
from app.models.user import User
from app.schemas.analysis import AnalysisListItem, AnalysisListResponse
from app.services.ab1_reader import read_ab1_file
from app.services.ab1_reader import read_chromatogram
from app.services.audit import AuditAction, add_audit_event
from app.services.sequence_cleaner import clean_sequence
from app.services.storage.ab1_storage import UPLOAD_ROOT, delete_owned_ab1_file, save_ab1_file
from app.services.model_predictions import (
    get_or_record_current_prediction,
    latest_prediction_map,
    prediction_summary,
    record_prediction,
    serialize_prediction,
)
from app.services.variant_detector import (
    JAK2_PIPELINE_VERSION,
    analyze_jak2_chromatogram,
)

analyses_router = APIRouter(prefix="/analyses", tags=["analyses"])


def _analysis_list_item(
    analysis: Analysis,
    prediction: ModelPrediction | None,
    report: dict,
) -> AnalysisListItem:
    return AnalysisListItem.model_validate(
        {
            "id": analysis.id,
            "original_file_name": analysis.original_file_name,
            "gene": analysis.gene,
            "target_variant": analysis.target_variant,
            "status": analysis.status.value,
            "qc_status": analysis.qc_status.value,
            "v617f_detected": analysis.v617f_detected,
            "ai_prediction": prediction_summary(prediction),
            "report": report,
            "created_at": analysis.created_at,
        }
    )


def _report_summary_map(
    session: Session,
    analysis_ids,
) -> dict[int, dict]:
    ids = list(analysis_ids)
    if not ids:
        return {}

    latest_decisions: dict[int, ReviewDecision] = {}
    for review in session.scalars(
        select(Review)
        .where(Review.analysis_id.in_(ids))
        .order_by(Review.analysis_id, Review.created_at.desc(), Review.id.desc())
    ):
        latest_decisions.setdefault(review.analysis_id, review.decision)

    finalized_reports: dict[int, MolecularReport] = {}
    for report in session.scalars(
        select(MolecularReport)
        .where(
            MolecularReport.analysis_id.in_(ids),
            MolecularReport.status == "finalized",
        )
        .order_by(MolecularReport.analysis_id, MolecularReport.version.desc())
    ):
        finalized_reports.setdefault(report.analysis_id, report)

    summaries: dict[int, dict] = {}
    for analysis_id in ids:
        decision = latest_decisions.get(analysis_id)
        finalized = finalized_reports.get(analysis_id)
        decision_is_final = decision in {
            ReviewDecision.NOT_DETECTED,
            ReviewDecision.HETEROZYGOUS,
            ReviewDecision.HOMOZYGOUS,
            ReviewDecision.INCONCLUSIVE,
        }
        if (
            finalized is not None
            and decision_is_final
            and finalized.final_decision == decision.value
        ):
            summaries[analysis_id] = {
                "status": "finalized",
                "decision": finalized.final_decision,
                "version": finalized.version,
                "download_url": (
                    f"/api/analyses/{analysis_id}/report.pdf"
                    f"?version={finalized.version}"
                ),
            }
        elif finalized is not None and decision_is_final:
            summaries[analysis_id] = {
                "status": "needs_update",
                "decision": decision.value,
                "version": finalized.version,
                "download_url": (
                    f"/api/analyses/{analysis_id}/report.pdf"
                    f"?version={finalized.version}"
                ),
            }
        elif decision_is_final:
            summaries[analysis_id] = {
                "status": "ready_to_create",
                "decision": decision.value,
                "version": None,
                "download_url": None,
            }
        else:
            summaries[analysis_id] = {
                "status": "awaiting_decision",
                "decision": decision.value if decision else None,
                "version": None,
                "download_url": None,
            }
    return summaries


@analyses_router.post("", status_code=status.HTTP_201_CREATED)
async def upload_analysis(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
) -> dict:
    """Upload an AB1 file, perform preliminary QC, and save its metrics."""

    stored_path, file_sha256 = await save_ab1_file(
        upload=file,
        user_id=current_user.id,
    )

    existing_analysis = session.scalar(
        select(Analysis).where(
            Analysis.user_id == current_user.id,
            Analysis.file_sha256 == file_sha256,
        )
    )
    if existing_analysis is not None:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This AB1 file was already uploaded as analysis "
                f"#{existing_analysis.id}."
            ),
        )

    try:
        sequencing_data = read_ab1_file(stored_path)

        quality_result = clean_sequence(
            sequencing_data["sequence"],
            sequencing_data["quality_scores"],
        )

    except (ValueError, FileNotFoundError, OSError) as exc:
        stored_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The AB1 file could not be read or processed.",
        ) from exc

    try:
        preliminary_result = analyze_jak2_chromatogram(
            read_chromatogram(stored_path)
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        preliminary_result = {
            "found": False,
            "needs_review": True,
            "review_status": "Needs Review",
            "review_reasons": [
                "JAK2 target evidence could not be generated from this AB1 file."
            ],
            "error": type(exc).__name__,
        }

    # Preliminary QC only. Mutation classification remains unset until the
    # project has validated decision rules and labelled reference samples.
    qc_status = (
        QCStatus.PASSED
        if quality_result["quality_assessment"] == "good"
        and not preliminary_result.get("needs_review", True)
        else QCStatus.NEEDS_REVIEW
    )

    analysis = Analysis(
        user_id=current_user.id,
        original_file_name=Path(file.filename or "").name,
        stored_file_path=str(stored_path),
        file_sha256=file_sha256,
        gene="JAK2",
        target_variant="V617F",
        status=AnalysisStatus.PROCESSING,
        qc_status=qc_status,
        sequence_length=quality_result["original_length"],
        cleaned_sequence_length=quality_result["cleaned_length"],
        average_quality=quality_result["average_quality"],
        minimum_quality=quality_result["minimum_quality"],
        maximum_quality=quality_result["maximum_quality"],
        low_quality_count=quality_result["low_quality_count"],
        low_quality_percentage=quality_result["low_quality_percentage"],
        retained_percentage=quality_result["retained_percentage"],
        quality_assessment=quality_result["quality_assessment"],
        preliminary_result_json=json.dumps(
            preliminary_result,
            ensure_ascii=True,
            separators=(",", ":"),
        ),
        result_summary=(
            "Preliminary JAK2 target evidence generated. No mutation "
            "classification has been made."
        ),
    )

    try:
        session.add(analysis)
        session.flush()
        add_audit_event(
            session,
            actor_id=current_user.id,
            analysis_id=analysis.id,
            action=AuditAction.ANALYSIS_UPLOADED,
            details={
                "gene": analysis.gene,
                "target_variant": analysis.target_variant,
                "qc_status": analysis.qc_status.value,
            },
        )
        analysis.status = AnalysisStatus.COMPLETED
        analysis.completed_at = datetime.now(UTC)
        session.commit()
        session.refresh(analysis)

    except SQLAlchemyError as exc:
        session.rollback()
        stored_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The analysis record could not be saved.",
        ) from exc

    return {
        "id": analysis.id,
        "file_name": analysis.original_file_name,
        "gene": analysis.gene,
        "target_variant": analysis.target_variant,
        "status": analysis.status.value,
        "qc_status": analysis.qc_status.value,
        "file_sha256": analysis.file_sha256,
        "quality_control": {
            "sequence_length": analysis.sequence_length,
            "cleaned_sequence_length": analysis.cleaned_sequence_length,
            "average_quality": analysis.average_quality,
            "minimum_quality": analysis.minimum_quality,
            "maximum_quality": analysis.maximum_quality,
            "low_quality_count": analysis.low_quality_count,
            "low_quality_percentage": analysis.low_quality_percentage,
            "retained_percentage": analysis.retained_percentage,
            "quality_assessment": analysis.quality_assessment,
        },
        "preliminary_target_analysis": preliminary_result,
        "ai_prediction": None,
        "message": (
            "File uploaded and preliminary QC generated. "
            "Awaiting specialist QC decision before AI prediction."
        ),
    }


@analyses_router.get("", response_model=AnalysisListResponse)
def get_analyses(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    search: str | None = None,
    result: Annotated[
        str,
        Query(pattern="^(all|mutation|normal|review|pending)$"),
    ] = "all",
    qc_status: str | None = None,
) -> AnalysisListResponse:
    """Return the signed-in user's analyses with search and filters."""

    filters = [Analysis.user_id == current_user.id]

    if search and search.strip():
        search_term = f"%{search.strip().lower()}%"
        filters.append(
            or_(
                func.lower(Analysis.original_file_name).like(search_term),
                func.lower(Analysis.gene).like(search_term),
            )
        )

    latest_prediction_ids = (
        select(func.max(ModelPrediction.id))
        .group_by(ModelPrediction.analysis_id)
    )
    latest_predictions = select(ModelPrediction.analysis_id).where(
        ModelPrediction.id.in_(latest_prediction_ids)
    )

    if result == "mutation":
        filters.append(
            Analysis.id.in_(
                latest_predictions.where(
                    ModelPrediction.prediction == "hetero"
                )
            )
        )
    elif result == "normal":
        filters.append(
            Analysis.id.in_(
                latest_predictions.where(
                    ModelPrediction.prediction == "negative"
                )
            )
        )
    elif result == "review":
        filters.append(
            or_(
                Analysis.qc_status == QCStatus.NEEDS_REVIEW,
                Analysis.id.in_(
                    latest_predictions.where(
                        ModelPrediction.status == "Needs Review"
                    )
                ),
            )
        )
    elif result == "pending":
        filters.append(
            or_(
                Analysis.status.in_(
                    [AnalysisStatus.PENDING, AnalysisStatus.PROCESSING]
                ),
                Analysis.qc_status == QCStatus.PENDING,
                Analysis.id.not_in(latest_predictions),
            )
        )

    if qc_status:
        valid_qc_statuses = {item.value for item in QCStatus}
        if qc_status not in valid_qc_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid QC status",
            )

        filters.append(Analysis.qc_status == QCStatus(qc_status))

    total = session.scalar(
        select(func.count(Analysis.id)).where(*filters)
    ) or 0

    analyses = session.scalars(
        select(Analysis)
        .where(*filters)
        .order_by(Analysis.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    prediction_by_analysis = latest_prediction_map(
        session, (analysis.id for analysis in analyses)
    )
    report_by_analysis = _report_summary_map(
        session, (analysis.id for analysis in analyses)
    )
    items = [
        _analysis_list_item(
            analysis,
            prediction_by_analysis.get(analysis.id),
            report_by_analysis[analysis.id],
        )
        for analysis in analyses
    ]

    return AnalysisListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@analyses_router.get("/{analysis_id}")
def get_analysis_details(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    """Return one analysis only if it belongs to the signed-in user."""

    analysis = get_owned_analysis(session, analysis_id, current_user.id)

    report_summary = _report_summary_map(session, [analysis.id])[analysis.id]

    return {
        "id": analysis.id,
        "original_file_name": analysis.original_file_name,
        "gene": analysis.gene,
        "target_variant": analysis.target_variant,
        "status": analysis.status.value,
        "qc_status": analysis.qc_status.value,
        "quality_control": {
            "sequence_length": analysis.sequence_length,
            "cleaned_sequence_length": analysis.cleaned_sequence_length,
            "average_quality": analysis.average_quality,
            "minimum_quality": analysis.minimum_quality,
            "maximum_quality": analysis.maximum_quality,
            "low_quality_count": analysis.low_quality_count,
            "low_quality_percentage": analysis.low_quality_percentage,
            "retained_percentage": analysis.retained_percentage,
            "quality_assessment": analysis.quality_assessment,
        },
        "v617f_detected": analysis.v617f_detected,
        "ai_prediction": prediction_summary(
            latest_prediction_map(session, [analysis.id]).get(analysis.id)
        ),
        "report": report_summary,
        "result_summary": analysis.result_summary,
        "error_message": analysis.error_message,
        "created_at": analysis.created_at.isoformat(),
        "updated_at": analysis.updated_at.isoformat(),
        "completed_at": (
            analysis.completed_at.isoformat()
            if analysis.completed_at
            else None
        ),
    }


def _remove_owned_upload_files(paths: set[str], user_id: int) -> None:
    """Delete only managed AB1 files owned by the current user."""
    for raw_path in paths:
        delete_owned_ab1_file(raw_path, user_id)

    owned_root = (UPLOAD_ROOT / f"user_{user_id}").resolve()
    try:
        owned_root.rmdir()
    except OSError:
        pass

@analyses_router.delete("/{analysis_id}")
def delete_analysis(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, int | str]:
    """Delete one owned analysis and its managed AB1/report files."""

    analysis = get_owned_analysis(session, analysis_id, current_user.id)

    reports = session.scalars(
        select(MolecularReport).where(
            MolecularReport.analysis_id == analysis.id
        )
    ).all()
    managed_paths = {
        path
        for path in [
            analysis.stored_file_path,
            *(report.normal_control_file_path for report in reports),
        ]
        if path
    }
    add_audit_event(
        session,
        actor_id=current_user.id,
        analysis_id=analysis.id,
        action=AuditAction.ANALYSIS_DELETED,
        details={
            "deleted_analysis_id": analysis.id,
            "report_count": len(reports),
        },
    )
    try:
        session.delete(analysis)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The analysis could not be deleted",
        ) from exc

    _remove_owned_upload_files(managed_paths, current_user.id)
    return {"id": analysis_id, "status": "deleted"}


# chromatogram-viewer-v1
@analyses_router.get("/{analysis_id}/chromatogram")
def get_analysis_chromatogram(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    """Return original trace data only for the owner of this analysis."""
    from app.services.ab1_reader import read_chromatogram

    analysis = get_owned_analysis(session, analysis_id, current_user.id)
    try:
        return read_chromatogram(analysis.stored_file_path)
    except (ValueError, OSError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail="Chromatogram unavailable for this AB1 file") from exc

@analyses_router.get("/{analysis_id}/jak2-target")
def get_jak2_target_analysis(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    """Return preliminary JAK2 target and peak analysis."""

    analysis = get_owned_analysis(session, analysis_id, current_user.id)

    if analysis.gene != "JAK2":
        raise HTTPException(
            status_code=400,
            detail="This endpoint supports JAK2 only.",
        )

    if analysis.preliminary_result_json:
        try:
            result = json.loads(analysis.preliminary_result_json)
        except json.JSONDecodeError:
            result = None
    else:
        result = None

    try:
        cache_is_current = (
            isinstance(result, dict)
            and result.get("pipeline_version") == JAK2_PIPELINE_VERSION
        )
        if not cache_is_current:
            data = read_chromatogram(analysis.stored_file_path)
            result = analyze_jak2_chromatogram(data)
            analysis.preliminary_result_json = json.dumps(
                result,
                ensure_ascii=True,
                separators=(",", ":"),
            )
            analysis.qc_status = (
                QCStatus.PASSED
                if analysis.quality_assessment == "good"
                and not result.get("needs_review", True)
                else QCStatus.NEEDS_REVIEW
            )
            add_audit_event(
                session,
                actor_id=current_user.id,
                analysis_id=analysis.id,
                action=AuditAction.ANALYSIS_RECALCULATED,
                details={"pipeline_version": JAK2_PIPELINE_VERSION},
            )
            session.commit()

    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(
            status_code=422,
            detail="JAK2 target analysis unavailable.",
        ) from exc

    # NOISE_NOTICE_V1: read-only, descriptive measurements for pre-existing analyses.
    # These values DO NOT alter AI predictions, review status, or saved QC.
    if isinstance(result, dict) and result.get("found") and "noise_assessment" not in result:
        try:
            trace_for_noise = read_chromatogram(analysis.stored_file_path)
            from app.services.noise_assessment import assess_target_noise
            result = {**result, "noise_assessment": assess_target_noise(
                base_index=int(result["ab1_base_index"]),
                sequence=trace_for_noise["sequence"],
                quality_scores=trace_for_noise["quality_scores"],
                base_positions=trace_for_noise["base_positions"],
                channels=trace_for_noise["channels"],
            )}
        except (KeyError, ValueError, IndexError, TypeError, OSError):
            result = {**result, "noise_assessment": {
                "available": False,
                "reason": "Signal measurements could not be calculated for this saved analysis.",
            }}

    # UNSUPPORTED_SAVED_ADVISORY_V1: add display-only evidence to cached analyses.
    # The pipeline version is unchanged: do NOT rewrite stored evidence or QC state.
    if isinstance(result, dict) and result.get("found") and "unsupported_target_pattern" not in result:
        from app.services.unsupported_target_pattern import assess_unsupported_target_pattern
        try:
            result = {**result, "unsupported_target_pattern": assess_unsupported_target_pattern(
                target=result, peaks=result.get("peak_analysis") or {},
            )}
        except (KeyError, TypeError, ValueError, OverflowError):
            result = {**result, "unsupported_target_pattern": {
                "available": False,
                "review_recommended": False,
                "status": "Unassessed",
                "reason": "Saved target peak evidence is insufficient for this advisory.",
            }}

    return {
        "analysis_id": analysis.id,
        "gene": analysis.gene,
        "target_variant": analysis.target_variant,
        "analysis_type": "preliminary",
        "result": result,
    }

def _require_ai_target_and_file(analysis: Analysis) -> None:
    """Check the JAK2 V617F target and availability of the AB1 file path."""
    if analysis.gene != "JAK2" or analysis.target_variant != "V617F":
        raise HTTPException(
            status_code=400,
            detail="AI prediction supports JAK2 V617F only",
        )
    if not analysis.stored_file_path:
        raise HTTPException(status_code=422, detail="AB1 file path unavailable")


@analyses_router.get("/{analysis_id}/ai-prediction")
def get_ai_prediction(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    """Return a research-only AI prediction for an existing AB1 analysis."""

    analysis = get_owned_analysis(session, analysis_id, current_user.id)

    _require_ai_target_and_file(analysis)

    # Show an existing historical result without recalculating it.
    # New uploads have no prediction until specialist QC approval.
    previous = require_preliminary_qc_approval(session, analysis, allow_saved_legacy=True)
    if previous is not None and previous.explanation_json is not None:
        return serialize_prediction(previous)
    record, created = get_or_record_current_prediction(session, analysis)
    if created:
        add_audit_event(
            session,
            actor_id=current_user.id,
            analysis_id=analysis.id,
            action=AuditAction.AI_PREDICTION_CREATED,
            details={
                "prediction_id": record.id,
                "status": record.status,
                "prediction": record.prediction,
                "model_version": record.model_version,
                "research_use_only": True,
                "shap_upgrade": previous is not None,
            },
        )
        session.commit()
        session.refresh(record)
    return serialize_prediction(record)


@analyses_router.post("/{analysis_id}/ai-prediction/refresh")
def refresh_ai_prediction(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    """Append a new research-only model run without replacing history."""

    analysis = get_owned_analysis(session, analysis_id, current_user.id)
    _require_ai_target_and_file(analysis)

    require_preliminary_qc_approval(session, analysis)
    record = record_prediction(session, analysis)
    add_audit_event(
        session,
        actor_id=current_user.id,
        analysis_id=analysis.id,
        action=AuditAction.AI_PREDICTION_CREATED,
        details={
            "prediction_id": record.id,
            "status": record.status,
            "prediction": record.prediction,
            "model_version": record.model_version,
            "research_use_only": True,
            "refresh": True,
        },
    )
    session.commit()
    session.refresh(record)
    return serialize_prediction(record)

# Preliminary specialist QC approval is independent from AI result review.
class PreliminaryQCDecisionInput(BaseModel):
    decision: QCDecision
    comment: str | None = Field(default=None, max_length=2000)


def get_latest_preliminary_qc_decision(
    session: Session, analysis_id: int,
) -> PreliminaryQCDecision | None:
    return session.scalar(
        select(PreliminaryQCDecision)
        .where(PreliminaryQCDecision.analysis_id == analysis_id)
        .order_by(PreliminaryQCDecision.id.desc())
        .limit(1)
    )


def _qc_target_found(analysis: Analysis) -> bool:
    try:
        preliminary = json.loads(analysis.preliminary_result_json or "{}")
    except (ValueError, TypeError):
        return False
    return isinstance(preliminary, dict) and preliminary.get("found") is True


def require_preliminary_qc_approval(
    session: Session,
    analysis: Analysis,
    *,
    allow_saved_legacy: bool = False,
) -> ModelPrediction | None:
    if not _qc_target_found(analysis):
        raise HTTPException(
            status_code=409, detail="Target Not Found. AI prediction unavailable."
        )
    decision = get_latest_preliminary_qc_decision(session, analysis.id)
    if decision is None:
        if allow_saved_legacy:
            existing = session.scalar(
                select(ModelPrediction)
                .where(ModelPrediction.analysis_id == analysis.id)
                .order_by(ModelPrediction.id.desc())
                .limit(1)
            )
            if existing is not None:
                return existing  # Read-only access; no new inference.
        raise HTTPException(
            status_code=409, detail="Initial QC review is pending."
        )
    if decision.decision != QCDecision.CONTINUE_ANALYSIS:
        raise HTTPException(
            status_code=409, detail="Request Repeat selected. AI prediction blocked."
        )
    return None


@analyses_router.get("/{analysis_id}/preliminary-qc-decision")
def get_preliminary_qc_decision(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    analysis = get_owned_analysis(session, analysis_id, current_user.id)
    latest = get_latest_preliminary_qc_decision(session, analysis.id)
    return {
        "analysis_id": analysis.id,
        "target_found": _qc_target_found(analysis),
        "preliminary_qc_status": analysis.qc_status.value,
        "decision": latest.decision.value if latest else "pending",
        "comment": latest.comment if latest else None,
        "decided_at": latest.created_at.isoformat() if latest else None,
    }


@analyses_router.post("/{analysis_id}/preliminary-qc-decision")
def save_preliminary_qc_decision(
    analysis_id: int,
    payload: PreliminaryQCDecisionInput,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    analysis = get_owned_analysis(session, analysis_id, current_user.id)
    if payload.decision == QCDecision.CONTINUE_ANALYSIS and not _qc_target_found(analysis):
        raise HTTPException(
            status_code=409, detail="Target Not Found. AI analysis cannot continue."
        )
    comment = (payload.comment or "").strip()
    if (
        payload.decision == QCDecision.REQUEST_REPEAT
        or (
            payload.decision == QCDecision.CONTINUE_ANALYSIS
            and analysis.qc_status != QCStatus.PASSED
        )
    ) and not comment:
        raise HTTPException(
            status_code=422, detail="A reason is required for this QC decision."
        )
    record = PreliminaryQCDecision(
        analysis_id=analysis.id,
        reviewer_id=current_user.id,
        decision=payload.decision,
        comment=comment or None,
    )
    session.add(record)
    session.flush()
    add_audit_event(
        session,
        actor_id=current_user.id,
        analysis_id=analysis.id,
        action=AuditAction.QC_DECISION_RECORDED,
        details={
            "decision_id": record.id,
            "decision": record.decision.value,
            "qc_status_at_decision": analysis.qc_status.value,
            "reason_provided": bool(comment),
        },
    )
    session.commit()
    session.refresh(record)
    return {
        "id": record.id,
        "analysis_id": record.analysis_id,
        "decision": record.decision.value,
        "comment": record.comment,
        "created_at": record.created_at.isoformat(),
    }
