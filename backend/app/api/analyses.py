
"""Analysis upload, history, and detail endpoints."""

import json
from datetime import UTC, datetime, timedelta
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
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.core.config import get_settings
from app.models.analysis import Analysis, AnalysisStatus, QCStatus
from app.models.research_variant import CandidateVariant, ExternalAnnotation
from app.models.user import User
from app.schemas.analysis import AnalysisListItem, AnalysisListResponse
from app.services.ab1_reader import read_ab1_file
from app.services.ab1_reader import read_chromatogram
from app.services.sequence_cleaner import clean_sequence
from app.services.storage.ab1_storage import save_ab1_file
from app.services.clinvar import CLINVAR_SOURCE, ClinVarClient, ClinVarServiceError
from app.services.variant_detector import (
    analyze_jak2_chromatogram,
    extract_jak2_candidate_snvs,
)

analyses_router = APIRouter(prefix="/analyses", tags=["analyses"])
MAX_CLINVAR_LOOKUPS_PER_ANALYSIS = 20


def _serialize_external_annotation(annotation: ExternalAnnotation) -> dict:
    def parse_json(value: str | None, fallback: list) -> list:
        if not value:
            return fallback
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return fallback
        return parsed if isinstance(parsed, list) else fallback

    return {
        "source": annotation.source,
        "lookup_status": annotation.lookup_status,
        "source_record_id": annotation.source_record_id,
        "accession": annotation.accession,
        "accession_version": annotation.accession_version,
        "title": annotation.title,
        "variant_type": annotation.variant_type,
        "canonical_spdi": annotation.canonical_spdi,
        "classifications": parse_json(annotation.classifications_json, []),
        "conditions": parse_json(annotation.conditions_json, []),
        "review_status": annotation.review_status,
        "source_url": annotation.source_url,
        "fetched_at": annotation.fetched_at.isoformat(),
    }


def _serialize_candidate(candidate: CandidateVariant) -> dict:
    complement = str.maketrans("ACGT", "TGCA")
    if candidate.direction == "Reverse":
        raw_reference_allele = candidate.reference_allele.translate(complement)
        raw_observed_allele = candidate.observed_allele.translate(complement)
    else:
        raw_reference_allele = candidate.reference_allele
        raw_observed_allele = candidate.observed_allele

    return {
        "id": candidate.id,
        "reference_accession": candidate.reference_accession,
        "transcript_position": candidate.transcript_position,
        "coding_position": candidate.coding_position,
        "reference_allele": candidate.reference_allele,
        "observed_allele": candidate.observed_allele,
        "reference_oriented_change": (
            f"{candidate.reference_allele}>{candidate.observed_allele}"
        ),
        "raw_ab1_reference_allele": raw_reference_allele,
        "raw_ab1_observed_allele": raw_observed_allele,
        "raw_ab1_change": f"{raw_reference_allele}>{raw_observed_allele}",
        "hgvs": candidate.hgvs,
        "ab1_base_number": candidate.ab1_base_number,
        "direction": candidate.direction,
        "phred_quality": candidate.phred_quality,
        "review_status": candidate.review_status,
        "lookup_eligible": candidate.lookup_eligible,
        "external_annotations": [
            _serialize_external_annotation(annotation)
            for annotation in candidate.external_annotations
        ],
    }


def _research_response(analysis: Analysis) -> dict:
    screened_candidates = sorted(
        analysis.candidate_variants,
        key=lambda item: (item.transcript_position, item.id),
    )
    matched_candidates = [
        candidate for candidate in screened_candidates
        if any(
            annotation.source == CLINVAR_SOURCE
            and annotation.lookup_status == "matched"
            and annotation.source_record_id
            for annotation in candidate.external_annotations
        )
    ]
    return {
        "analysis_id": analysis.id,
        "gene": analysis.gene,
        "scope": "Aligned JAK2 bases covered by this AB1 read only",
        "research_use_only": True,
        "external_lookup_limit": MAX_CLINVAR_LOOKUPS_PER_ANALYSIS,
        "limitations": [
            "Base-call SNV candidates only; indels and mixed secondary peaks are not called.",
            "A ClinVar match is an external research annotation, not a diagnosis.",
            "No ClinVar match must not be interpreted as benign.",
            "Candidates without an exact ClinVar match are withheld from displayed external results.",
        ],
        "screened_candidate_count": len(screened_candidates),
        "candidate_count": len(matched_candidates),
        "candidates": [
            _serialize_candidate(item) for item in matched_candidates
        ],
    }


def _sync_research_candidates(
    session: Session,
    analysis: Analysis,
    extracted: list[dict],
) -> None:
    existing = {item.hgvs: item for item in analysis.candidate_variants}
    current_hgvs = {item["hgvs"] for item in extracted}

    stale_ids = [
        item.id for hgvs, item in existing.items() if hgvs not in current_hgvs
    ]
    if stale_ids:
        session.execute(
            delete(CandidateVariant).where(CandidateVariant.id.in_(stale_ids))
        )

    for item in extracted:
        candidate = existing.get(item["hgvs"])
        if candidate is None:
            candidate = CandidateVariant(analysis_id=analysis.id, **{
                key: item[key]
                for key in (
                    "reference_accession",
                    "transcript_position",
                    "coding_position",
                    "reference_allele",
                    "observed_allele",
                    "hgvs",
                    "ab1_base_number",
                    "direction",
                    "phred_quality",
                    "review_status",
                    "lookup_eligible",
                )
            })
            session.add(candidate)
        else:
            for key in (
                "transcript_position",
                "coding_position",
                "reference_allele",
                "observed_allele",
                "ab1_base_number",
                "direction",
                "phred_quality",
                "review_status",
                "lookup_eligible",
            ):
                setattr(candidate, key, item[key])

    session.commit()
    session.refresh(analysis)


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
        "message": (
            "File uploaded and preliminary evidence generated. Mutation "
            "classification remains pending validation."
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


@analyses_router.get("/{analysis_id}/research-variants")
def get_research_variants(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    """Return saved research candidates and cached annotations."""

    analysis = session.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id,
        )
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return _research_response(analysis)


@analyses_router.post("/{analysis_id}/research-variants/refresh")
def refresh_research_variants(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    force_external_refresh: bool = False,
) -> dict:
    """Extract JAK2 SNV candidates and annotate eligible HGVS via ClinVar."""

    analysis = session.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id,
        )
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.gene != "JAK2":
        raise HTTPException(status_code=400, detail="Research screening supports JAK2 only")

    try:
        trace = read_chromatogram(analysis.stored_file_path)
        extracted = extract_jak2_candidate_snvs(trace)
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Research candidates could not be extracted from this AB1 file",
        ) from exc

    _sync_research_candidates(session, analysis, extracted)
    session.expire(analysis, ["candidate_variants"])
    candidates = list(analysis.candidate_variants)
    settings = get_settings()
    utc_now = datetime.now(UTC).replace(tzinfo=None)
    cache_cutoff = utc_now - timedelta(
        hours=settings.clinvar_cache_hours
    )
    lookup_candidates = [item for item in candidates if item.lookup_eligible]
    lookup_candidates.sort(
        key=lambda item: item.phred_quality or 0,
        reverse=True,
    )
    lookup_candidates = lookup_candidates[:MAX_CLINVAR_LOOKUPS_PER_ANALYSIS]

    try:
        with ClinVarClient(settings) as clinvar:
            for candidate in lookup_candidates:
                annotation = session.scalar(
                    select(ExternalAnnotation).where(
                        ExternalAnnotation.candidate_variant_id == candidate.id,
                        ExternalAnnotation.source == CLINVAR_SOURCE,
                    )
                )
                if (
                    annotation is not None
                    and not force_external_refresh
                    and annotation.fetched_at >= cache_cutoff
                ):
                    continue

                result = clinvar.lookup_variant(candidate.hgvs)
                fetched_at = datetime.now(UTC).replace(tzinfo=None)
                if annotation is None:
                    annotation = ExternalAnnotation(
                        candidate_variant_id=candidate.id,
                        source=CLINVAR_SOURCE,
                        lookup_status="not_found",
                        fetched_at=fetched_at,
                    )
                    session.add(annotation)

                annotation.fetched_at = fetched_at
                if result is None:
                    annotation.lookup_status = "not_found"
                    annotation.source_record_id = None
                    annotation.accession = None
                    annotation.accession_version = None
                    annotation.title = None
                    annotation.variant_type = None
                    annotation.canonical_spdi = None
                    annotation.classifications_json = "[]"
                    annotation.conditions_json = "[]"
                    annotation.review_status = None
                    annotation.source_url = None
                else:
                    annotation.lookup_status = "matched"
                    for field in (
                        "source_record_id",
                        "accession",
                        "accession_version",
                        "title",
                        "variant_type",
                        "canonical_spdi",
                        "review_status",
                        "source_url",
                    ):
                        setattr(annotation, field, result.get(field))
                    annotation.classifications_json = json.dumps(
                        result.get("classifications", []),
                        ensure_ascii=False,
                    )
                    annotation.conditions_json = json.dumps(
                        result.get("conditions", []),
                        ensure_ascii=False,
                    )

        session.commit()
    except ClinVarServiceError as exc:
        session.rollback()
        raise HTTPException(
            status_code=502,
            detail=(
                "ClinVar is temporarily unavailable. Candidate variants were "
                "saved locally; try the external lookup again later."
            ),
        ) from exc

    session.expire(analysis, ["candidate_variants"])
    return _research_response(analysis)


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

@analyses_router.get("/{analysis_id}/jak2-target")
def get_jak2_target_analysis(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    """Return preliminary JAK2 target and peak analysis."""

    analysis = session.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id,
        )
    )

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found",
        )

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
        if result is None:
            data = read_chromatogram(analysis.stored_file_path)
            result = analyze_jak2_chromatogram(data)

    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(
            status_code=422,
            detail="JAK2 target analysis unavailable.",
        ) from exc

    return {
        "analysis_id": analysis.id,
        "gene": analysis.gene,
        "target_variant": analysis.target_variant,
        "analysis_type": "preliminary",
        "result": result,
    }
