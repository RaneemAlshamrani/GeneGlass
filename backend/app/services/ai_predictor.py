"""Optional research-only AI prediction; does not modify the existing QC pipeline."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.services.shap_explainer import (
    explain_hetero_probability,
    unavailable_explanation,
)

ASSETS = Path(__file__).resolve().parents[2] / "ai_assets"
MODEL_PATH = ASSETS / "geneglass_random_forest.joblib"
LIMITATIONS = (
    "Binary research model; not validated for homo/noise or clinical "
    "diagnosis. Probabilities are not clinical confidence."
)


@lru_cache(maxsize=1)
def get_model_identity() -> dict[str, str]:
    """Return reproducible identities for the model and inference bundle."""

    artifact_digest = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    bundle_digest = hashlib.sha256()
    bundle_assets = (
        ASSETS / "geneglass_random_forest.joblib",
        ASSETS / "ab1_processing.py",
        ASSETS / "model_metadata.json",
        ASSETS / "jak2_reference.txt",
        ASSETS / "shap_background.json",
        Path(__file__).with_name("shap_explainer.py"),
    )
    for asset in bundle_assets:
        asset_name = asset.name
        bundle_digest.update(asset_name.encode("utf-8"))
        bundle_digest.update(asset.read_bytes())
    metadata = json.loads(
        (ASSETS / "model_metadata.json").read_text(encoding="utf-8")
    )
    return {
        "model_name": metadata["model_name"],
        "model_version": bundle_digest.hexdigest()[:12],
        "model_artifact_sha256": artifact_digest,
    }


@lru_cache(maxsize=1)
def _load_assets():
    metadata = json.loads((ASSETS / "model_metadata.json").read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("geneglass_training_ab1_processing", ASSETS / "ab1_processing.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the training feature extractor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Only load trusted model artifacts supplied by the project team.
    model = joblib.load(MODEL_PATH)
    features = metadata["features"]
    if list(getattr(model, "feature_names_in_", features)) != features:
        raise ValueError("Model feature order differs from metadata")
    return model, metadata, module


def predict_ab1(file_path: str | Path, *, qc_passed: bool = True,
                minimum_class_probability: float | None = None) -> dict[str, Any]:
    """Return Negative/Hetero or Needs Review; no clinical interpretation.

    minimum_class_probability is an OPTIONAL, *unvalidated* review policy.
    Leave it None until a threshold has been chosen on separate validation data.
    """
    identity = get_model_identity()
    if not qc_passed:
        return {
            "status": "Needs Review",
            "reason": "Existing QC requires review",
            "prediction": None,
            "probabilities": None,
            "orientation": None,
            "features": None,
            "explanation": unavailable_explanation(
                "Existing QC requires specialist review"
            ),
            **identity,
            "research_use_only": True,
            "limitations": LIMITATIONS,
        }
    if minimum_class_probability is not None and not (0.5 <= minimum_class_probability <= 1.0):
        raise ValueError("minimum_class_probability must be between 0.5 and 1.0")
    try:
        model, metadata, extractor = _load_assets()
        features = extractor.extract_features(file_path)
        row = pd.DataFrame([{key: features[key] for key in metadata["features"]}], columns=metadata["features"])
        if np.isinf(row.to_numpy(dtype=float)).any():
            raise ValueError("Infinite extracted feature")
        classes = [int(c) for c in model.classes_]
        scores = model.predict_proba(row)[0]
        probabilities = {metadata["classes"][str(c)]: float(p) for c,p in zip(classes,scores)}
        predicted = metadata["classes"][str(int(model.predict(row)[0]))]
        maximum = max(probabilities.values())
        review = minimum_class_probability is not None and maximum < minimum_class_probability
        try:
            explanation = explain_hetero_probability(
                model,
                row,
                list(metadata["features"]),
            )
        except (
            ValueError,
            KeyError,
            IndexError,
            OSError,
            ImportError,
            AttributeError,
            UnicodeError,
            RuntimeError,
            FloatingPointError,
        ) as exc:
            explanation = unavailable_explanation(
                f"SHAP explanation unavailable: {type(exc).__name__}"
            )
        return {
            "status": "Needs Review" if review else ("Hetero" if predicted == "hetero" else "Negative"),
            "prediction": predicted,
            "probabilities": probabilities,
            "reason": "Prediction below provisional review threshold" if review else None,
            "orientation": features["orientation"],
            "features": {k: None if not math.isfinite(float(features[k])) else float(features[k]) for k in metadata["features"]},
            "explanation": explanation,
            **identity,
            "research_use_only": True,
            "limitations": LIMITATIONS,
        }
    except (ValueError, KeyError, IndexError, OSError, UnicodeError, RuntimeError, FloatingPointError) as exc:
        return {
            "status": "Needs Review",
            "prediction": None,
            "probabilities": None,
            "reason": f"AI processing unavailable: {type(exc).__name__}",
            "orientation": None,
            "features": None,
            "explanation": unavailable_explanation(
                "Prediction features are unavailable"
            ),
            **identity,
            "research_use_only": True,
            "limitations": LIMITATIONS,
        }
