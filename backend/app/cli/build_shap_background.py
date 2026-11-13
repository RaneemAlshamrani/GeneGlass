"""Build a de-identified SHAP background from the reconstructed training split.

The output contains feature vectors and split provenance only. AB1 filenames and
source paths are deliberately excluded from the runtime asset.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from app.services.ai_predictor import _load_assets


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest(root: Path) -> list[dict[str, str]]:
    manifest = root / "manifest.csv"
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"file_name", "label", "sha256"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Invalid split manifest: {manifest}")
    return rows


def _resolve_ab1(root: Path, row: dict[str, str], split_name: str) -> Path:
    candidate = root / split_name / row["label"] / row["file_name"]
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    observed = _sha256(candidate)
    expected = row["sha256"].lower()
    if observed != expected:
        raise ValueError(f"SHA-256 mismatch for {candidate.name}")
    return candidate


def build_background(training_root: Path, testing_root: Path) -> dict:
    model, metadata, extractor = _load_assets()
    feature_names = list(metadata["features"])
    training_manifest = training_root / "manifest.csv"
    testing_manifest = testing_root / "manifest.csv"
    training_rows = _read_manifest(training_root)
    testing_rows = _read_manifest(testing_root)

    training_hashes = {row["sha256"].lower() for row in training_rows}
    testing_hashes = {row["sha256"].lower() for row in testing_rows}
    overlap = training_hashes & testing_hashes
    if overlap:
        raise ValueError("Training and testing manifests overlap by SHA-256")

    feature_rows: list[dict[str, float | None]] = []
    for row in training_rows:
        file_path = _resolve_ab1(training_root, row, "Training")
        extracted = extractor.extract_features(file_path)
        feature_rows.append({
            name: (
                float(extracted[name])
                if math.isfinite(float(extracted[name]))
                else None
            )
            for name in feature_names
        })

    if list(getattr(model, "feature_names_in_", feature_names)) != feature_names:
        raise ValueError("Model feature order differs from model metadata")

    return {
        "schema_version": 1,
        "feature_names": feature_names,
        "background_rows": feature_rows,
        "provenance": {
            "training_sample_count": len(training_rows),
            "testing_sample_count": len(testing_rows),
            "training_label_counts": dict(sorted(Counter(
                row["label"] for row in training_rows
            ).items())),
            "training_manifest_sha256": _sha256(training_manifest),
            "testing_manifest_sha256": _sha256(testing_manifest),
            "test_overlap_sha256_count": 0,
            "contains_filenames": False,
            "note": (
                "Background uses the 101-file reconstructed training complement. "
                "The original Colab training manifest was not retained; this split "
                "is strongly evidenced but not independently proven."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-root", type=Path, required=True)
    parser.add_argument("--testing-root", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "ai_assets"
        / "shap_background.json",
    )
    args = parser.parse_args()
    payload = build_background(args.training_root, args.testing_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Saved {len(payload['background_rows'])} de-identified rows to "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()
