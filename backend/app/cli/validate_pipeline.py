"""Command-line entry point for offline reference-dataset validation."""

import argparse
import json
from pathlib import Path

from app.validation.reference_dataset import (
    ManifestError,
    run_reference_validation,
    write_validation_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run non-diagnostic technical validation against a private AB1 "
            "reference manifest"
        )
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_reference_validation(args.manifest)
        if args.output:
            destination = write_validation_report(report, args.output)
            print(f"Validation report written to {destination}")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    except (ManifestError, FileExistsError) as exc:
        print(f"Validation could not run: {exc}")
        return 2
    return 0 if report["summary"]["processing_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
