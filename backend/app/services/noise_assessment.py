"""Research-only descriptive noise measurements around a mapped AB1 target.

Never alters trace arrays, model features, QC status, or prediction.
There are deliberately no severity cutoffs until separately validated.
"""
from __future__ import annotations

from typing import Any


def assess_target_noise(
    *,
    base_index: int,
    sequence: str,
    quality_scores: list[int],
    base_positions: list[int],
    channels: dict[str, list[int]],
    flank_bases: int = 5,
) -> dict[str, Any]:
    """Describe raw trace properties in a local +/- flank_bases window.

    Secondary peak signal at the mutation base can be genuine heterozygosity,
    so this routine DOES NOT label individual sites as noise.
    """
    if not 0 <= base_index < len(sequence):
        return {"available": False, "reason": "Target index is unavailable."}
    start = max(0, base_index - flank_bases)
    end = min(len(sequence), base_index + flank_bases + 1)
    if len(base_positions) < end or len(quality_scores) < end:
        return {"available": False, "reason": "Base positions or Phred scores incomplete."}
    if set(channels) < set("ACGT"):
        return {"available": False, "reason": "Trace channels incomplete."}

    points = []
    for idx in range(start, end):
        position = int(base_positions[idx])
        if position < 0 or any(position >= len(channels[b]) for b in "ACGT"):
            return {"available": False, "reason": "Trace positions outside channel arrays."}
        heights = sorted((max(0, int(channels[b][position])) for b in "ACGT"), reverse=True)
        maximum = heights[0]
        ratio = heights[1] / maximum if maximum > 0 else None
        points.append({
            "ab1_base_number": idx + 1,
            "phred": int(quality_scores[idx]),
            "secondary_to_primary_ratio": round(ratio, 4) if ratio is not None else None,
            "is_target": idx == base_index,
        })

    flank = [p for p in points if not p["is_target"]]
    flank_ratios = [p["secondary_to_primary_ratio"] for p in flank if p["secondary_to_primary_ratio"] is not None]
    flank_phred = [p["phred"] for p in flank]
    return {
        "available": True,
        "status": "Unassessed",  # No unvalidated Good/Mild/Severe threshold.
        "window_start_ab1_base_number": start + 1,
        "window_end_ab1_base_number": end,
        "target_ab1_base_number": base_index + 1,
        "mean_flank_secondary_ratio": round(sum(flank_ratios) / len(flank_ratios), 4) if flank_ratios else None,
        "min_flank_phred": min(flank_phred) if flank_phred else None,
        "mean_flank_phred": round(sum(flank_phred) / len(flank_phred), 2) if flank_phred else None,
        "points": points,
        "note": "Descriptive raw-trace QC only. Secondary peaks may be genuine mixed alleles; no validated noise severity decision is made.",
    }
