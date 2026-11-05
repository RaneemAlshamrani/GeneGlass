"""Run reproducible, non-diagnostic checks against local reference AB1 files."""

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.ab1_reader import read_chromatogram
from app.services.variant_detector import (
    JAK2_V617F_CDNA_POSITION,
    MIN_ALIGNMENT_IDENTITY_PERCENT,
    MIN_ALIGNMENT_READ_COVERAGE_PERCENT,
    REFERENCE_PATH,
    analyze_jak2_chromatogram,
)

PIPELINE_VERSION = "preliminary-jak2-evidence-v1"
REFERENCE_ACCESSION = "NM_004972.4"
ALLOWED_EXPECTED_STATUSES = {"positive", "negative", "unknown"}
ALLOWED_SOURCE_TYPES = {
    "commercial_reference_material",
    "proficiency_testing",
    "previously_tested_specimen",
    "synthetic_control",
    "development_sample",
}
SAMPLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class ManifestError(ValueError):
    """Raised when a validation manifest is incomplete or unsafe."""


@dataclass(frozen=True)
class ReferenceSample:
    sample_id: str
    ab1_path: Path
    expected_v617f_status: str
    comparator_method: str
    source_type: str
    replicate_group: str | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_reference_manifest(manifest_path: str | Path) -> list[ReferenceSample]:
    """Validate manifest metadata without reading any AB1 contents."""

    path = Path(manifest_path).resolve()
    if not path.is_file():
        raise ManifestError(f"Manifest file not found: {path.name}")

    required_fields = {
        "sample_id",
        "ab1_path",
        "expected_v617f_status",
        "comparator_method",
        "source_type",
        "replicate_group",
    }
    samples: list[ReferenceSample] = []
    seen_ids: set[str] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_fields = required_fields - set(reader.fieldnames or [])
        if missing_fields:
            raise ManifestError(
                "Manifest is missing columns: "
                + ", ".join(sorted(missing_fields))
            )

        for row_number, row in enumerate(reader, start=2):
            sample_id = (row.get("sample_id") or "").strip()
            if not SAMPLE_ID_PATTERN.fullmatch(sample_id):
                raise ManifestError(
                    f"Row {row_number}: sample_id must be de-identified and "
                    "contain only letters, numbers, dot, underscore, or hyphen"
                )
            if sample_id in seen_ids:
                raise ManifestError(
                    f"Row {row_number}: duplicate sample_id {sample_id}"
                )
            seen_ids.add(sample_id)

            relative_ab1_path = (row.get("ab1_path") or "").strip()
            if not relative_ab1_path:
                raise ManifestError(f"Row {row_number}: ab1_path is required")
            ab1_path = Path(relative_ab1_path)
            if not ab1_path.is_absolute():
                ab1_path = (path.parent / ab1_path).resolve()
            if ab1_path.suffix.lower() != ".ab1":
                raise ManifestError(
                    f"Row {row_number}: reference file must use .ab1 extension"
                )

            expected_status = (
                row.get("expected_v617f_status") or ""
            ).strip().lower()
            if expected_status not in ALLOWED_EXPECTED_STATUSES:
                raise ManifestError(
                    f"Row {row_number}: expected_v617f_status must be one of "
                    + ", ".join(sorted(ALLOWED_EXPECTED_STATUSES))
                )

            comparator_method = (row.get("comparator_method") or "").strip()
            if expected_status in {"positive", "negative"} and not comparator_method:
                raise ManifestError(
                    f"Row {row_number}: independently verified positive/negative "
                    "samples require comparator_method"
                )

            source_type = (row.get("source_type") or "").strip().lower()
            if source_type not in ALLOWED_SOURCE_TYPES:
                raise ManifestError(
                    f"Row {row_number}: unsupported source_type"
                )

            replicate_group = (row.get("replicate_group") or "").strip() or None
            samples.append(ReferenceSample(
                sample_id=sample_id,
                ab1_path=ab1_path,
                expected_v617f_status=expected_status,
                comparator_method=comparator_method,
                source_type=source_type,
                replicate_group=replicate_group,
            ))

    if not samples:
        raise ManifestError("Manifest contains no reference samples")
    return samples


def _technical_checks(result: dict[str, Any]) -> dict[str, bool]:
    peaks = result.get("peak_analysis") or {}
    region = result.get("target_region") or {}
    return {
        "target_mapped": result.get("found") is True,
        "identity_at_least_preliminary_threshold": (
            float(result.get("alignment_identity_percentage") or 0)
            >= MIN_ALIGNMENT_IDENTITY_PERCENT
        ),
        "coverage_at_least_preliminary_threshold": (
            float(result.get("alignment_coverage_percentage") or 0)
            >= MIN_ALIGNMENT_READ_COVERAGE_PERCENT
        ),
        "target_quality_available": result.get("quality_score") is not None,
        "target_peaks_available": bool(peaks.get("peak_heights")),
        "target_region_available": region.get("available") is True,
    }


def _sample_result(sample: ReferenceSample) -> dict[str, Any]:
    base = {
        "sample_id": sample.sample_id,
        "expected_v617f_status": sample.expected_v617f_status,
        "comparator_method": sample.comparator_method or None,
        "source_type": sample.source_type,
        "replicate_group": sample.replicate_group,
    }
    if not sample.ab1_path.is_file():
        return {
            **base,
            "processing_status": "error",
            "error_code": "file_not_found",
        }

    try:
        trace = read_chromatogram(sample.ab1_path)
        result = analyze_jak2_chromatogram(trace)
    except (ValueError, OSError, FileNotFoundError) as exc:
        return {
            **base,
            "file_sha256": _sha256(sample.ab1_path),
            "processing_status": "error",
            "error_code": type(exc).__name__,
        }

    checks = _technical_checks(result)
    peaks = result.get("peak_analysis") or {}
    return {
        **base,
        "file_sha256": _sha256(sample.ab1_path),
        "processing_status": "processed",
        "technical_check_status": (
            "passed" if all(checks.values()) else "needs_review"
        ),
        "technical_checks": checks,
        "evidence": {
            "target_mapped": result.get("found", False),
            "direction": result.get("direction"),
            "target_ab1_base_number": result.get("ab1_base_number"),
            "observed_base": result.get("observed_base"),
            "target_phred_quality": result.get("quality_score"),
            "alignment_identity_percentage": result.get(
                "alignment_identity_percentage"
            ),
            "alignment_coverage_percentage": result.get(
                "alignment_coverage_percentage"
            ),
            "primary_peak": peaks.get("primary_base"),
            "secondary_peak": peaks.get("secondary_base"),
            "secondary_to_primary_ratio": peaks.get("overlap_ratio"),
            "review_status": result.get("review_status"),
            "review_reasons": result.get("review_reasons", []),
        },
        "classification_comparison": (
            "not_available_pipeline_has_no_validated_classifier"
        ),
    }


def run_reference_validation(
    manifest_path: str | Path,
) -> dict[str, Any]:
    """Process a private manifest and return a de-identified JSON-ready report."""

    manifest = Path(manifest_path).resolve()
    samples = load_reference_manifest(manifest)
    results = [_sample_result(sample) for sample in samples]
    processed = [
        item for item in results if item["processing_status"] == "processed"
    ]
    status_counts = {
        status: sum(
            item["expected_v617f_status"] == status for item in results
        )
        for status in sorted(ALLOWED_EXPECTED_STATUSES)
    }
    technical_check_names = sorted({
        check_name
        for item in processed
        for check_name in item.get("technical_checks", {})
    })
    failed_check_counts = {
        check_name: sum(
            item.get("technical_checks", {}).get(check_name) is False
            for item in processed
        )
        for check_name in technical_check_names
    }
    return {
        "report_type": "GeneGlass preliminary pipeline validation evidence",
        "research_use_only": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "pipeline": {
            "version": PIPELINE_VERSION,
            "classification_available": False,
            "preliminary_thresholds": {
                "minimum_alignment_identity_percentage": (
                    MIN_ALIGNMENT_IDENTITY_PERCENT
                ),
                "minimum_read_coverage_percentage": (
                    MIN_ALIGNMENT_READ_COVERAGE_PERCENT
                ),
            },
        },
        "reference": {
            "accession": REFERENCE_ACCESSION,
            "v617f_cdna_position": JAK2_V617F_CDNA_POSITION,
            "fasta_sha256": _sha256(REFERENCE_PATH),
        },
        "manifest_sha256": _sha256(manifest),
        "summary": {
            "total_samples": len(results),
            "successfully_processed": len(processed),
            "processing_errors": len(results) - len(processed),
            "technical_checks_passed": sum(
                item.get("technical_check_status") == "passed"
                for item in processed
            ),
            "technical_checks_need_review": sum(
                item.get("technical_check_status") == "needs_review"
                for item in processed
            ),
            "failed_technical_check_counts": failed_check_counts,
            "expected_status_counts": status_counts,
            "classification_metrics": "not_calculated",
            "classification_metrics_reason": (
                "The current pipeline exposes preliminary evidence and does not "
                "produce a validated positive/negative classification."
            ),
        },
        "samples": results,
        "limitations": [
            "This report validates technical processing only, not clinical performance.",
            "Sensitivity, specificity, PPA, and NPA are not calculated without a validated classifier and an independent reference standard.",
            "AB1 files and raw sequences are processed locally and are not embedded in this report.",
        ],
    }


def write_validation_report(report: dict[str, Any], output_path: str | Path) -> Path:
    """Write a report without overwriting an existing validation artifact."""

    destination = Path(output_path).resolve()
    if destination.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing report: {destination.name}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination
