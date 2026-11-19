"""Command-line interface for ethio-procurement-ocds-auditor."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from auditor.ocds_mapper import CSVValidationError, build_ocds_package, parse_csv_records
from auditor.red_flags import AuditThresholds, evaluate_red_flags
from auditor.report import write_audit_artifacts


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="ethio-ocds-audit",
        description=(
            "Normalize Ethiopian public procurement CSV records into OCDS 1.1 "
            "and generate deterministic red-flag audit reports with SHA-256 provenance."
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to input procurement CSV file.",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("output"),
        type=Path,
        help="Directory to write OCDS JSON, audit reports, and SHA-256 manifest (default: output).",
    )
    parser.add_argument(
        "--overrun-threshold",
        default=0.25,
        type=float,
        help="Cost variance ratio threshold for RF-COST-001 (default: 0.25 = 25%%).",
    )
    parser.add_argument(
        "--repeat-supplier-threshold",
        default=3,
        type=int,
        help="Minimum award count to flag repeat supplier concentration (default: 3).",
    )
    parser.add_argument(
        "--as-of-date",
        default=None,
        type=str,
        help="Optional reference ISO date (YYYY-MM-DD) for evaluating overdue active contracts.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint returning process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        parsed_as_of: date | None = (
            date.fromisoformat(args.as_of_date) if args.as_of_date else None
        )
        thresholds = AuditThresholds(
            overrun_threshold=args.overrun_threshold,
            repeat_supplier_threshold=args.repeat_supplier_threshold,
            as_of_date=parsed_as_of,
        )
        records = parse_csv_records(args.input)
        ocds_package = build_ocds_package(records)
        findings = evaluate_red_flags(records, thresholds=thresholds)
        result = write_audit_artifacts(
            output_dir=args.output_dir,
            input_path=args.input,
            records=records,
            ocds_package=ocds_package,
            findings=findings,
            thresholds=thresholds,
        )
    except (FileNotFoundError, CSVValidationError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    flagged_count = len({f.procurement_id for f in findings})
    print(f"Processed {len(records)} procurement records.")
    print(
        f"Identified {len(findings)} red-flag indicators across {flagged_count} records "
        "(for human audit review only)."
    )
    print(f"OCDS package:      {result.ocds_path} (sha256: {result.ocds_sha256[:12]}...)")
    print(
        f"JSON audit report: {result.report_json_path} "
        f"(sha256: {result.report_json_sha256[:12]}...)"
    )
    print(
        f"Markdown summary:  {result.summary_md_path} "
        f"(sha256: {result.summary_md_sha256[:12]}...)"
    )
    print(f"SHA-256 manifest:  {result.manifest_sha256_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())