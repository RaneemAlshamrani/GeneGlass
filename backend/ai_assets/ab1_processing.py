
import numpy as np
from pathlib import Path
from Bio import SeqIO, Align
from Bio.Seq import Seq

reference_seq = (
    Path(__file__).with_name("jak2_reference.txt")
    .read_text(encoding="utf-8")
    .strip()
)

mutation_idx = 300

aligner = Align.PairwiseAligner()
aligner.mode = "local"
aligner.match_score = 2
aligner.mismatch_score = -3
aligner.open_gap_score = -5
aligner.extend_gap_score = -1

def extract_features(file_path):
    record = SeqIO.read(str(file_path), "abi")
    sequence = str(record.seq).upper()

    # Align both orientations
    forward = aligner.align(reference_seq, sequence)[0]

    reverse_sequence = str(
        Seq(sequence).reverse_complement()
    )
    reverse = aligner.align(
        reference_seq, reverse_sequence
    )[0]

    if forward.score >= reverse.score:
        best = forward
        orientation = "Forward"
    else:
        best = reverse
        orientation = "Reverse"

    # Locate the mutation in the original AB1 read
    ref_indices, read_indices = best.indices

    positions = read_indices[
        ref_indices == mutation_idx
    ]

    positions = positions[positions >= 0]

    if len(positions) != 1:
        raise ValueError(
            "Mutation position could not be mapped"
        )

    read_pos = int(positions[0])

    if orientation == "Reverse":
        original_pos = len(sequence) - 1 - read_pos
        ref_base, alt_base = "C", "A"
    else:
        original_pos = read_pos
        ref_base, alt_base = "G", "T"

    raw = record.annotations["abif_raw"]

    # Locate peak position in chromatogram
    center = int(raw["PLOC2"][original_pos])

    dye_order = raw["FWO_1"].decode("ascii")
    channels = {
        base: np.asarray(raw[f"DATA{9+i}"], dtype=float)
        for i, base in enumerate(dye_order)
    }

    # Peak intensities around mutation
    left = max(0, center - 3)
    right = min(len(channels["G"]), center + 4)

    reference_peak = float(
        channels[ref_base][left:right].max()
    )
    alternative_peak = float(
        channels[alt_base][left:right].max()
    )

    total = reference_peak + alternative_peak

    alternative_ratio = (
        alternative_peak / total if total > 0 else 0.0
    )

    # Local background signal from the other channels
    other_bases = [
        b for b in "GATC"
        if b not in [ref_base, alt_base]
    ]

    background = np.mean([
        channels[b][left:right].mean()
        for b in other_bases
    ])

    local_noise_ratio = float(
        background / max(reference_peak, alternative_peak, 1)
    )

    peak_overlap_score = float(
        min(reference_peak, alternative_peak)
        / max(reference_peak, alternative_peak, 1)
    )

    qualities = record.letter_annotations.get(
        "phred_quality", []
    )

    phred_quality = (
        float(qualities[original_pos])
        if len(qualities) > original_pos
        else np.nan
    )

    return {
        "orientation": orientation,
        "alignment_score": float(best.score),
        "reference_peak": reference_peak,
        "alternative_peak": alternative_peak,
        "alternative_ratio": alternative_ratio,
        "phred_quality": phred_quality,
        "peak_overlap_score": peak_overlap_score,
        "local_noise_ratio": local_noise_ratio
    }
