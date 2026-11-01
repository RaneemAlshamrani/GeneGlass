
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


# chromatogram-viewer-v1

def read_chromatogram(file_path: str | Path) -> dict[str, Any]:
    """Read raw fluorescence traces using the AB1 dye/base order (FWO_1)."""
    record = SeqIO.read(str(file_path), "abi")
    raw = record.annotations.get("abif_raw", {})
    order = raw.get("FWO_1", b"GATC")
    if isinstance(order, bytes):
        order = order.decode("ascii", errors="replace")
    order = str(order).upper()
    if len(order) != 4 or set(order) != set("ACGT"):
        raise ValueError("Unsupported AB1 dye order")
    traces = {base: list(raw.get(f"DATA{9+i}", [])) for i, base in enumerate(order)}
    positions = [int(x) for x in raw.get("PLOC2", [])]
    sequence = str(record.seq)
    quality = [int(x) for x in record.letter_annotations.get("phred_quality", [])]
    if not all(traces.values()) or len(positions) != len(sequence) or len(quality) != len(sequence):
        raise ValueError("Incomplete AB1 chromatogram data")
    if any(p < 0 or p >= len(next(iter(traces.values()))) for p in positions):
        raise ValueError("Invalid AB1 peak positions")
    return {"sequence": sequence, "quality_scores": quality,
            "base_positions": positions, "channels": traces, "dye_order": order}
