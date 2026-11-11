"""Optional research-only AI prediction; does not modify the existing QC pipeline."""
from __future__ import annotations

import importlib.util
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

ASSETS = Path(__file__).resolve().parents[2] / "ai_assets"


@lru_cache(maxsize=1)
def _load_assets():
    metadata = json.loads((ASSETS / "model_metadata.json").read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("geneglass_training_ab1_processing", ASSETS / "ab1_processing.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the training feature extractor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Only load trusted model artifacts supplied by the project team.
    model = joblib.load(ASSETS / "geneglass_random_forest.joblib")
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
    if not qc_passed:
        return {"status": "Needs Review", "reason": "Existing QC requires review",
                "prediction": None, "probabilities": None, "research_use_only": True}
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
        return {
            "status": "Needs Review" if review else ("Hetero" if predicted == "hetero" else "Negative"),
            "prediction": predicted,
            "probabilities": probabilities,
            "reason": "Prediction below provisional review threshold" if review else None,
            "orientation": features["orientation"],
            "features": {k: None if not math.isfinite(float(features[k])) else float(features[k]) for k in metadata["features"]},
            "model_name": metadata["model_name"],
            "research_use_only": True,
            "limitations": "Binary research model; not validated for homo/noise or clinical diagnosis. Probabilities are not clinical confidence.",
        }
    except (ValueError, KeyError, IndexError, OSError, UnicodeError, RuntimeError, FloatingPointError) as exc:
        return {"status": "Needs Review", "prediction": None, "probabilities": None,
                "reason": f"AI processing unavailable: {type(exc).__name__}", "research_use_only": True}
