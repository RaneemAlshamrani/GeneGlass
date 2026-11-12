"""Research-only screen for a predominantly alternative JAK2 V617F target trace.

This is an advisory, NOT a genotype call or clinical classifier. Does not
modify AB1 traces, the binary Random Forest inputs, or stored QC status.
"""
from __future__ import annotations

from typing import Any


# Provisional *screening* parameters, NOT clinically validated cutoffs.
MIN_TARGET_PHRED = 20
MIN_ALIGNMENT_IDENTITY_PERCENT = 80.0
MIN_READ_COVERAGE_PERCENT = 50.0
MAX_COMPETING_PEAK_TO_ALT_RATIO = 0.15


def assess_unsupported_target_pattern(*, target: dict, peaks: dict) -> dict[str, Any]:
    """Suggest specialist review when the raw alternate signal overwhelmingly dominates.

    Forward reference G>T: raw G (reference), T (alternative).
    Reverse complement: raw C (reference), A (alternative).
    A single dominant alternative signal may also be an artifact or another
    biological pattern; it DOES NOT establish homozygosity.
    """
    result: dict[str, Any] = {
        "available": False,
        "review_recommended": False,
        "status": "Unassessed",
        "reason": "Target signal not yet assessed.",
        "note": "Research-only advisory. Not a homozygous genotype determination.",
    }
    if not target.get("found"):
        result["reason"] = "JAK2 target could not be mapped."
        return result

    direction = target.get("direction")
    if direction == "Forward":
        ref, alt = "G", "T"
    elif direction == "Reverse":
        ref, alt = "C", "A"
    else:
        result["reason"] = "Unknown read orientation."
        return result

    try:
        quality = float(target["quality_score"])
        identity = float(target["alignment_identity_percentage"])
        coverage = float(target["alignment_coverage_percentage"])
        values = {base: float(peaks["peak_heights"][base]) for base in "ACGT"}
    except (KeyError, TypeError, ValueError, OverflowError):
        result["reason"] = "Required target quality or raw peak data unavailable."
        return result
    if any(v < 0 or not (v < float("inf")) for v in values.values()):
        result["reason"] = "Invalid raw peak intensities."
        return result
    if values[alt] <= 0:
        result["reason"] = "Alternative-allele signal is absent."
        return result

    competing = max(values[base] for base in "ACGT" if base != alt)
    ratio = competing / values[alt]
    result.update({
        "available": True,
        "status": "Measured",
        "direction": direction,
        "raw_reference_channel": ref,
        "raw_alternative_channel": alt,
        "raw_reference_peak": values[ref],
        "raw_alternative_peak": values[alt],
        "max_other_to_alternative_ratio": round(ratio, 4),
        "target_phred": quality,
        "reason": "Target peak metrics displayed for manual specialist inspection.",
    })

    # Guard against unsupported conclusions from poor mapping or low-quality calls.
    eligible = (
        quality >= MIN_TARGET_PHRED
        and identity >= MIN_ALIGNMENT_IDENTITY_PERCENT
        and coverage >= MIN_READ_COVERAGE_PERCENT
    )
    if eligible and ratio <= MAX_COMPETING_PEAK_TO_ALT_RATIO:
        result.update({
            "review_recommended": True,
            "status": "Possible unsupported target pattern",
            "reason": (
                "Predominantly alternative-allele signal at JAK2 V617F. "
                "The Negative/Hetero model does not classify this pattern; "
                "specialist verification is needed."
            ),
        })
    return result
