"""Tree SHAP explanations for the research-only GeneGlass classifier."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ASSETS = Path(__file__).resolve().parents[2] / "ai_assets"
BACKGROUND_PATH = ASSETS / "shap_background.json"
TARGET_CLASS = "hetero"

_EXPLAINER_CACHE: dict[int, tuple[Any, dict[str, Any], str, str]] = {}


def _load_background() -> tuple[dict[str, Any], str]:
    raw = BACKGROUND_PATH.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    digest = hashlib.sha256(raw).hexdigest()
    return payload, digest


def _get_explainer(
    model: Any,
    feature_names: list[str],
) -> tuple[Any, dict[str, Any], str, str]:
    cache_key = id(model)
    cached = _EXPLAINER_CACHE.get(cache_key)
    if cached is not None:
        return cached

    import shap

    payload, background_digest = _load_background()
    if payload.get("feature_names") != feature_names:
        raise ValueError("SHAP background feature order differs from model metadata")
    background_rows = payload.get("background_rows")
    if not isinstance(background_rows, list) or not background_rows:
        raise ValueError("SHAP background is empty")

    background = pd.DataFrame(background_rows, columns=feature_names)
    imputer = model.named_steps["imputer"]
    classifier = model.named_steps["classifier"]
    transformed = imputer.transform(background)
    masker = shap.maskers.Independent(
        transformed,
        max_samples=len(transformed),
    )
    explainer = shap.TreeExplainer(
        classifier,
        data=masker,
        feature_perturbation="interventional",
        model_output="probability",
    )
    shap_version = importlib.metadata.version("shap")
    cached = (explainer, payload, background_digest, shap_version)
    _EXPLAINER_CACHE[cache_key] = cached
    return cached


def explain_hetero_probability(
    model: Any,
    row: pd.DataFrame,
    feature_names: list[str],
) -> dict[str, Any]:
    """Explain one prediction as contributions to the Hetero probability."""

    explainer, background, background_digest, shap_version = _get_explainer(
        model,
        feature_names,
    )
    classifier = model.named_steps["classifier"]
    classes = [int(value) for value in classifier.classes_]
    if 1 not in classes:
        raise ValueError("Hetero class is missing from the classifier")
    class_index = classes.index(1)

    transformed = model.named_steps["imputer"].transform(row)
    explanation = explainer(transformed, check_additivity=True)
    values = np.asarray(explanation.values, dtype=float)
    base_values = np.asarray(explanation.base_values, dtype=float)
    if values.ndim != 3 or values.shape != (1, len(feature_names), len(classes)):
        raise ValueError("Unexpected SHAP output shape")

    contributions = values[0, :, class_index]
    base_value = float(base_values[0, class_index])
    output_value = float(model.predict_proba(row)[0, class_index])
    reconstructed = base_value + float(contributions.sum())
    if not math.isclose(reconstructed, output_value, rel_tol=1e-5, abs_tol=1e-5):
        raise ValueError("SHAP contributions do not reconstruct model output")

    feature_values = row.iloc[0]
    ordered = sorted(
        (
            {
                "feature": feature,
                "value": (
                    None
                    if pd.isna(feature_values[feature])
                    else float(feature_values[feature])
                ),
                "impact": float(impact),
                "direction": "toward_hetero" if impact >= 0 else "toward_negative",
            }
            for feature, impact in zip(feature_names, contributions, strict=True)
        ),
        key=lambda item: abs(item["impact"]),
        reverse=True,
    )
    provenance = background.get("provenance") or {}
    return {
        "available": True,
        "method": "Tree SHAP",
        "target_class": TARGET_CLASS,
        "base_value": base_value,
        "output_value": output_value,
        "reconstructed_output": reconstructed,
        "contributions": ordered,
        "background_sample_count": len(background["background_rows"]),
        "background_sha256": background_digest,
        "shap_version": shap_version,
        "background_provenance": provenance.get("note"),
        "test_overlap_sha256_count": provenance.get(
            "test_overlap_sha256_count"
        ),
        "limitations": (
            "Explains this model output, not biological causality or clinical "
            "validity. Correlated signal features may share attribution."
        ),
    }


def unavailable_explanation(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "method": "Tree SHAP",
        "target_class": TARGET_CLASS,
        "reason": reason,
    }
