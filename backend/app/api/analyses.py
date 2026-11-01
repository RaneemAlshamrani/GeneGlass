
"""Analysis upload, history, and detail endpoints."""

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

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.analysis import Analysis, AnalysisStatus, QCStatus
from app.models.user import User
from app.schemas.analysis import AnalysisListItem, AnalysisListResponse
from app.services.ab1_reader import read_ab1_file
from app.services.sequence_cleaner import clean_sequence
from app.services.storage.ab1_storage import save_ab1_file

analyses_router = APIRouter(prefix="/analyses", tags=["analyses"])


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

    # These are preliminary project QC categories.
    # Final acceptance criteria should be confirmed by the project team.
    qc_status = (
        QCStatus.PASSED
        if quality_result["quality_assessment"] == "good"
        else QCStatus.NEEDS_REVIEW
    )

    analysis = Analysis(
        user_id=current_user.id,
        original_file_name=Path(file.filename or "").name,
        stored_file_path=str(stored_path),
        file_sha256=file_sha256,
        gene="JAK2",
        target_variant="V617F",
        status=AnalysisStatus.PENDING,
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
    )

    try:
        session.add(analysis)
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
        "message": "File uploaded and preliminary quality control completed. Variant detection is pending.",
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

    if result == "mutation":
        filters.extend(
            [
                Analysis.gene == "JAK2",
                Analysis.status == AnalysisStatus.COMPLETED,
                Analysis.v617f_detected.is_(True),
            ]
        )
    elif result == "normal":
        filters.extend(
            [
                Analysis.gene == "JAK2",
                Analysis.status == AnalysisStatus.COMPLETED,
                Analysis.v617f_detected.is_(False),
            ]
        )
    elif result == "review":
        filters.append(Analysis.qc_status == QCStatus.NEEDS_REVIEW)
    elif result == "pending":
        filters.append(
            or_(
                Analysis.status.in_(
                    [AnalysisStatus.PENDING, AnalysisStatus.PROCESSING]
                ),
                Analysis.qc_status == QCStatus.PENDING,
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

    items = [
        AnalysisListItem.model_validate(analysis)
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

    analysis = session.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id,
        )
    )

    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

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


# chromatogram-viewer-v1
@analyses_router.get("/{analysis_id}/chromatogram")
def get_analysis_chromatogram(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    """Return original trace data only for the owner of this analysis."""
    from app.services.ab1_reader import read_chromatogram

    analysis = session.scalar(select(Analysis).where(
        Analysis.id == analysis_id, Analysis.user_id == current_user.id
    ))
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    try:
        return read_chromatogram(analysis.stored_file_path)
    except (ValueError, OSError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail="Chromatogram unavailable for this AB1 file") from exc
