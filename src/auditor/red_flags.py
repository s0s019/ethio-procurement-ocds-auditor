"""Deterministic red-flag risk indicators for Ethiopian public procurement review.

Important:
    Every finding produced by this module is a statistical or procedural anomaly
    indicator intended to prioritize human audit verification under Ethiopia's
    Federal Public Procurement and Property Administration Proclamation No.
    1333/2024. Findings do not constitute proof of corruption or legal guilt.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from auditor.ocds_mapper import ProcurementRecord


@dataclass(frozen=True, slots=True)
class AuditThresholds:
    """Configurable thresholds for deterministic red-flag checks."""

    overrun_threshold: float = 0.25
    repeat_supplier_threshold: int = 3
    as_of_date: date | None = None

    def __post_init__(self) -> None:
        if self.overrun_threshold < 0:
            raise ValueError("overrun_threshold must be non-negative.")
        if self.repeat_supplier_threshold < 1:
            raise ValueError("repeat_supplier_threshold must be at least 1.")


@dataclass(frozen=True, slots=True)
class RedFlagFinding:
    """Structured audit risk indicator requiring human review."""

    procurement_id: str
    ocid: str
    procuring_entity: str
    supplier_name: str
    indicator_code: str
    indicator_name: str
    severity: str
    explanation: str
    supporting_values: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize finding into a plain dictionary."""
        return asdict(self)


def _normalize_supplier_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _check_cost_overrun(
    record: ProcurementRecord, threshold: float
) -> RedFlagFinding | None:
    award_over_est = (
        (record.awarded_amount_etb - record.estimated_amount_etb)
        / record.estimated_amount_etb
        if record.estimated_amount_etb > 0
        else 0.0
    )
    amendment_over_award = (
        (record.final_contract_amount_etb - record.awarded_amount_etb)
        / record.awarded_amount_etb
        if record.awarded_amount_etb > 0
        else 0.0
    )
    final_over_est = (
        (record.final_contract_amount_etb - record.estimated_amount_etb)
        / record.estimated_amount_etb
        if record.estimated_amount_etb > 0
        else 0.0
    )

    max_variance = max(award_over_est, amendment_over_award, final_over_est)
    if max_variance <= threshold:
        return None

    reasons: list[str] = []
    if amendment_over_award > threshold:
        reasons.append(
            f"final contract value exceeds awarded amount by {amendment_over_award:.1%}"
        )
    if award_over_est > threshold:
        reasons.append(
            f"awarded amount exceeds initial estimate by {award_over_est:.1%}"
        )
    if not reasons and final_over_est > threshold:
        reasons.append(
            f"final contract value exceeds initial estimate by {final_over_est:.1%}"
        )

    severity = "high" if max_variance >= max(threshold * 2, 0.50) else "medium"
    explanation = (
        f"Cost variance indicator triggered ({'; '.join(reasons)}, "
        f"threshold {threshold:.1%}). Requires human review of approved variation "
        f"orders, market price changes, or engineer estimates."
    )

    return RedFlagFinding(
        procurement_id=record.procurement_id,
        ocid=record.ocid,
        procuring_entity=record.procuring_entity,
        supplier_name=record.supplier_name,
        indicator_code="RF-COST-001",
        indicator_name="Cost Overrun / Upward Variance",
        severity=severity,
        explanation=explanation,
        supporting_values={
            "estimated_amount_etb": record.estimated_amount_etb,
            "awarded_amount_etb": record.awarded_amount_etb,
            "final_contract_amount_etb": record.final_contract_amount_etb,
            "award_over_estimate_ratio": round(award_over_est, 4),
            "amendment_over_award_ratio": round(amendment_over_award, 4),
            "final_over_estimate_ratio": round(final_over_est, 4),
            "threshold_ratio": threshold,
        },
    )


def _check_single_bidder_open_tender(
    record: ProcurementRecord,
) -> RedFlagFinding | None:
    if record.procurement_method_ocds != "open" or record.bids_received > 1:
        return None

    explanation = (
        f"Open competitive tender ({record.procurement_method_raw}) received only "
        f"{record.bids_received} bid. Requires human review of tender advertisement "
        f"reach, qualification criteria, and technical specification neutrality."
    )

    return RedFlagFinding(
        procurement_id=record.procurement_id,
        ocid=record.ocid,
        procuring_entity=record.procuring_entity,
        supplier_name=record.supplier_name,
        indicator_code="RF-COMP-001",
        indicator_name="Single-Bidder Competitive Tender",
        severity="medium",
        explanation=explanation,
        supporting_values={
            "procurement_method": record.procurement_method_raw,
            "ocds_procurement_method": record.procurement_method_ocds,
            "bids_received": record.bids_received,
        },
    )


def _check_schedule_slippage(
    record: ProcurementRecord, effective_as_of: date
) -> RedFlagFinding | None:
    if record.extension_documented:
        return None

    delay_days = 0
    basis = ""
    if (
        record.actual_completion_date is not None
        and record.actual_completion_date > record.planned_completion_date
    ):
        delay_days = (record.actual_completion_date - record.planned_completion_date).days
        basis = "actual completion exceeded planned date"
    elif (
        record.actual_completion_date is None
        and record.reported_status != "terminated"
        and effective_as_of > record.planned_completion_date
    ):
        delay_days = (effective_as_of - record.planned_completion_date).days
        basis = f"contract remains '{record.reported_status}' past planned completion date as of {effective_as_of.isoformat()}"

    if delay_days <= 0:
        return None

    severity = "high" if delay_days >= 90 else "medium"
    explanation = (
        f"Undocumented schedule slippage of {delay_days} days ({basis}, with no "
        f"documented time extension). Requires human review of site logs, variation "
        f"approvals, and liquidated damages applicability."
    )

    return RedFlagFinding(
        procurement_id=record.procurement_id,
        ocid=record.ocid,
        procuring_entity=record.procuring_entity,
        supplier_name=record.supplier_name,
        indicator_code="RF-TIME-001",
        indicator_name="Undocumented Schedule Slippage",
        severity=severity,
        explanation=explanation,
        supporting_values={
            "planned_completion_date": record.planned_completion_date.isoformat(),
            "actual_completion_date": (
                record.actual_completion_date.isoformat()
                if record.actual_completion_date
                else None
            ),
            "as_of_date": effective_as_of.isoformat(),
            "delay_days": delay_days,
            "extension_documented": record.extension_documented,
            "reported_status": record.reported_status,
        },
    )


def _check_missing_inspection(record: ProcurementRecord) -> RedFlagFinding | None:
    if record.reported_status != "completed":
        return None
    if record.inspection_signoff not in {"missing", "pending"}:
        return None

    severity = "high" if record.inspection_signoff == "missing" else "medium"
    explanation = (
        f"Contract is marked 'completed' while final inspection/handover sign-off is "
        f"'{record.inspection_signoff}'. Requires human verification of physical "
        f"delivery certificates and inspection committee minutes before final closure."
    )

    return RedFlagFinding(
        procurement_id=record.procurement_id,
        ocid=record.ocid,
        procuring_entity=record.procuring_entity,
        supplier_name=record.supplier_name,
        indicator_code="RF-HANDOVER-001",
        indicator_name="Completed Without Final Inspection Sign-Off",
        severity=severity,
        explanation=explanation,
        supporting_values={
            "reported_status": record.reported_status,
            "inspection_signoff": record.inspection_signoff,
            "final_contract_amount_etb": record.final_contract_amount_etb,
        },
    )


def evaluate_red_flags(
    records: list[ProcurementRecord], thresholds: AuditThresholds | None = None
) -> list[RedFlagFinding]:
    """Run all deterministic red-flag checks across a list of procurement records."""
    cfg = thresholds or AuditThresholds()
    effective_as_of = cfg.as_of_date or date.today()

    total_awards = len(records)
    total_final_etb = sum(r.final_contract_amount_etb for r in records)

    supplier_records: dict[str, list[ProcurementRecord]] = defaultdict(list)
    for rec in records:
        supplier_records[_normalize_supplier_key(rec.supplier_name)].append(rec)

    findings: list[RedFlagFinding] = []

    for rec in records:
        cost_flag = _check_cost_overrun(rec, cfg.overrun_threshold)
        if cost_flag:
            findings.append(cost_flag)

        single_bid_flag = _check_single_bidder_open_tender(rec)
        if single_bid_flag:
            findings.append(single_bid_flag)

        supplier_key = _normalize_supplier_key(rec.supplier_name)
        peer_awards = supplier_records[supplier_key]
        award_count = len(peer_awards)
        if award_count >= cfg.repeat_supplier_threshold:
            supplier_total_etb = sum(item.final_contract_amount_etb for item in peer_awards)
            award_share = award_count / total_awards if total_awards > 0 else 0.0
            value_share = (
                supplier_total_etb / total_final_etb if total_final_etb > 0 else 0.0
            )
            severity = (
                "high"
                if award_count >= cfg.repeat_supplier_threshold + 2 or value_share >= 0.40
                else "medium"
            )
            findings.append(
                RedFlagFinding(
                    procurement_id=rec.procurement_id,
                    ocid=rec.ocid,
                    procuring_entity=rec.procuring_entity,
                    supplier_name=rec.supplier_name,
                    indicator_code="RF-CONC-001",
                    indicator_name="Repeat Supplier Concentration",
                    severity=severity,
                    explanation=(
                        f"Supplier '{rec.supplier_name}' holds {award_count} awards "
                        f"({award_share:.1%} of tenders, {value_share:.1%} of total ETB "
                        f"contract value; threshold {cfg.repeat_supplier_threshold}). "
                        f"Requires human review of lot splitting, market capacity, and "
                        f"independent bid evaluation."
                    ),
                    supporting_values={
                        "supplier_award_count": award_count,
                        "total_tenders_in_dataset": total_awards,
                        "award_share_ratio": round(award_share, 4),
                        "supplier_total_etb": round(supplier_total_etb, 2),
                        "dataset_total_etb": round(total_final_etb, 2),
                        "value_share_ratio": round(value_share, 4),
                        "threshold_count": cfg.repeat_supplier_threshold,
                    },
                )
            )

        delay_flag = _check_schedule_slippage(rec, effective_as_of)
        if delay_flag:
            findings.append(delay_flag)

        handover_flag = _check_missing_inspection(rec)
        if handover_flag:
            findings.append(handover_flag)

    return findings