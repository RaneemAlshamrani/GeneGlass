"""Tests for reproducible, non-diagnostic reference-dataset validation."""

import json
from pathlib import Path

import pytest

from app.services.variant_detector import (
    JAK2_V617F_REFERENCE_INDEX,
    load_jak2_reference,
)
from app.validation import reference_dataset
from app.validation.reference_dataset import (
    ManifestError,
    load_reference_manifest,
    run_reference_validation,
    write_validation_report,
)


def build_synthetic_target_trace() -> dict:
    reference = load_jak2_reference()
    start = JAK2_V617F_REFERENCE_INDEX - 100
    sequence = reference[start : JAK2_V617F_REFERENCE_INDEX + 101]
    base_positions = [index * 2 for index in range(len(sequence))]
    trace_length = base_positions[-1] + 2
    channels = {base: [5] * trace_length for base in "ACGT"}
    for index, base in enumerate(sequence):
        channels[base][base_positions[index]] = 1000
    return {
        "sequence": sequence,
        "quality_scores": [40] * len(sequence),
        "base_positions": base_positions,
        "channels": channels,
    }


def write_manifest(path: Path, row: str) -> None:
    path.write_text(
        "sample_id,ab1_path,expected_v617f_status,comparator_method,"
        "source_type,replicate_group\n"
        + row
        + "\n",
        encoding="utf-8",
    )


def test_reference_validation_reports_technical_evidence_without_raw_data(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ab1_path = tmp_path / "reference.ab1"
    ab1_path.write_bytes(b"ABIF-reference-material")
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        "REF-001,reference.ab1,negative,Independent qPCR,"
        "commercial_reference_material,LOT-A",
    )
    monkeypatch.setattr(
        reference_dataset,
        "read_chromatogram",
        lambda _path: build_synthetic_target_trace(),
    )

    report = run_reference_validation(manifest)

    assert report["research_use_only"] is True
    assert report["reference"]["accession"] == "NM_004972.4"
    assert len(report["reference"]["fasta_sha256"]) == 64
    assert report["summary"]["total_samples"] == 1
    assert report["summary"]["technical_checks_passed"] == 1
    assert all(
        count == 0
        for count in report["summary"][
            "failed_technical_check_counts"
        ].values()
    )
    assert report["summary"]["classification_metrics"] == "not_calculated"
    sample = report["samples"][0]
    assert sample["technical_check_status"] == "passed"
    assert sample["classification_comparison"].startswith("not_available")
    serialized = json.dumps(report)
    assert str(ab1_path) not in serialized
    assert "sequence" not in sample
    assert "channels" not in sample

    output = write_validation_report(report, tmp_path / "report.json")
    assert json.loads(output.read_text(encoding="utf-8"))["samples"][0][
        "sample_id"
    ] == "REF-001"
    with pytest.raises(FileExistsError):
        write_validation_report(report, output)


def test_manifest_rejects_labels_without_independent_comparator(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        "REF-002,sample.ab1,positive,,previously_tested_specimen,",
    )

    with pytest.raises(ManifestError, match="comparator_method"):
        load_reference_manifest(manifest)


def test_missing_reference_file_is_reported_without_exposing_path(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.csv"
    write_manifest(
        manifest,
        "REF-003,missing.ab1,unknown,,development_sample,",
    )

    report = run_reference_validation(manifest)

    assert report["summary"]["processing_errors"] == 1
    assert report["samples"][0]["error_code"] == "file_not_found"
    assert str(tmp_path) not in json.dumps(report)
