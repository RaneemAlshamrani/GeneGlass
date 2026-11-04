"""Regression tests for JAK2 reference mapping and peak evidence."""

from app.services.variant_detector import (
    JAK2_V617F_REFERENCE_INDEX,
    analyze_jak2_chromatogram,
    extract_jak2_candidate_snvs,
    load_jak2_reference,
)

def test_jak2_reference_target_is_reference_g() -> None:
    reference = load_jak2_reference()

    assert reference[JAK2_V617F_REFERENCE_INDEX] == "G"


def build_synthetic_target_trace() -> dict:
    reference = load_jak2_reference()
    start = JAK2_V617F_REFERENCE_INDEX - 100
    sequence = reference[start : JAK2_V617F_REFERENCE_INDEX + 101]
    base_positions = [index * 2 for index in range(len(sequence))]
    trace_length = base_positions[-1] + 2
    channels = {base: [5] * trace_length for base in "ACGT"}

    for index, base in enumerate(sequence):
        channels[base][base_positions[index]] = 1000

    return {
        "sequence": sequence,
        "quality_scores": [40] * len(sequence),
        "base_positions": base_positions,
        "channels": channels,
    }


def test_synthetic_reference_read_maps_target_and_peak_details() -> None:
    trace = build_synthetic_target_trace()

    result = analyze_jak2_chromatogram(trace)

    assert result["found"] is True
    assert result["direction"] == "Forward"
    assert isinstance(result["ab1_base_number"], int)
    assert result["observed_base"] in {"A", "C", "G", "T"}
    assert result["alignment_identity_percentage"] == 100
    assert result["alignment_coverage_percentage"] == 100
    assert result["quality_score"] is not None

    peaks = result["peak_analysis"]
    assert set(peaks["peak_heights"]) == {"A", "C", "G", "T"}
    assert peaks["primary_base"] in {"A", "C", "G", "T"}
    assert peaks["secondary_base"] in {"A", "C", "G", "T"}

    region = result["target_region"]
    assert region["available"] is True
    assert any(base["is_target"] for base in region["bases"])
    assert result["review_status"] in {
        "Needs Review",
        "No QC Review Flag",
    }
    assert result["review_status"] == "No QC Review Flag"
    evidence = result["reference_evidence"]
    assert evidence["variation_id"] == 14662
    assert evidence["transcript"] == "NM_004972.4"
    assert evidence["hgvs_c"] == "c.1849G>T"
    assert evidence["url"].startswith("https://www.ncbi.nlm.nih.gov/clinvar/")


def test_extracts_high_quality_v617f_as_research_candidate() -> None:
    trace = build_synthetic_target_trace()
    sequence = list(trace["sequence"])
    sequence[100] = "T"
    trace["sequence"] = "".join(sequence)

    candidates = extract_jak2_candidate_snvs(trace)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["hgvs"] == "NM_004972.4:c.1849G>T"
    assert candidate["reference_allele"] == "G"
    assert candidate["observed_allele"] == "T"
    assert candidate["phred_quality"] == 40
    assert candidate["lookup_eligible"] is True
    assert candidate["review_status"] == "Research Candidate"
