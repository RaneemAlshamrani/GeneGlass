from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import joblib

from app.services.noise_qc_features import FEATURE_NAMES


ASSETS = Path(__file__).resolve().parents[1] / "ai_assets"


def test_noise_qc_artifact_and_metadata_are_consistent() -> None:
    model_path = ASSETS / "noise_qc_random_forest.joblib"
    metadata = json.loads((ASSETS / "noise_qc_metadata.json").read_text(encoding="utf-8"))
    model = joblib.load(model_path)

    assert metadata["research_use_only"] is True
    assert metadata["classes"] == {"0": "acceptable", "1": "noise"}
    assert metadata["features"] == FEATURE_NAMES
    assert list(model.feature_names_in_) == FEATURE_NAMES
    assert hashlib.sha256(model_path.read_bytes()).hexdigest() == metadata["model_sha256"]
    assert 0 <= metadata["review_probability_threshold"] < metadata["noise_probability_threshold"] <= 1


def test_noise_qc_split_has_no_file_or_group_leakage() -> None:
    with (ASSETS / "noise_qc_split_manifest.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    training = [row for row in rows if row["split"] == "training"]
    testing = [row for row in rows if row["split"] == "testing"]

    assert len(training) == 133
    assert len(testing) == 47
    assert {row["sha256"] for row in training}.isdisjoint(row["sha256"] for row in testing)
    assert {row["group_hash"] for row in training}.isdisjoint(row["group_hash"] for row in testing)


def test_noise_qc_independent_evaluation_is_recorded_without_claiming_validation() -> None:
    evaluation = json.loads((ASSETS / "noise_qc_evaluation.json").read_text(encoding="utf-8"))
    metrics = evaluation["independent_test_metrics"]
    triage = evaluation["independent_test_triage"]

    assert metrics["confusion_matrix"] == {"tn": 26, "fp": 5, "fn": 2, "tp": 14}
    assert metrics["roc_auc"] >= 0.90
    assert metrics["noise_recall"] >= 0.80
    assert triage["noise"]["pass"] == 0
    assert any("not clinically validated" in item.lower() for item in evaluation["limitations"])
