"""Audit report generation (JSON + Markdown) and SHA-256 provenance hashing."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auditor.ocds_mapper import PROCLAMATION_REFERENCE, ProcurementRecord
from auditor.red_flags import AuditThresholds, RedFlagFinding

DISCLAIMER_TEXT = (
    "Red-flag indicators highlight statistical or procedural anomalies for human "
    "audit verification only and do not constitute proof of corruption, fraud, "
    "or legal liability."
)


@dataclass(frozen=True, slots=True)
class AuditArtifactsResult:
    """Paths and SHA-256 digests of all generated audit artifacts."""

    ocds_path: Path
    report_json_path: Path
    summary_md_path: Path
    manifest_sha256_path: Path
    input_sha256: str
    ocds_sha256: str
    report_json_sha256: str
    summary_md_sha256: str


def sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hex digest of a file using streaming reads."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize payload deterministically to UTF-8 JSON bytes."""
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _build_supplier_concentration_summary(
    records: list[ProcurementRecord],
) -> list[dict[str, Any]]:
    total_etb = sum(r.final_contract_amount_etb for r in records)
    grouped: dict[str, list[ProcurementRecord]] = defaultdict(list)
    for rec in records:
        grouped[rec.supplier_name].append(rec)

    summary = []
    for supplier, items in grouped.items():
        supplier_etb = round(sum(i.final_contract_amount_etb for i in items), 2)
        summary.append(
            {
                "supplierName": supplier,
                "awardCount": len(items),
                "totalFinalContractETB": supplier_etb,
                "valueShareRatio": round(supplier_etb / total_etb, 4)
                if total_etb > 0
                else 0.0,
            }
        )
    summary.sort(
        key=lambda row: (-row["awardCount"], -row["totalFinalContractETB"], row["supplierName"])
    )
    return summary


def build_audit_report(
    records: list[ProcurementRecord],
    ocds_package: dict[str, Any],
    findings: list[RedFlagFinding],
    thresholds: AuditThresholds,
    input_path: Path,
    input_sha256: str,
    ocds_sha256: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble the machine-readable JSON audit report dictionary."""
    timestamp = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    flagged_ids = {f.procurement_id for f in findings}
    by_indicator = dict(sorted(Counter(f.indicator_code for f in findings).items()))
    by_severity = dict(sorted(Counter(f.severity for f in findings).items()))

    return {
        "reportMetadata": {
            "tool": "ethio-procurement-ocds-auditor",
            "version": "0.1.0",
            "generatedAt": timestamp,
            "standard": f"OCDS {ocds_package.get('version', '1.1')}",
            "legalContext": PROCLAMATION_REFERENCE,
            "disclaimer": DISCLAIMER_TEXT,
            "thresholds": {
                "overrunThreshold": thresholds.overrun_threshold,
                "repeatSupplierThreshold": thresholds.repeat_supplier_threshold,
                "asOfDate": (
                    thresholds.as_of_date.isoformat()
                    if thresholds.as_of_date
                    else None
                ),
            },
        },
        "provenance": {
            "inputFile": str(input_path),
            "inputSha256": input_sha256,
            "ocdsPackageSha256": ocds_sha256,
        },
        "summary": {
            "totalProcurements": len(records),
            "flaggedProcurements": len(flagged_ids),
            "cleanProcurements": len(records) - len(flagged_ids),
            "totalFindings": len(findings),
            "totalEstimatedAmountETB": round(
                sum(r.estimated_amount_etb for r in records), 2
            ),
            "totalAwardedAmountETB": round(
                sum(r.awarded_amount_etb for r in records), 2
            ),
            "totalFinalContractAmountETB": round(
                sum(r.final_contract_amount_etb for r in records), 2
            ),
            "findingsByIndicator": by_indicator,
            "findingsBySeverity": by_severity,
            "supplierBreakdown": _build_supplier_concentration_summary(records),
        },
        "findings": [f.to_dict() for f in findings],
    }


def render_markdown_summary(
    report: dict[str, Any], report_json_sha256: str
) -> str:
    """Render a human-readable Markdown audit summary."""
    meta = report["reportMetadata"]
    prov = report["provenance"]
    summary = report["summary"]
    findings = report["findings"]
    thresholds = meta["thresholds"]

    lines: list[str] = [
        "# Ethiopian Public Procurement OCDS Audit Summary",
        "",
        f"> **Audit Notice:** {meta['disclaimer']}",
        "",
        "## 1. Run Context & Thresholds",
        "",
        f"- **Generated At (UTC):** `{meta['generatedAt']}`",
        f"- **Standard / Legal Framing:** {meta['standard']} | {meta['legalContext']}",
        f"- **Overrun Threshold:** `{thresholds['overrunThreshold']:.0%}`",
        f"- **Repeat Supplier Threshold:** `{thresholds['repeatSupplierThreshold']}` awards",
        f"- **As-Of Date:** `{thresholds['asOfDate'] or 'system current date'}`",
        "",
        "## 2. Portfolio Overview",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total Procurements Analyzed | {summary['totalProcurements']} |",
        f"| Procurements with Red-Flag Indicators | {summary['flaggedProcurements']} |",
        f"| Procurements Without Indicators | {summary['cleanProcurements']} |",
        f"| Total Red-Flag Indicators Raised | {summary['totalFindings']} |",
        f"| Total Estimated Value (ETB) | {summary['totalEstimatedAmountETB']:,.2f} |",
        f"| Total Awarded Value (ETB) | {summary['totalAwardedAmountETB']:,.2f} |",
        f"| Total Final Contract Value (ETB) | {summary['totalFinalContractAmountETB']:,.2f} |",
        "",
        "## 3. Indicators by Code & Severity",
        "",
    ]

    if summary["findingsByIndicator"]:
        lines.extend(
            [
                "| Indicator Code | Count |",
                "|---|---:|",
            ]
        )
        for code, count in summary["findingsByIndicator"].items():
            lines.append(f"| `{code}` | {count} |")
        lines.append("")
        lines.append(
            "**Severity Breakdown:** "
            + ", ".join(
                f"{sev}: {cnt}" for sev, cnt in summary["findingsBySeverity"].items()
            )
        )
    else:
        lines.append("No red-flag indicators were triggered under the configured thresholds.")

    lines.extend(["", "## 4. Detailed Findings Requiring Human Review", ""])
    if findings:
        lines.extend(
            [
                "| Procurement ID | OCID | Procuring Entity | Supplier | Indicator | Severity | Summary |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for f in findings:
            safe_expl = f["explanation"].replace("|", "/")
            lines.append(
                f"| `{f['procurement_id']}` | `{f['ocid']}` | {f['procuring_entity']} | "
                f"{f['supplier_name']} | `{f['indicator_code']}` | **{f['severity'].upper()}** | "
                f"{safe_expl} |"
            )
    else:
        lines.append("No detailed findings to display.")

    lines.extend(
        [
            "",
            "## 5. Provenance & SHA-256 Verification",
            "",
            "| Artifact | SHA-256 Digest |",
            "|---|---|",
            f"| Input CSV (`{Path(prov['inputFile']).name}`) | `{prov['inputSha256']}` |",
            f"| OCDS Release Package (`ocds_releases.json`) | `{prov['ocdsPackageSha256']}` |",
            f"| JSON Audit Report (`audit_report.json`) | `{report_json_sha256}` |",
            "",
            "All artifact hashes are also recorded in `provenance_hashes.sha256` for automated integrity checks.",
            "",
        ]
    )
    return "\n".join(lines)


def write_audit_artifacts(
    output_dir: Path,
    input_path: Path,
    records: list[ProcurementRecord],
    ocds_package: dict[str, Any],
    findings: list[RedFlagFinding],
    thresholds: AuditThresholds,
    generated_at: str | None = None,
) -> AuditArtifactsResult:
    """Write OCDS JSON, audit JSON, Markdown summary, and SHA-256 manifest."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    input_sha256 = sha256_file(input_path)

    ocds_bytes = canonical_json_bytes(ocds_package)
    ocds_sha256 = sha256_bytes(ocds_bytes)
    ocds_path = out / "ocds_releases.json"
    ocds_path.write_bytes(ocds_bytes)

    report_dict = build_audit_report(
        records=records,
        ocds_package=ocds_package,
        findings=findings,
        thresholds=thresholds,
        input_path=input_path,
        input_sha256=input_sha256,
        ocds_sha256=ocds_sha256,
        generated_at=generated_at,
    )
    report_bytes = canonical_json_bytes(report_dict)
    report_json_sha256 = sha256_bytes(report_bytes)
    report_json_path = out / "audit_report.json"
    report_json_path.write_bytes(report_bytes)

    summary_text = render_markdown_summary(report_dict, report_json_sha256)
    summary_bytes = summary_text.encode("utf-8")
    summary_md_sha256 = sha256_bytes(summary_bytes)
    summary_md_path = out / "audit_summary.md"
    summary_md_path.write_bytes(summary_bytes)

    manifest_lines = [
        f"{input_sha256}  {Path(input_path).resolve()}",
        f"{ocds_sha256}  {ocds_path.name}",
        f"{report_json_sha256}  {report_json_path.name}",
        f"{summary_md_sha256}  {summary_md_path.name}",
    ]
    manifest_path = out / "provenance_hashes.sha256"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    return AuditArtifactsResult(
        ocds_path=ocds_path,
        report_json_path=report_json_path,
        summary_md_path=summary_md_path,
        manifest_sha256_path=manifest_path,
        input_sha256=input_sha256,
        ocds_sha256=ocds_sha256,
        report_json_sha256=report_json_sha256,
        summary_md_sha256=summary_md_sha256,
    )