"""Tests for a non-diagnostic unsupported-pattern review advisory."""
from app.services.unsupported_target_pattern import assess_unsupported_target_pattern


def target(direction='Reverse', q=50, identity=97.88, coverage=97.52):
    return dict(found=True, direction=direction, quality_score=q,
                alignment_identity_percentage=identity,
                alignment_coverage_percentage=coverage)


def test_reverse_alternative_dominant_sample_flags():
    # Provided screenshot: A858 C33 G31 T11, reverse complement of G>T.
    result = assess_unsupported_target_pattern(target=target(),
        peaks={'peak_heights': {'A':858,'C':33,'G':31,'T':11}})
    assert result['review_recommended'] is True
    assert result['raw_alternative_channel'] == 'A'
    assert result['raw_reference_channel'] == 'C'


def test_forward_alternative_dominant_flags():
    result = assess_unsupported_target_pattern(target=target('Forward'),
        peaks={'peak_heights': {'A':11,'C':14,'G':30,'T':800}})
    assert result['review_recommended'] is True
    assert result['raw_alternative_channel'] == 'T'


def test_reference_dominant_does_not_flag():
    result = assess_unsupported_target_pattern(target=target(),
        peaks={'peak_heights': {'A':15,'C':800,'G':12,'T':10}})
    assert result['review_recommended'] is False


def test_mixed_peaks_do_not_flag():
    result = assess_unsupported_target_pattern(target=target(),
        peaks={'peak_heights': {'A':550,'C':470,'G':12,'T':10}})
    assert result['review_recommended'] is False


def test_low_quality_or_bad_alignment_does_not_flag():
    peaks={'peak_heights': {'A':858,'C':33,'G':31,'T':11}}
    assert not assess_unsupported_target_pattern(target=target(q=8), peaks=peaks)['review_recommended']
    assert not assess_unsupported_target_pattern(target=target(identity=70), peaks=peaks)['review_recommended']


def test_missing_data_fails_closed():
    result = assess_unsupported_target_pattern(target=target(), peaks={})
    assert result['available'] is False
    assert result['review_recommended'] is False
