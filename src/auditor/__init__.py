"""ethio-procurement-ocds-auditor package.

Provides CSV normalization to OCDS 1.1 releases, deterministic red-flag risk
indicators for Ethiopian public procurement oversight, and SHA-256 verifiable
audit report generation.
"""

from auditor.ocds_mapper import (
    CSVValidationError,
    ProcurementRecord,
    build_ocds_package,
    generate_deterministic_ocid,
    parse_csv_records,
    record_to_ocds_release,
)
from auditor.red_flags import (
    AuditThresholds,
    RedFlagFinding,
    evaluate_red_flags,
)
from auditor.report import (
    AuditArtifactsResult,
    build_audit_report,
    render_markdown_summary,
    sha256_bytes,
    sha256_file,
    write_audit_artifacts,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "AuditArtifactsResult",
    "AuditThresholds",
    "CSVValidationError",
    "ProcurementRecord",
    "RedFlagFinding",
    "build_audit_report",
    "build_ocds_package",
    "evaluate_red_flags",
    "generate_deterministic_ocid",
    "parse_csv_records",
    "record_to_ocds_release",
    "render_markdown_summary",
    "sha256_bytes",
    "sha256_file",
    "write_audit_artifacts",
]