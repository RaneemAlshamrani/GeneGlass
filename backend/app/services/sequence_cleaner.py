
"""Quality-based cleaning and quality control utilities for Sanger DNA sequences."""

from typing import Any


DEFAULT_QUALITY_THRESHOLD = 20


def clean_sequence(
    sequence: str,
    quality_scores: list[int],
    quality_threshold: int = DEFAULT_QUALITY_THRESHOLD,
) -> dict[str, Any]:
    """Clean a DNA sequence and calculate basic quality metrics."""

    if len(sequence) != len(quality_scores):
        raise ValueError(
            "Sequence length must match the number of quality scores."
        )

    if not 0 <= quality_threshold <= 93:
        raise ValueError("Quality threshold must be between 0 and 93.")

    if any(not 0 <= score <= 93 for score in quality_scores):
        raise ValueError("Quality scores must be between 0 and 93.")

    clean_bases = []
    low_quality_positions = []
    retained_positions = []

    for index, (base, quality) in enumerate(zip(sequence, quality_scores)):
        if quality < quality_threshold:
            low_quality_positions.append(index)
        else:
            clean_bases.append(base)
            retained_positions.append(index)

    original_length = len(sequence)
    low_quality_count = len(low_quality_positions)
    retained_count = len(retained_positions)

    average_quality = (
        round(sum(quality_scores) / original_length, 2)
        if original_length
        else None
    )

    minimum_quality = min(quality_scores) if quality_scores else None
    maximum_quality = max(quality_scores) if quality_scores else None

    low_quality_percentage = (
        round((low_quality_count / original_length) * 100, 2)
        if original_length
        else 0
    )

    retained_percentage = (
        round((retained_count / original_length) * 100, 2)
        if original_length
        else 0
    )

    if average_quality is None:
        quality_assessment = "unavailable"
    elif average_quality >= 30:
        quality_assessment = "good"
    elif average_quality >= 20:
        quality_assessment = "moderate"
    else:
        quality_assessment = "poor"

    return {
        "original_length": original_length,
        "cleaned_length": retained_count,
        "cleaned_sequence": "".join(clean_bases),
        "quality_threshold": quality_threshold,
        "average_quality": average_quality,
        "minimum_quality": minimum_quality,
        "maximum_quality": maximum_quality,
        "low_quality_count": low_quality_count,
        "low_quality_percentage": low_quality_percentage,
        "retained_count": retained_count,
        "retained_percentage": retained_percentage,
        "quality_assessment": quality_assessment,
        "low_quality_positions": low_quality_positions,
        "retained_positions": retained_positions,
    }
