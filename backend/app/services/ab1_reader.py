
"""Read DNA sequence, quality scores, and chromatogram from AB1 files."""

from pathlib import Path
from typing import Any

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord


def read_ab1_file(file_path: str | Path) -> dict[str, Any]:
    """Extract sequencing data from an AB1 file."""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"AB1 file not found: {path.name}")

    record: SeqRecord | None = SeqIO.read(str(path), "abi")

    sequence = str(record.seq)
    quality_scores = record.letter_annotations.get("phred_quality", [])

    chromatogram = record.annotations.get("abif_raw", {})

    channels = {
        "A": chromatogram.get("DATA10", []),
        "C": chromatogram.get("DATA12", []),
        "G": chromatogram.get("DATA9", []),
        "T": chromatogram.get("DATA11", []),
    }

    return {
        "file_name": path.name,
        "sequence": sequence,
        "sequence_length": len(sequence),
        "quality_scores": quality_scores,
        "average_quality": (
            round(sum(quality_scores) / len(quality_scores), 2)
            if quality_scores
            else None
        ),
        "chromatogram": channels,
        "base_positions": record.annotations.get("abif_raw", {}).get(
            "PLOC2", []
        ),
    }
