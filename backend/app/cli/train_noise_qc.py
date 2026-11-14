"""Train and independently evaluate the research-only AB1 noise QC gate."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

from app.services.noise_qc_features import FEATURE_NAMES, extract_noise_qc_features


RANDOM_SEED = 20261114
SOURCE_LABELS = {"negative": 0, "hetero": 0, "noice": 1, "noise": 1}


@dataclass(frozen=True)
class Sample:
    archive_name: str
    label: int
    label_name: str
    sha256: str
    group_hash: str
    content: bytes
    features: dict[str, float]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sample_group(filename: str) -> str:
    """Build a conservative sample group from the pre-'=' specimen token."""
    stem = unicodedata.normalize("NFKD", PurePosixPath(filename).stem).upper()
    specimen = stem.split("=", 1)[0]
    specimen = re.sub(r"\b(?:NOI[CS]E|NOISY|NEGATIVE|HETERO|HTERO|HETRO|NORMAL)\b", " ", specimen)
    specimen = re.sub(r"(?:[-_ ](?:F|R))$", "", specimen)
    specimen = re.sub(r"\bJAK2?[-_ ]?(?:F|R)$", "JAK2", specimen)
    specimen = re.sub(r"[^A-Z0-9]+", "-", specimen).strip("-")
    if not specimen:
        specimen = _sha256(filename.encode("utf-8"))[:16]
    return hashlib.sha256(specimen.encode("utf-8")).hexdigest()[:20]


def _load_samples(source_zip: Path) -> tuple[list[Sample], Counter[str]]:
    samples: list[Sample] = []
    excluded: Counter[str] = Counter()
    with ZipFile(source_zip) as archive, tempfile.TemporaryDirectory(prefix="geneglass-noise-qc-") as temp:
        temp_root = Path(temp)
        for info in archive.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".ab1"):
                continue
            parts = PurePosixPath(info.filename).parts
            folder = parts[-2].lower() if len(parts) >= 2 else ""
            if folder not in SOURCE_LABELS:
                excluded[folder or "unlabeled"] += 1
                continue
            label = SOURCE_LABELS[folder]
            content = archive.read(info)
            digest = _sha256(content)
            local_path = temp_root / f"{digest}.ab1"
            local_path.write_bytes(content)
            features = extract_noise_qc_features(local_path)
            samples.append(Sample(
                archive_name=info.filename,
                label=label,
                label_name="noise" if label else "acceptable",
                sha256=digest,
                group_hash=_sample_group(info.filename),
                content=content,
                features=features,
            ))
    if len({sample.sha256 for sample in samples}) != len(samples):
        raise ValueError("Duplicate AB1 contents found in the source dataset")
    return samples, excluded


def _choose_test_fold(labels: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    splitter = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=RANDOM_SEED)
    placeholder = np.zeros(len(labels))
    candidates = list(splitter.split(placeholder, labels, groups))
    target_counts = Counter(labels)

    def score(candidate: tuple[np.ndarray, np.ndarray]) -> float:
        _, test_index = candidate
        observed = Counter(labels[test_index])
        return sum(abs(observed[label] - total / 4) for label, total in target_counts.items())

    return min(candidates, key=score)


def _model() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("classifier", RandomForestClassifier(
            n_estimators=600,
            max_features="sqrt",
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=RANDOM_SEED,
            n_jobs=-1,
        )),
    ])


def _select_threshold(labels: np.ndarray, probabilities: np.ndarray, minimum_recall: float = 0.95) -> float:
    candidates = sorted({0.05, 0.95, *np.round(probabilities, 6)})
    eligible = []
    for threshold in candidates:
        predictions = (probabilities >= threshold).astype(int)
        recall = recall_score(labels, predictions, pos_label=1, zero_division=0)
        specificity = recall_score(labels, predictions, pos_label=0, zero_division=0)
        if recall >= minimum_recall:
            eligible.append((specificity, threshold))
    if not eligible:
        return 0.5
    return float(max(eligible, key=lambda item: (item[0], item[1]))[1])


def _wilson(successes: int, total: int, z: float = 1.96) -> list[float | None]:
    if total == 0:
        return [None, None]
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    margin = z * ((rate * (1 - rate) / total + z * z / (4 * total * total)) ** 0.5) / denominator
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def _metrics(labels: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict[str, object]:
    predictions = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return {
        "threshold": round(threshold, 6),
        "accuracy": round(float(accuracy_score(labels, predictions)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(labels, predictions)), 4),
        "noise_precision": round(float(precision_score(labels, predictions, pos_label=1, zero_division=0)), 4),
        "noise_recall": round(float(recall_score(labels, predictions, pos_label=1, zero_division=0)), 4),
        "noise_recall_wilson_95_ci": _wilson(int(tp), int(tp + fn)),
        "acceptable_specificity": round(float(tn / (tn + fp)), 4) if tn + fp else None,
        "acceptable_specificity_wilson_95_ci": _wilson(int(tn), int(tn + fp)),
        "noise_f1": round(float(f1_score(labels, predictions, pos_label=1, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(labels, probabilities)), 4),
        "average_precision": round(float(average_precision_score(labels, probabilities)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def _triage_counts(
    labels: np.ndarray,
    probabilities: np.ndarray,
    review_threshold: float,
    noise_threshold: float,
) -> dict[str, dict[str, int]]:
    result = {
        "acceptable": {"pass": 0, "needs_review": 0, "high_noise": 0},
        "noise": {"pass": 0, "needs_review": 0, "high_noise": 0},
    }
    for label, probability in zip(labels, probabilities, strict=True):
        actual = "noise" if label else "acceptable"
        zone = (
            "high_noise" if probability >= noise_threshold
            else "needs_review" if probability >= review_threshold
            else "pass"
        )
        result[actual][zone] += 1
    return result


def _write_split_zip(path: Path, samples: list[Sample], split: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = io.StringIO()
    writer = csv.writer(manifest, lineterminator="\n")
    writer.writerow(["path", "label", "sha256", "group_hash"])
    used_names: set[str] = set()
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for sample in sorted(samples, key=lambda item: (item.label_name, item.sha256)):
            base = PurePosixPath(sample.archive_name).name
            if base.lower() in used_names:
                base = f"{sample.sha256[:8]}_{base}"
            used_names.add(base.lower())
            destination = f"{split}/{sample.label_name}/{base}"
            archive.writestr(destination, sample.content)
            writer.writerow([destination, sample.label_name, sample.sha256, sample.group_hash])
        archive.writestr(f"{split}/manifest.csv", manifest.getvalue().encode("utf-8"))


def train(
    source_zip: Path,
    artifacts_dir: Path,
    training_zip: Path,
    testing_zip: Path,
) -> dict[str, object]:
    samples, excluded = _load_samples(source_zip)
    labels = np.asarray([sample.label for sample in samples], dtype=int)
    groups = np.asarray([sample.group_hash for sample in samples])
    features = pd.DataFrame([sample.features for sample in samples], columns=FEATURE_NAMES)
    train_index, test_index = _choose_test_fold(labels, groups)
    if set(groups[train_index]) & set(groups[test_index]):
        raise RuntimeError("Sample-group leakage detected between train and test")

    x_train, x_test = features.iloc[train_index], features.iloc[test_index]
    y_train, y_test = labels[train_index], labels[test_index]
    train_groups = groups[train_index]
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    pipeline = _model()
    oof_probabilities = cross_val_predict(
        pipeline,
        x_train,
        y_train,
        groups=train_groups,
        cv=cv,
        method="predict_proba",
        n_jobs=1,
    )[:, 1]
    threshold = _select_threshold(y_train, oof_probabilities)
    review_threshold = _select_threshold(y_train, oof_probabilities, minimum_recall=1.0)
    pipeline.fit(x_train, y_train)
    test_probabilities = pipeline.predict_proba(x_test)[:, 1]

    training_samples = [samples[index] for index in train_index]
    testing_samples = [samples[index] for index in test_index]
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / "noise_qc_random_forest.joblib"
    metadata_path = artifacts_dir / "noise_qc_metadata.json"
    evaluation_path = artifacts_dir / "noise_qc_evaluation.json"
    manifest_path = artifacts_dir / "noise_qc_split_manifest.csv"
    joblib.dump(pipeline, model_path)

    classifier = pipeline.named_steps["classifier"]
    feature_importance = sorted(
        ({"feature": name, "importance": round(float(value), 6)}
         for name, value in zip(FEATURE_NAMES, classifier.feature_importances_, strict=True)),
        key=lambda item: item["importance"],
        reverse=True,
    )
    test_predictions = [
        {
            "sha256": sample.sha256,
            "group_hash": sample.group_hash,
            "actual": sample.label_name,
            "noise_probability": round(float(probability), 6),
            "predicted": "noise" if probability >= threshold else "acceptable",
            "triage": (
                "high_noise" if probability >= threshold
                else "needs_review" if probability >= review_threshold
                else "pass"
            ),
        }
        for sample, probability in sorted(
            zip(testing_samples, test_probabilities, strict=True),
            key=lambda item: item[0].sha256,
        )
    ]
    evaluation = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_zip_sha256": _sha256(source_zip.read_bytes()),
        "random_seed": RANDOM_SEED,
        "split_strategy": "StratifiedGroupKFold 4-way holdout; groups derived from specimen token",
        "cross_validation": "5-fold StratifiedGroupKFold on training split",
        "counts": {
            "source_eligible": dict(sorted(Counter(sample.label_name for sample in samples).items())),
            "excluded": dict(sorted(excluded.items())),
            "training": dict(sorted(Counter(sample.label_name for sample in training_samples).items())),
            "testing": dict(sorted(Counter(sample.label_name for sample in testing_samples).items())),
            "training_groups": len(set(groups[train_index])),
            "testing_groups": len(set(groups[test_index])),
        },
        "oof_training_metrics": _metrics(y_train, oof_probabilities, threshold),
        "independent_test_metrics": _metrics(y_test, test_probabilities, threshold),
        "conservative_review_operating_point": _metrics(
            y_test, test_probabilities, review_threshold
        ),
        "independent_test_triage": _triage_counts(
            y_test,
            test_probabilities,
            review_threshold,
            threshold,
        ),
        "feature_importance": feature_importance,
        "independent_test_predictions": test_predictions,
        "limitations": [
            "Research-only proof of concept; not clinically validated.",
            "Noise labels are inherited from the source folder and require specialist audit.",
            "The independent noise test set is small, so confidence intervals are wide.",
            "A low-risk prediction does not prove that an AB1 trace is clinically acceptable.",
        ],
    }
    metadata = {
        "model_name": "GeneGlass Noise QC Random Forest",
        "model_type": "binary_trace_quality_gate",
        "classes": {"0": "acceptable", "1": "noise"},
        "noise_probability_threshold": threshold,
        "review_probability_threshold": review_threshold,
        "features": FEATURE_NAMES,
        "random_seed": RANDOM_SEED,
        "training_samples": len(training_samples),
        "test_samples": len(testing_samples),
        "research_use_only": True,
        "model_sha256": _sha256(model_path.read_bytes()),
        "evaluation_file": evaluation_path.name,
        "limitations": evaluation["limitations"],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    evaluation_path.write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")

    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sha256", "label", "split", "group_hash"])
        for split, selected in (("training", training_samples), ("testing", testing_samples)):
            for sample in sorted(selected, key=lambda item: item.sha256):
                writer.writerow([sample.sha256, sample.label_name, split, sample.group_hash])

    _write_split_zip(training_zip, training_samples, "Training")
    _write_split_zip(testing_zip, testing_samples, "Testing")
    return {
        "model": str(model_path),
        "metadata": str(metadata_path),
        "evaluation": str(evaluation_path),
        "manifest": str(manifest_path),
        "training_zip": str(training_zip),
        "testing_zip": str(testing_zip),
        "test_metrics": evaluation["independent_test_metrics"],
        "counts": evaluation["counts"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--artifacts-dir", type=Path, default=Path("ai_assets"))
    parser.add_argument("--training-zip", type=Path, required=True)
    parser.add_argument("--testing-zip", type=Path, required=True)
    args = parser.parse_args()
    result = train(
        args.source_zip.resolve(),
        args.artifacts_dir.resolve(),
        args.training_zip.resolve(),
        args.testing_zip.resolve(),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
