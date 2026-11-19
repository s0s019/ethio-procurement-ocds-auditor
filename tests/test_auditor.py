"""Comprehensive unit and integration tests for ethio-procurement-ocds-auditor."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from auditor.cli import main as cli_main
from auditor.ocds_mapper import (
    CSVValidationError,
    ProcurementRecord,
    build_ocds_package,
    generate_deterministic_ocid,
    parse_csv_records,
    record_to_ocds_release,
)
from auditor.red_flags import AuditThresholds, evaluate_red_flags
from auditor.report import sha256_file, write_audit_artifacts

SAMPLE_CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_tenders.csv"


def _make_record(**overrides: object) -> ProcurementRecord:
    defaults: dict[str, object] = {
        "procurement_id": "ETH-TEST-001",
        "procuring_entity": "Ministry of Health",
        "sector": "Health",
        "title": "Medical Supplies Procurement",
        "procurement_method_raw": "Open National Competitive Bidding",
        "procurement_method_ocds": "open",
        "award_date_ec": "2017-05-01",
        "award_date_gc": date(2025, 1, 9),
        "estimated_amount_etb": 1_000_000.0,
        "awarded_amount_etb": 1_000_000.0,
        "final_contract_amount_etb": 1_000_000.0,
        "supplier_name": "Alpha Medical PLC",
        "bids_received": 4,
        "planned_completion_date": date(2025, 6, 1),
        "actual_completion_date": date(2025, 5, 25),
        "extension_documented": False,
        "reported_status": "completed",
        "inspection_signoff": "signed",
    }
    defaults.update(overrides)
    return ProcurementRecord(**defaults)  # type: ignore[arg-type]


def test_parse_sample_csv_and_ocds_mapping() -> None:
    records = parse_csv_records(SAMPLE_CSV_PATH)
    assert len(records) == 16

    first = records[0]
    assert first.procurement_id == "ETH-FDRE-2025-001"
    assert first.ocid == generate_deterministic_ocid("ETH-FDRE-2025-001")
    assert first.ocid == "ocds-ethpub-eth-fdre-2025-001"

    release = record_to_ocds_release(first)
    assert release["ocid"] == first.ocid
    assert release["tender"]["value"]["currency"] == "ETB"
    assert release["tender"]["procurementMethod"] == "open"
    assert release["awards"][0]["value"]["amount"] == 44200000.0
    assert release["contracts"][0]["value"]["amount"] == 44200000.0
    assert len(release["parties"]) == 2
    assert "Proclamation No. 1333/2024" in (
        release["ethiopiaProcurementContext"]["proclamationReference"]
    )


def test_csv_validation_errors(tmp_path: Path) -> None:
    bad_csv = tmp_path / "missing_col.csv"
    bad_csv.write_text("procurement_id,title\nETH-1,Test\n", encoding="utf-8")
    with pytest.raises(CSVValidationError, match="missing required columns"):
        parse_csv_records(bad_csv)

    header = SAMPLE_CSV_PATH.read_text(encoding="utf-8").splitlines()[0]
    bad_num_csv = tmp_path / "bad_num.csv"
    bad_num_csv.write_text(
        header
        + "\nETH-1,Min,Health,Title,Open National Competitive Bidding,2017-01-01,"
        "2024-09-11,NOT_A_NUMBER,100,100,Supplier,3,2025-01-01,2025-01-01,no,completed,signed\n",
        encoding="utf-8",
    )
    with pytest.raises(CSVValidationError, match="invalid numeric amount"):
        parse_csv_records(bad_num_csv)


def test_cost_overrun_heuristic_and_threshold() -> None:
    # +30% upward contract amendment over awarded amount
    rec = _make_record(
        estimated_amount_etb=1_000_000.0,
        awarded_amount_etb=1_000_000.0,
        final_contract_amount_etb=1_300_000.0,
    )
    findings_default = evaluate_red_flags([rec], AuditThresholds(overrun_threshold=0.25))
    assert any(f.indicator_code == "RF-COST-001" for f in findings_default)

    findings_relaxed = evaluate_red_flags([rec], AuditThresholds(overrun_threshold=0.35))
    assert not any(f.indicator_code == "RF-COST-001" for f in findings_relaxed)


def test_single_bidder_open_vs_direct_procurement() -> None:
    open_single = _make_record(
        procurement_id="ETH-OPEN-1",
        procurement_method_raw="Open National Competitive Bidding",
        procurement_method_ocds="open",
        bids_received=1,
    )
    direct_single = _make_record(
        procurement_id="ETH-DIRECT-1",
        procurement_method_raw="Direct Procurement",
        procurement_method_ocds="direct",
        bids_received=1,
    )
    findings = evaluate_red_flags([open_single, direct_single])
    comp_flags = [f for f in findings if f.indicator_code == "RF-COMP-001"]
    assert len(comp_flags) == 1
    assert comp_flags[0].procurement_id == "ETH-OPEN-1"


def test_repeat_supplier_concentration_threshold() -> None:
    recs = [
        _make_record(procurement_id="ETH-1", supplier_name="Repeated PLC"),
        _make_record(procurement_id="ETH-2", supplier_name="  repeated   plc "),
        _make_record(procurement_id="ETH-3", supplier_name="Other PLC"),
    ]
    flags_at_3 = evaluate_red_flags(
        recs, AuditThresholds(repeat_supplier_threshold=3)
    )
    assert not any(f.indicator_code == "RF-CONC-001" for f in flags_at_3)

    flags_at_2 = evaluate_red_flags(
        recs, AuditThresholds(repeat_supplier_threshold=2)
    )
    conc_flags = [f for f in flags_at_2 if f.indicator_code == "RF-CONC-001"]
    assert len(conc_flags) == 2
    assert conc_flags[0].supporting_values["supplier_award_count"] == 2


def test_schedule_slippage_and_documented_extension() -> None:
    late_no_ext = _make_record(
        procurement_id="ETH-LATE",
        planned_completion_date=date(2025, 6, 1),
        actual_completion_date=date(2025, 8, 1),
        extension_documented=False,
    )
    overdue_with_ext = _make_record(
        procurement_id="ETH-EXT",
        planned_completion_date=date(2025, 6, 1),
        actual_completion_date=None,
        extension_documented=True,
        reported_status="in_progress",
        inspection_signoff="pending",
    )
    overdue_no_ext = _make_record(
        procurement_id="ETH-OVERDUE",
        planned_completion_date=date(2025, 6, 1),
        actual_completion_date=None,
        extension_documented=False,
        reported_status="delayed",
        inspection_signoff="pending",
    )

    findings = evaluate_red_flags(
        [late_no_ext, overdue_with_ext, overdue_no_ext],
        AuditThresholds(as_of_date=date(2025, 9, 1)),
    )
    time_flags = {f.procurement_id: f for f in findings if f.indicator_code == "RF-TIME-001"}
    assert set(time_flags.keys()) == {"ETH-LATE", "ETH-OVERDUE"}
    assert time_flags["ETH-LATE"].supporting_values["delay_days"] == 61
    assert time_flags["ETH-OVERDUE"].supporting_values["delay_days"] == 92


def test_completed_missing_inspection_signoff() -> None:
    missing_signoff = _make_record(
        procurement_id="ETH-MISS",
        reported_status="completed",
        inspection_signoff="missing",
    )
    pending_signoff = _make_record(
        procurement_id="ETH-PEND",
        reported_status="completed",
        inspection_signoff="pending",
    )
    in_progress_pending = _make_record(
        procurement_id="ETH-PROG",
        planned_completion_date=date(2026, 12, 1),
        actual_completion_date=None,
        reported_status="in_progress",
        inspection_signoff="pending",
    )

    findings = evaluate_red_flags(
        [missing_signoff, pending_signoff, in_progress_pending],
        AuditThresholds(as_of_date=date(2026, 11, 1)),
    )
    handover_flags = {
        f.procurement_id: f for f in findings if f.indicator_code == "RF-HANDOVER-001"
    }
    assert set(handover_flags.keys()) == {"ETH-MISS", "ETH-PEND"}
    assert handover_flags["ETH-MISS"].severity == "high"
    assert handover_flags["ETH-PEND"].severity == "medium"


def test_sample_dataset_expected_flags() -> None:
    records = parse_csv_records(SAMPLE_CSV_PATH)
    findings = evaluate_red_flags(
        records, AuditThresholds(overrun_threshold=0.25, repeat_supplier_threshold=3, as_of_date=date(2026, 11, 19))
    )
    flagged_ids = {f.procurement_id for f in findings}
    assert flagged_ids == {
        "ETH-FDRE-2025-003",
        "ETH-FDRE-2025-006",
        "ETH-FDRE-2025-007",
        "ETH-FDRE-2025-008",
        "ETH-FDRE-2025-011",
        "ETH-FDRE-2025-013",
        "ETH-FDRE-2025-014",
        "ETH-FDRE-2025-015",
    }


def test_sha256_provenance_consistency_and_tamper_detection(tmp_path: Path) -> None:
    working_csv = tmp_path / "tenders.csv"
    working_csv.write_bytes(SAMPLE_CSV_PATH.read_bytes())

    thresholds = AuditThresholds(as_of_date=date(2026, 11, 19))
    records = parse_csv_records(working_csv)
    pkg = build_ocds_package(records, published_date="2026-11-19T00:00:00Z")
    findings = evaluate_red_flags(records, thresholds)

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    res1 = write_audit_artifacts(
        out1, working_csv, records, pkg, findings, thresholds, generated_at="2026-11-19T00:00:00Z"
    )
    res2 = write_audit_artifacts(
        out2, working_csv, records, pkg, findings, thresholds, generated_at="2026-11-19T00:00:00Z"
    )

    assert res1.input_sha256 == res2.input_sha256
    assert res1.ocds_sha256 == res2.ocds_sha256
    assert res1.report_json_sha256 == res2.report_json_sha256
    assert res1.summary_md_sha256 == res2.summary_md_sha256

    # Verify stored hashes match actual files on disk
    assert sha256_file(res1.ocds_path) == res1.ocds_sha256
    assert sha256_file(res1.report_json_path) == res1.report_json_sha256

    # Simulate tampering with the OCDS JSON artifact
    tampered_text = res1.ocds_path.read_text(encoding="utf-8").replace(
        "44200000.0", "44200001.0", 1
    )
    res1.ocds_path.write_text(tampered_text, encoding="utf-8")
    assert sha256_file(res1.ocds_path) != res1.ocds_sha256


def test_cli_end_to_end(tmp_path: Path) -> None:
    out_dir = tmp_path / "cli_output"
    exit_code = cli_main(
        [
            "--input",
            str(SAMPLE_CSV_PATH),
            "--output-dir",
            str(out_dir),
            "--overrun-threshold",
            "0.25",
            "--repeat-supplier-threshold",
            "3",
            "--as-of-date",
            "2026-11-19",
        ]
    )
    assert exit_code == 0
    assert (out_dir / "ocds_releases.json").exists()
    assert (out_dir / "audit_report.json").exists()
    assert (out_dir / "audit_summary.md").exists()
    assert (out_dir / "provenance_hashes.sha256").exists()

    report_data = json.loads((out_dir / "audit_report.json").read_text(encoding="utf-8"))
    assert report_data["summary"]["totalProcurements"] == 16
    assert report_data["summary"]["flaggedProcurements"] == 8
    assert "human audit verification only" in report_data["reportMetadata"]["disclaimer"]