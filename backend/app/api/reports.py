"""Fast report workflow for patient data, control AB1, and PDF export."""

from __future__ import annotations

from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.analysis import Analysis
from app.models.molecular_report import MolecularReport
from app.models.user import User
from app.services.ab1_reader import read_chromatogram
from app.services.audit import AuditAction, add_audit_event
from app.services.molecular_report_pdf import build_molecular_report_pdf
from app.services.storage.ab1_storage import save_ab1_file
from app.services.variant_detector import find_jak2_v617f_position

reports_router = APIRouter(prefix="/analyses", tags=["reports"])


def _analysis_for_owner(session: Session, analysis_id: int, user_id: int) -> Analysis:
    analysis = session.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == user_id,
        )
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


def _latest_report(session: Session, analysis_id: int) -> MolecularReport | None:
    return session.scalar(
        select(MolecularReport)
        .where(MolecularReport.analysis_id == analysis_id)
        .order_by(MolecularReport.version.desc())
        .limit(1)
    )


def _serialize(report: MolecularReport) -> dict:
    return {
        "id": report.id,
        "analysis_id": report.analysis_id,
        "version": report.version,
        "status": report.status,
        "patient_name": report.patient_name,
        "medical_record_number": report.medical_record_number,
        "gender": report.gender,
        "date_of_birth": report.date_of_birth,
        "physician_name": report.physician_name,
        "report_number": report.report_number,
        "received_date": report.received_date,
        "submitted_date": report.submitted_date,
        "clinical_history": report.clinical_history,
        "specimen_type": report.specimen_type,
        "final_decision": report.final_decision,
        "interpretation": report.interpretation,
        "normal_control_uploaded": bool(report.normal_control_file_path),
        "finalized_at": report.finalized_at,
        "download_url": (
            f"/api/analyses/{report.analysis_id}/report.pdf?version={report.version}"
            if report.status == "finalized"
            else None
        ),
    }


def _copy_as_draft(report: MolecularReport, author_id: int) -> MolecularReport:
    return MolecularReport(
        analysis_id=report.analysis_id,
        author_id=author_id,
        version=report.version + 1,
        status="draft",
        patient_name=report.patient_name,
        medical_record_number=report.medical_record_number,
        gender=report.gender,
        date_of_birth=report.date_of_birth,
        physician_name=report.physician_name,
        report_number=report.report_number,
        received_date=report.received_date,
        submitted_date=report.submitted_date,
        clinical_history=report.clinical_history,
        specimen_type=report.specimen_type,
        final_decision=report.final_decision,
        interpretation=report.interpretation,
        normal_control_file_path=report.normal_control_file_path,
        normal_control_sha256=report.normal_control_sha256,
    )


@reports_router.get("/{analysis_id}/report")
def get_report(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    _analysis_for_owner(session, analysis_id, current_user.id)
    report = _latest_report(session, analysis_id)
    return {"report": _serialize(report) if report else None}


@reports_router.put("/{analysis_id}/report")
async def save_report_draft(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    patient_name: Annotated[str, Form()],
    medical_record_number: Annotated[str, Form()],
    gender: Annotated[str, Form()],
    date_of_birth: Annotated[date, Form()],
    physician_name: Annotated[str, Form()],
    report_number: Annotated[str, Form()],
    received_date: Annotated[date, Form()],
    submitted_date: Annotated[date, Form()],
    clinical_history: Annotated[str, Form()] = "",
    specimen_type: Annotated[str, Form()] = "Peripheral Blood",
    final_decision: Annotated[Literal["positive", "negative"], Form()] = "negative",
    interpretation: Annotated[str, Form()] = "",
    normal_control: Annotated[UploadFile | None, File()] = None,
) -> dict:
    analysis = _analysis_for_owner(session, analysis_id, current_user.id)
    latest = _latest_report(session, analysis_id)
    if latest is None:
        report = MolecularReport(
            analysis_id=analysis.id,
            author_id=current_user.id,
            version=1,
            status="draft",
        )
        session.add(report)
    elif latest.status == "finalized":
        report = _copy_as_draft(latest, current_user.id)
        session.add(report)
    else:
        report = latest

    new_control_path: Path | None = None
    old_control_path = report.normal_control_file_path
    if normal_control is not None and normal_control.filename:
        new_control_path, control_sha256 = await save_ab1_file(
            normal_control, current_user.id
        )
        try:
            control_trace = read_chromatogram(new_control_path)
            target = find_jak2_v617f_position(control_trace["sequence"])
            if not target.get("found"):
                raise ValueError("V617F target is not covered")
        except (ValueError, FileNotFoundError, OSError) as exc:
            new_control_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=422,
                detail="The normal-control AB1 does not cover the JAK2 V617F target.",
            ) from exc
        report.normal_control_file_path = str(new_control_path)
        report.normal_control_sha256 = control_sha256

    report.patient_name = patient_name.strip()
    report.medical_record_number = medical_record_number.strip()
    report.gender = gender.strip()
    report.date_of_birth = date_of_birth
    report.physician_name = physician_name.strip()
    report.report_number = report_number.strip()
    report.received_date = received_date
    report.submitted_date = submitted_date
    report.clinical_history = clinical_history.strip()
    report.specimen_type = specimen_type.strip() or "Peripheral Blood"
    report.final_decision = final_decision
    report.interpretation = interpretation.strip()
    report.author_id = current_user.id
    session.flush()
    add_audit_event(
        session,
        actor_id=current_user.id,
        analysis_id=analysis.id,
        action=AuditAction.REPORT_DRAFT_SAVED,
        details={"report_id": report.id, "version": report.version},
    )
    session.commit()
    session.refresh(report)
    if (
        new_control_path is not None
        and old_control_path
        and old_control_path != str(new_control_path)
        and latest is not None
        and latest.status == "draft"
    ):
        Path(old_control_path).unlink(missing_ok=True)
    return {"report": _serialize(report)}


@reports_router.post("/{analysis_id}/report/finalize")
def finalize_report(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict:
    analysis = _analysis_for_owner(session, analysis_id, current_user.id)
    report = _latest_report(session, analysis_id)
    if report is None or report.status != "draft":
        raise HTTPException(status_code=409, detail="No report draft is available")
    required = {
        "patient name": report.patient_name,
        "medical record number": report.medical_record_number,
        "physician": report.physician_name,
        "report number": report.report_number,
        "final decision": report.final_decision,
        "interpretation": report.interpretation,
        "normal control": report.normal_control_file_path,
    }
    missing = [label for label, value in required.items() if not value]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Complete these report fields: {', '.join(missing)}.",
        )
    try:
        patient_trace = read_chromatogram(analysis.stored_file_path or "")
        control_trace = read_chromatogram(report.normal_control_file_path or "")
        if not find_jak2_v617f_position(patient_trace["sequence"]).get("found"):
            raise ValueError("Patient target unavailable")
        if not find_jak2_v617f_position(control_trace["sequence"]).get("found"):
            raise ValueError("Control target unavailable")
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Patient or normal-control chromatogram is unavailable.",
        ) from exc

    report.status = "finalized"
    report.finalized_at = datetime.now(UTC)
    add_audit_event(
        session,
        actor_id=current_user.id,
        analysis_id=analysis.id,
        action=AuditAction.REPORT_FINALIZED,
        details={
            "report_id": report.id,
            "version": report.version,
            "decision": report.final_decision,
        },
    )
    session.commit()
    session.refresh(report)
    return {"report": _serialize(report)}


@reports_router.get("/{analysis_id}/report.pdf")
def download_report_pdf(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    version: int | None = None,
) -> StreamingResponse:
    analysis = _analysis_for_owner(session, analysis_id, current_user.id)
    query = select(MolecularReport).where(
        MolecularReport.analysis_id == analysis.id,
        MolecularReport.status == "finalized",
    )
    if version is not None:
        query = query.where(MolecularReport.version == version)
    report = session.scalar(query.order_by(MolecularReport.version.desc()).limit(1))
    if report is None:
        raise HTTPException(status_code=404, detail="Finalized report not found")
    try:
        content = build_molecular_report_pdf(report, analysis, report.author)
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=422, detail="Report PDF could not be generated") from exc
    safe_number = re.sub(r"[^A-Za-z0-9._-]+", "-", report.report_number or "report")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="GeneGlass-{safe_number}.pdf"'
        },
    )
