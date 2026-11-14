"""Inference helper for the research-only AB1 noise QC gate."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from app.services.noise_qc_features import FEATURE_NAMES, extract_noise_qc_features


ASSETS = Path(__file__).resolve().parents[2] / "ai_assets"
MODEL_PATH = ASSETS / "noise_qc_random_forest.joblib"
METADATA_PATH = ASSETS / "noise_qc_metadata.json"


@lru_cache(maxsize=1)
def _load_assets() -> tuple[object, dict[str, object]]:
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    model = joblib.load(MODEL_PATH)
    if metadata["features"] != FEATURE_NAMES:
        raise ValueError("Noise QC metadata feature order is incompatible")
    if list(getattr(model, "feature_names_in_", FEATURE_NAMES)) != FEATURE_NAMES:
        raise ValueError("Noise QC model feature order is incompatible")
    digest = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    if digest != metadata["model_sha256"]:
        raise ValueError("Noise QC model artifact hash does not match metadata")
    return model, metadata


def predict_noise_qc(file_path: str | Path) -> dict[str, object]:
    """Return a conservative three-zone QC triage for one original AB1 trace."""
    model, metadata = _load_assets()
    features = extract_noise_qc_features(file_path)
    row = pd.DataFrame([features], columns=FEATURE_NAMES)
    probability = float(model.predict_proba(row)[0, 1])
    noise_threshold = float(metadata["noise_probability_threshold"])
    review_threshold = float(metadata["review_probability_threshold"])
    status = (
        "high_noise" if probability >= noise_threshold
        else "needs_review" if probability >= review_threshold
        else "pass"
    )
    return {
        "status": status,
        "noise_probability": probability,
        "review_probability_threshold": review_threshold,
        "noise_probability_threshold": noise_threshold,
        "model_name": metadata["model_name"],
        "model_sha256": metadata["model_sha256"],
        "features": features,
        "research_use_only": True,
        "note": (
            "Research-only QC support. Needs Review or High Noise should not "
            "be converted into a genotype result without specialist review."
        ),
    }
