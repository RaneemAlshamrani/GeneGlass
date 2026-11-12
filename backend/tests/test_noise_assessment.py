"""Tests for an observational noise assessment that must not change input traces."""
from copy import deepcopy
from app.services.noise_assessment import assess_target_noise


def test_noise_assessment_is_descriptive_and_does_not_mutate():
    trace = {b: [0] * 30 for b in "ACGT"}
    for i in (5, 10, 15, 20, 25):
        trace["G"][i] = 100
        trace["A"][i] = 8
    trace["T"][15] = 90  # Legitimate target second peak must NOT auto-reject.
    original = deepcopy(trace)
    result = assess_target_noise(
        base_index=2, sequence="GGGGG", quality_scores=[34] * 5,
        base_positions=[5, 10, 15, 20, 25], channels=trace, flank_bases=2,
    )
    assert result["available"] is True
    assert result["status"] == "Unassessed"
    assert result["target_ab1_base_number"] == 3
    assert result["mean_flank_secondary_ratio"] == 0.08
    assert trace == original


def test_missing_channels_fails_safely():
    result = assess_target_noise(
        base_index=0, sequence="A", quality_scores=[20],
        base_positions=[0], channels={"A": [10]},
    )
    assert result["available"] is False
