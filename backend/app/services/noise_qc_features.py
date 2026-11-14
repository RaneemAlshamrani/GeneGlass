"""Feature extraction for the research-only AB1 noise QC model.

The QC model deliberately uses trace-wide signal and quality measurements. It
does not use the filename, the JAK2 genotype prediction, or a smoothed trace.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from Bio import SeqIO


FEATURE_NAMES = [
    "sequence_length",
    "mean_phred",
    "median_phred",
    "phred_p10",
    "low_phred_fraction",
    "very_low_phred_fraction",
    "central_mean_phred",
    "central_low_phred_fraction",
    "primary_peak_median",
    "primary_peak_p10",
    "primary_peak_p99",
    "primary_peak_cv",
    "secondary_ratio_mean",
    "secondary_ratio_median",
    "secondary_ratio_p90",
    "secondary_ratio_p95",
    "secondary_ratio_gt_0_20_fraction",
    "secondary_ratio_gt_0_33_fraction",
    "tertiary_ratio_mean",
    "peak_spacing_mean",
    "peak_spacing_cv",
    "nonpositive_spacing_fraction",
    "ambiguous_base_fraction",
]


def _ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype=float),
        where=denominator > 0,
    )


def _coefficient_of_variation(values: np.ndarray) -> float:
    mean = float(np.mean(values))
    return float(np.std(values) / mean) if mean > 0 else 0.0


def extract_noise_qc_features(file_path: str | Path) -> dict[str, float]:
    """Extract deterministic, unsmoothed trace-wide QC features from one AB1."""
    record = SeqIO.read(str(file_path), "abi")
    sequence = str(record.seq).upper()
    qualities = np.asarray(record.letter_annotations.get("phred_quality", []), dtype=float)
    raw: dict[str, Any] = record.annotations.get("abif_raw", {})
    positions = np.asarray(raw.get("PLOC2", []), dtype=int)

    order = raw.get("FWO_1", b"GATC")
    if isinstance(order, bytes):
        order = order.decode("ascii", errors="strict")
    order = str(order).upper()
    if len(order) != 4 or set(order) != set("ACGT"):
        raise ValueError("Unsupported AB1 dye order")
    channels = {
        base: np.asarray(raw.get(f"DATA{9 + index}", []), dtype=float)
        for index, base in enumerate(order)
    }

    length = len(sequence)
    if length < 20 or len(qualities) != length or len(positions) != length:
        raise ValueError("Incomplete AB1 sequence, quality, or peak positions")
    trace_length = min((len(values) for values in channels.values()), default=0)
    if trace_length == 0 or np.any(positions < 0) or np.any(positions >= trace_length):
        raise ValueError("Invalid AB1 trace channels or peak positions")

    sampled = np.column_stack([channels[base][positions] for base in "ACGT"])
    ordered = np.sort(np.maximum(sampled, 0.0), axis=1)
    primary = ordered[:, 3]
    secondary = ordered[:, 2]
    tertiary = ordered[:, 1]
    secondary_ratio = _ratio(secondary, primary)
    tertiary_ratio = _ratio(tertiary, primary)
    spacing = np.diff(positions).astype(float)

    trim = max(10, int(round(length * 0.10)))
    central_slice = slice(trim, length - trim) if length > 2 * trim else slice(0, length)
    central_qualities = qualities[central_slice]

    result = {
        "sequence_length": float(length),
        "mean_phred": float(np.mean(qualities)),
        "median_phred": float(np.median(qualities)),
        "phred_p10": float(np.percentile(qualities, 10)),
        "low_phred_fraction": float(np.mean(qualities < 20)),
        "very_low_phred_fraction": float(np.mean(qualities < 10)),
        "central_mean_phred": float(np.mean(central_qualities)),
        "central_low_phred_fraction": float(np.mean(central_qualities < 20)),
        "primary_peak_median": float(np.median(primary)),
        "primary_peak_p10": float(np.percentile(primary, 10)),
        "primary_peak_p99": float(np.percentile(primary, 99)),
        "primary_peak_cv": _coefficient_of_variation(primary),
        "secondary_ratio_mean": float(np.mean(secondary_ratio)),
        "secondary_ratio_median": float(np.median(secondary_ratio)),
        "secondary_ratio_p90": float(np.percentile(secondary_ratio, 90)),
        "secondary_ratio_p95": float(np.percentile(secondary_ratio, 95)),
        "secondary_ratio_gt_0_20_fraction": float(np.mean(secondary_ratio > 0.20)),
        "secondary_ratio_gt_0_33_fraction": float(np.mean(secondary_ratio > 0.33)),
        "tertiary_ratio_mean": float(np.mean(tertiary_ratio)),
        "peak_spacing_mean": float(np.mean(spacing)),
        "peak_spacing_cv": _coefficient_of_variation(np.abs(spacing)),
        "nonpositive_spacing_fraction": float(np.mean(spacing <= 0)),
        "ambiguous_base_fraction": float(sum(base not in "ACGT" for base in sequence) / length),
    }
    if list(result) != FEATURE_NAMES:
        raise RuntimeError("Noise QC feature order changed unexpectedly")
    if not all(np.isfinite(value) for value in result.values()):
        raise ValueError("Non-finite AB1 QC feature")
    return result
