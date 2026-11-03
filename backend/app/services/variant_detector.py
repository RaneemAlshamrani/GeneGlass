"""Reference utilities for JAK2 variant detection."""

from pathlib import Path

from Bio import SeqIO
from Bio.Align import PairwiseAligner
from Bio.Seq import Seq

REFERENCE_PATH = (
    Path(__file__).resolve().parents[2]
    / "references"
    / "JAK2_NM_004972.4.fasta"
)

JAK2_V617F_CDNA_POSITION = 1849
JAK2_CDS_START = 468
JAK2_V617F_REFERENCE_POSITION = JAK2_CDS_START + JAK2_V617F_CDNA_POSITION - 1
JAK2_V617F_REFERENCE_INDEX = JAK2_V617F_REFERENCE_POSITION - 1

# Conservative preliminary alignment screening limits, not clinical cutoffs.
MIN_ALIGNMENT_IDENTITY_PERCENT = 80.0
MIN_ALIGNMENT_READ_COVERAGE_PERCENT = 50.0


def load_jak2_reference() -> str:
    """Load the complete JAK2 reference sequence without trimming."""
    record = SeqIO.read(REFERENCE_PATH, "fasta")

    if record.id != "NM_004972.4":
        raise ValueError("Unexpected JAK2 reference accession")

    return str(record.seq).upper()


def get_jak2_target() -> dict:
    """Return the reference nucleotide at JAK2 c.1849."""
    sequence = load_jak2_reference()

    # c.1849 is a coding-DNA position, not a FASTA index.
    # We will map it using the verified CDS annotation next.
    return {
        "reference": "NM_004972.4",
        "sequence_length": len(sequence),
        "cdna_position": JAK2_V617F_CDNA_POSITION,
        "reference_sequence": sequence,
    }


def align_ab1_to_jak2(ab1_sequence: str) -> dict:
    """Align the original AB1 sequence to JAK2 in both orientations."""
    reference = load_jak2_reference()
    sequence = ab1_sequence.upper()

  
    if not sequence:
        raise ValueError("AB1 sequence is empty")

    if len(sequence) < 50:
        raise ValueError(
            "Sequence is too short for reliable alignment. Needs Review."
        )

    

    aligner = PairwiseAligner()
    aligner.mode = "local"
    aligner.match_score = 2
    aligner.mismatch_score = -3
    aligner.open_gap_score = -5
    aligner.extend_gap_score = -1

    forward = aligner.align(reference, sequence)[0]

    reverse_sequence = str(Seq(sequence).reverse_complement())
    reverse = aligner.align(reference, reverse_sequence)[0]

    if forward.score >= reverse.score:
        best = forward
        direction = "Forward"
    else:
        best = reverse
        direction = "Reverse"
    
    aligned_reference, aligned_read = best.indices

    compared_positions = 0
    matching_positions = 0

    for ref_index, read_index in zip(aligned_reference, aligned_read):
        if ref_index == -1 or read_index == -1:
            continue

        compared_positions += 1

        if reference[ref_index] == (
            sequence if direction == "Forward" else reverse_sequence
        )[read_index]:
            matching_positions += 1

    identity_percentage = (
        round(matching_positions / compared_positions * 100, 2)
        if compared_positions else 0.0
    )
    aligned_read_positions = {
        int(read_index)
        for read_index in aligned_read
        if read_index != -1
    }

    coverage_percentage = round(
        len(aligned_read_positions) / len(sequence) * 100, 2
    )
    
    return {
        "direction": direction,
        "alignment_score": float(best.score),
        "reference_positions": best.aligned[0].tolist(),
        "read_positions": best.aligned[1].tolist(),
        "identity_percentage": identity_percentage,
        "coverage_percentage": coverage_percentage,
    }

def find_jak2_v617f_position(ab1_sequence: str) -> dict:
    """Map the JAK2 V617F reference position to an AB1 base index."""
    result = align_ab1_to_jak2(ab1_sequence)

    reference_index = JAK2_V617F_REFERENCE_INDEX
    read_length = len(ab1_sequence)

    for ref_block, read_block in zip(
        result["reference_positions"],
        result["read_positions"],
    ):
        ref_start, ref_end = ref_block
        read_start, read_end = read_block

        if ref_start <= reference_index < ref_end:
            offset = reference_index - ref_start

            # Aligned blocks contain corresponding bases.
            oriented_index = read_start + offset

            if result["direction"] == "Reverse":
                original_index = read_length - 1 - oriented_index
            else:
                original_index = oriented_index



            observed_base = ab1_sequence[original_index].upper()

            if result["direction"] == "Reverse":
                observed_base = str(
                    Seq(observed_base).complement()
                )

            return {
                "found": True,
                "direction": result["direction"],
                "reference_position": JAK2_V617F_REFERENCE_POSITION,
                "ab1_base_index": original_index,
                "ab1_base_number": original_index + 1,
                "observed_base": observed_base,
                "alignment_identity_percentage": result["identity_percentage"],
                "alignment_coverage_percentage": result["coverage_percentage"],
                "needs_review": observed_base not in "ACGT",
            }


    return {
        "found": False,
        "direction": result["direction"],
        "reference_position": JAK2_V617F_REFERENCE_POSITION,
        "ab1_base_index": None,
        "ab1_base_number": None,
        "alignment_identity_percentage": result["identity_percentage"],
        "alignment_coverage_percentage": result["coverage_percentage"],
        "reason": "Target position is not covered by the alignment.",
    }

def check_target_quality(
    ab1_base_index: int,
    quality_scores: list[int],
) -> dict:
    """Read the Phred quality at the mapped target position."""

    if not 0 <= ab1_base_index < len(quality_scores):
        return {
            "quality_score": None,
            "quality_status": "unavailable",
            "needs_review": True,
        }

    
    quality = int(quality_scores[ab1_base_index])
    quality_threshold = 20  # Preliminary QC threshold

    if quality < quality_threshold:
        quality_assessment = "low"
        requires_quality_review = True
    else:
        quality_assessment = "acceptable_preliminary"
        requires_quality_review = False

    return {
        "quality_score": quality,
        "quality_status": "available",
        "quality_assessment": quality_assessment,
        "needs_review": requires_quality_review,
    }

def analyze_jak2_target(
    ab1_sequence: str,
    quality_scores: list[int],
) -> dict:
    """Combine JAK2 target mapping with Phred quality."""

    position_result = find_jak2_v617f_position(ab1_sequence)

    if not position_result["found"]:
        return {
            **position_result,
            "needs_review": True,
            "quality_score": None,
            "reason": position_result.get(
                "reason", "Target position not found."
            ),
        }

    quality_result = check_target_quality(
        position_result["ab1_base_index"],
        quality_scores,
    )

    return {
        **position_result,
        "quality_score": quality_result["quality_score"],
        "quality_assessment": quality_result["quality_assessment"]
        if "quality_assessment" in quality_result
        else "unavailable",
        "needs_review": (
            position_result["needs_review"]
            or quality_result["needs_review"]
        ),
    }

def analyze_target_peaks(
    base_index: int,
    base_positions: list[int],
    channels: dict,
) -> dict:
    """Inspect fluorescence peaks at the target base."""

    if not 0 <= base_index < len(base_positions):
        return {
            "needs_review": True,
            "reason": "Target peak position is unavailable.",
        }

    peak_position = int(base_positions[base_index])

    heights = {}
    for base in "ACGT":
        trace = channels.get(base, [])
        if not 0 <= peak_position < len(trace):
            return {
                "needs_review": True,
                "reason": "Incomplete chromatogram channels.",
            }
        heights[base] = int(trace[peak_position])

    ranked = sorted(
        heights.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    primary_base, primary_height = ranked[0]
    secondary_base, secondary_height = ranked[1]

    overlap_ratio = (
        round(secondary_height / primary_height, 3)
        if primary_height > 0 else None
    )

    return {
        "peak_position": peak_position,
        "peak_heights": heights,
        "primary_base": primary_base,
        "secondary_base": secondary_base,
        "overlap_ratio": overlap_ratio,
        "needs_review": overlap_ratio is None,
    }

def analyze_target_region(
    base_index: int,
    sequence: str,
    base_positions: list[int],
    channels: dict,
    flank_bases: int = 5,
) -> dict:
    """Describe the target and neighboring AB1 peaks; do not classify a variant.

    Peak heights are sampled at each original AB1 base-call position.
    These are descriptive measurements, not validated mutation evidence.
    """
    if not 0 <= base_index < len(sequence):
        return {"available": False, "reason": "Target base is unavailable."}

    start = max(0, base_index - flank_bases)
    end = min(len(sequence), base_index + flank_bases + 1)
    if len(base_positions) < end:
        return {"available": False, "reason": "Target-region peak positions are incomplete."}

    region = []
    for index in range(start, end):
        sample = int(base_positions[index])
        heights = {}
        for base in "ACGT":
            trace = channels.get(base, [])
            if sample < 0 or sample >= len(trace):
                return {"available": False, "reason": "Target-region trace channels are incomplete."}
            heights[base] = int(trace[sample])

        ranked = sorted(heights, key=heights.get, reverse=True)
        primary = heights[ranked[0]]
        secondary = heights[ranked[1]]
        region.append({
            "ab1_base_number": index + 1,
            "called_base": sequence[index].upper(),
            "peak_position": sample,
            "peak_heights": heights,
            "primary_base": ranked[0],
            "secondary_base": ranked[1],
            "secondary_to_primary_ratio": round(secondary / primary, 3) if primary > 0 else None,
            "is_target": index == base_index,
        })

    return {
        "available": True,
        "target_ab1_base_number": base_index + 1,
        "window_start_ab1_base_number": start + 1,
        "window_end_ab1_base_number": end,
        "region_sequence": sequence[start:end].upper(),
        "bases": region,
        "interpretation": "Descriptive target-region signal measurements only; no mutation classification.",
    }


def analyze_jak2_chromatogram(data: dict) -> dict:
    """Combine target mapping, Phred quality, and peak analysis."""

    result = analyze_jak2_target(
        data["sequence"],
        data["quality_scores"],
    )

    if not result["found"]:
        return {
            **result,
            "target_region": {"available": False, "reason": result.get("reason", "Target not mapped.")},
            "review_reasons": [result.get("reason", "Target position could not be mapped.")],
            "review_status": "Needs Review",
        }

    peaks = analyze_target_peaks(
        result["ab1_base_index"],
        data["base_positions"],
        data["channels"],
    )

    region = analyze_target_region(
        result["ab1_base_index"],
        data["sequence"],
        data["base_positions"],
        data["channels"],
    )

    review_reasons = []
    identity = result.get("alignment_identity_percentage", 0.0)
    coverage = result.get("alignment_coverage_percentage", 0.0)
    if identity < MIN_ALIGNMENT_IDENTITY_PERCENT:
        review_reasons.append("JAK2 reference alignment has low sequence identity; verify the target mapping.")
    if coverage < MIN_ALIGNMENT_READ_COVERAGE_PERCENT:
        review_reasons.append("Only a small part of the AB1 read aligns to JAK2; verify the target mapping.")
    if result.get("quality_score") is None:
        review_reasons.append("Target base quality score is unavailable.")
    if result.get("observed_base") not in ("A", "C", "G", "T"):
        review_reasons.append("Target base call is ambiguous.")
    if peaks.get("needs_review"):
        review_reasons.append(peaks.get("reason", "Target peak data is unavailable."))
    if not region["available"]:
        review_reasons.append(region["reason"])

    return {
        **result,
        "peak_analysis": peaks,
        "target_region": region,
        "review_reasons": review_reasons,
        # Phred is shown for context, not used alone to flag the target.
        "needs_review": bool(review_reasons),
        "review_status": "Needs Review" if review_reasons else "No QC Review Flag",
    }


