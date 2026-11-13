"""Verification for de-identified, additive Tree SHAP explanations."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.services.ai_predictor import _load_assets, predict_ab1
from app.services.shap_explainer import (
    BACKGROUND_PATH,
    explain_hetero_probability,
)


def test_background_is_training_only_and_deidentified() -> None:
    raw = BACKGROUND_PATH.read_text(encoding="utf-8")
    payload = json.loads(raw)

    assert len(payload["background_rows"]) == 101
    assert payload["provenance"]["training_sample_count"] == 101
    assert payload["provenance"]["testing_sample_count"] == 20
    assert payload["provenance"]["test_overlap_sha256_count"] == 0
    assert payload["provenance"]["contains_filenames"] is False
    assert ".ab1" not in raw.lower()
    assert "source_archive_path" not in raw


def test_tree_shap_reconstructs_hetero_probability() -> None:
    model, metadata, _extractor = _load_assets()
    payload = json.loads(BACKGROUND_PATH.read_text(encoding="utf-8"))
    feature_names = list(metadata["features"])
    row = pd.DataFrame(
        [payload["background_rows"][0]],
        columns=feature_names,
    )

    explanation = explain_hetero_probability(model, row, feature_names)
    expected = float(model.predict_proba(row)[0, 1])

    assert explanation["available"] is True
    assert explanation["target_class"] == "hetero"
    assert explanation["background_sample_count"] == 101
    assert explanation["test_overlap_sha256_count"] == 0
    assert abs(explanation["output_value"] - expected) < 1e-10
    assert abs(explanation["reconstructed_output"] - expected) < 1e-5
    assert {item["feature"] for item in explanation["contributions"]} == set(
        feature_names
    )


def test_qc_failure_returns_no_shap_attribution(tmp_path: Path) -> None:
    result = predict_ab1(tmp_path / "not-read.ab1", qc_passed=False)

    assert result["status"] == "Needs Review"
    assert result["explanation"]["available"] is False
    assert "QC" in result["explanation"]["reason"]
