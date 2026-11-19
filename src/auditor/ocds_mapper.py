"""CSV ingestion, validation, and Open Contracting Data Standard (OCDS 1.1) mapping."""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

OCDS_VERSION = "1.1"
CURRENCY_ETB = "ETB"
DEFAULT_OCID_PREFIX = "ocds-ethpub"
PROCLAMATION_REFERENCE = (
    "Federal Public Procurement and Property Administration Proclamation No. 1333/2024"
)

REQUIRED_COLUMNS: tuple[str, ...] = (
    "procurement_id",
    "procuring_entity",
    "sector",
    "title",
    "procurement_method",
    "award_date_ec",
    "award_date_gc",
    "estimated_amount_etb",
    "awarded_amount_etb",
    "final_contract_amount_etb",
    "supplier_name",
    "bids_received",
    "planned_completion_date",
    "actual_completion_date",
    "extension_documented",
    "reported_status",
    "inspection_signoff",
)

VALID_REPORTED_STATUSES = {"completed", "in_progress", "delayed", "terminated"}
VALID_INSPECTION_SIGNOFFS = {"signed", "pending", "missing"}


class CSVValidationError(ValueError):
    """Raised when input CSV structure or field values fail validation."""


@dataclass(frozen=True, slots=True)
class ProcurementRecord:
    """Normalized representation of a single Ethiopian public procurement record."""

    procurement_id: str
    procuring_entity: str
    sector: str
    title: str
    procurement_method_raw: str
    procurement_method_ocds: str
    award_date_ec: str
    award_date_gc: date
    estimated_amount_etb: float
    awarded_amount_etb: float
    final_contract_amount_etb: float
    supplier_name: str
    bids_received: int
    planned_completion_date: date
    actual_completion_date: date | None
    extension_documented: bool
    reported_status: str
    inspection_signoff: str

    @property
    def ocid(self) -> str:
        """Return deterministic OCDS Open Contracting ID."""
        return generate_deterministic_ocid(self.procurement_id)


def generate_deterministic_ocid(
    procurement_id: str, prefix: str = DEFAULT_OCID_PREFIX
) -> str:
    """Build a deterministic OCDS `ocid` from a procurement identifier.

    Example: ``ETH-FDRE-2025-001`` -> ``ocds-ethpub-eth-fdre-2025-001``.
    """
    cleaned_prefix = re.sub(r"[^a-z0-9-]+", "-", prefix.strip().lower()).strip("-")
    if not cleaned_prefix:
        cleaned_prefix = DEFAULT_OCID_PREFIX

    cleaned_id = re.sub(r"[^a-z0-9-]+", "-", procurement_id.strip().lower()).strip("-")
    if not cleaned_id:
        digest = hashlib.sha256(procurement_id.encode("utf-8")).hexdigest()[:12]
        cleaned_id = f"record-{digest}"

    return f"{cleaned_prefix}-{cleaned_id}"


def generate_party_id(name: str, role: str) -> str:
    """Generate a deterministic OCDS party identifier from normalized entity name."""
    normalized = re.sub(r"\s+", " ", name.strip().lower())
    digest = hashlib.sha256(f"{role}:{normalized}".encode("utf-8")).hexdigest()[:10]
    return f"ET-{role.upper()}-{digest}"


def map_procurement_method(method_raw: str) -> tuple[str, str]:
    """Map Ethiopian procurement method labels to OCDS `procurementMethod` values."""
    normalized = re.sub(r"\s+", " ", method_raw.strip()).lower()
    if not normalized:
        raise ValueError("Procurement method cannot be empty.")

    if "open" in normalized:
        return "open", method_raw.strip()
    if "restricted" in normalized or "selective" in normalized or "two-stage" in normalized:
        return "selective", method_raw.strip()
    if "direct" in normalized or "single source" in normalized or "sole" in normalized:
        return "direct", method_raw.strip()
    if "quotation" in normalized or "rfq" in normalized or "request for proposals" in normalized:
        return "limited", method_raw.strip()

    return "open", method_raw.strip()


def _map_sector_to_ocds_category(sector: str) -> str:
    normalized = sector.strip().lower()
    if any(word in normalized for word in ("infra", "road", "water", "construc", "energy")):
        return "works"
    if any(word in normalized for word in ("it", "goods", "health", "agri", "edu")):
        return "goods"
    return "services"


def _map_contract_status(reported_status: str) -> str:
    if reported_status == "completed":
        return "terminated"  # In OCDS, fulfilled/closed contracts use 'terminated' or 'active'
    if reported_status == "terminated":
        return "cancelled"
    return "active"


def _parse_required_text(row: dict[str, str], col: str, row_num: int) -> str:
    val = (row.get(col) or "").strip()
    if not val:
        raise CSVValidationError(f"Row {row_num}: missing required value in '{col}'.")
    return val


def _parse_amount(
    row: dict[str, str], col: str, row_num: int, *, allow_zero: bool = True
) -> float:
    raw = _parse_required_text(row, col, row_num).replace(",", "")
    try:
        value = float(raw)
    except ValueError as exc:
        raise CSVValidationError(
            f"Row {row_num}: invalid numeric amount '{raw}' in '{col}'."
        ) from exc

    if value < 0 or (not allow_zero and value <= 0):
        comparator = ">= 0" if allow_zero else "> 0"
        raise CSVValidationError(
            f"Row {row_num}: '{col}' must be {comparator}, got {value}."
        )
    return round(value, 2)


def _parse_int(row: dict[str, str], col: str, row_num: int) -> int:
    raw = _parse_required_text(row, col, row_num)
    try:
        value = int(raw)
    except ValueError as exc:
        raise CSVValidationError(
            f"Row {row_num}: invalid integer '{raw}' in '{col}'."
        ) from exc
    if value < 0:
        raise CSVValidationError(f"Row {row_num}: '{col}' cannot be negative, got {value}.")
    return value


def _parse_iso_date(
    row: dict[str, str], col: str, row_num: int, *, required: bool = True
) -> date | None:
    raw = (row.get(col) or "").strip()
    if not raw:
        if required:
            raise CSVValidationError(f"Row {row_num}: missing required date in '{col}'.")
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise CSVValidationError(
            f"Row {row_num}: invalid ISO date '{raw}' in '{col}' (expected YYYY-MM-DD)."
        ) from exc


def _parse_bool(row: dict[str, str], col: str, row_num: int) -> bool:
    raw = _parse_required_text(row, col, row_num).lower()
    if raw in {"yes", "true", "1", "y"}:
        return True
    if raw in {"no", "false", "0", "n"}:
        return False
    raise CSVValidationError(
        f"Row {row_num}: invalid boolean '{raw}' in '{col}' (expected yes/no)."
    )


def parse_csv_records(csv_path: Path) -> list[ProcurementRecord]:
    """Read, validate, and normalize procurement records from a CSV file."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Input CSV file not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise CSVValidationError("Input CSV file is empty or missing a header row.")

        normalized_headers = [h.strip() for h in reader.fieldnames]
        reader.fieldnames = normalized_headers
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in normalized_headers]
        if missing_cols:
            raise CSVValidationError(
                f"Input CSV is missing required columns: {', '.join(missing_cols)}"
            )

        records: list[ProcurementRecord] = []
        seen_ids: set[str] = set()

        for row_num, row in enumerate(reader, start=2):
            if not any((v or "").strip() for v in row.values()):
                continue

            procurement_id = _parse_required_text(row, "procurement_id", row_num)
            if procurement_id in seen_ids:
                raise CSVValidationError(
                    f"Row {row_num}: duplicate procurement_id '{procurement_id}'."
                )
            seen_ids.add(procurement_id)

            method_raw = _parse_required_text(row, "procurement_method", row_num)
            method_ocds, method_details = map_procurement_method(method_raw)

            award_date_gc = _parse_iso_date(row, "award_date_gc", row_num, required=True)
            planned_date = _parse_iso_date(
                row, "planned_completion_date", row_num, required=True
            )
            actual_date = _parse_iso_date(
                row, "actual_completion_date", row_num, required=False
            )
            assert award_date_gc is not None and planned_date is not None

            reported_status = _parse_required_text(row, "reported_status", row_num).lower()
            if reported_status not in VALID_REPORTED_STATUSES:
                raise CSVValidationError(
                    f"Row {row_num}: invalid reported_status '{reported_status}'. "
                    f"Expected one of {sorted(VALID_REPORTED_STATUSES)}."
                )

            inspection_signoff = _parse_required_text(
                row, "inspection_signoff", row_num
            ).lower()
            if inspection_signoff not in VALID_INSPECTION_SIGNOFFS:
                raise CSVValidationError(
                    f"Row {row_num}: invalid inspection_signoff '{inspection_signoff}'. "
                    f"Expected one of {sorted(VALID_INSPECTION_SIGNOFFS)}."
                )

            records.append(
                ProcurementRecord(
                    procurement_id=procurement_id,
                    procuring_entity=_parse_required_text(row, "procuring_entity", row_num),
                    sector=_parse_required_text(row, "sector", row_num),
                    title=_parse_required_text(row, "title", row_num),
                    procurement_method_raw=method_details,
                    procurement_method_ocds=method_ocds,
                    award_date_ec=_parse_required_text(row, "award_date_ec", row_num),
                    award_date_gc=award_date_gc,
                    estimated_amount_etb=_parse_amount(
                        row, "estimated_amount_etb", row_num, allow_zero=False
                    ),
                    awarded_amount_etb=_parse_amount(
                        row, "awarded_amount_etb", row_num, allow_zero=True
                    ),
                    final_contract_amount_etb=_parse_amount(
                        row, "final_contract_amount_etb", row_num, allow_zero=True
                    ),
                    supplier_name=_parse_required_text(row, "supplier_name", row_num),
                    bids_received=_parse_int(row, "bids_received", row_num),
                    planned_completion_date=planned_date,
                    actual_completion_date=actual_date,
                    extension_documented=_parse_bool(row, "extension_documented", row_num),
                    reported_status=reported_status,
                    inspection_signoff=inspection_signoff,
                )
            )

    if not records:
        raise CSVValidationError("Input CSV contains headers but zero procurement rows.")

    return records


def record_to_ocds_release(
    record: ProcurementRecord, release_date: str | None = None
) -> dict[str, Any]:
    """Convert a normalized ``ProcurementRecord`` into an OCDS 1.1 release dict."""
    ocid = record.ocid
    buyer_id = generate_party_id(record.procuring_entity, "BUYER")
    supplier_id = generate_party_id(record.supplier_name, "SUPPLIER")
    release_timestamp = release_date or f"{record.award_date_gc.isoformat()}T00:00:00Z"

    award_id = f"{record.procurement_id}-AWD-1"
    contract_id = f"{record.procurement_id}-CTR-1"
    end_date = (
        record.actual_completion_date.isoformat()
        if record.actual_completion_date
        else record.planned_completion_date.isoformat()
    )

    return {
        "ocid": ocid,
        "id": f"{record.procurement_id}-rel-1",
        "date": release_timestamp,
        "tag": ["tender", "award", "contract", "implementation"],
        "initiationType": "tender",
        "language": "en",
        "parties": [
            {
                "id": buyer_id,
                "name": record.procuring_entity,
                "roles": ["buyer", "procuringEntity"],
                "address": {"countryName": "Ethiopia"},
            },
            {
                "id": supplier_id,
                "name": record.supplier_name,
                "roles": ["supplier"],
                "address": {"countryName": "Ethiopia"},
            },
        ],
        "buyer": {
            "id": buyer_id,
            "name": record.procuring_entity,
        },
        "tender": {
            "id": record.procurement_id,
            "title": record.title,
            "status": "complete",
            "mainProcurementCategory": _map_sector_to_ocds_category(record.sector),
            "procurementMethod": record.procurement_method_ocds,
            "procurementMethodDetails": record.procurement_method_raw,
            "numberOfTenderers": record.bids_received,
            "procuringEntity": {
                "id": buyer_id,
                "name": record.procuring_entity,
            },
            "value": {
                "amount": record.estimated_amount_etb,
                "currency": CURRENCY_ETB,
            },
        },
        "awards": [
            {
                "id": award_id,
                "title": record.title,
                "status": "active",
                "date": f"{record.award_date_gc.isoformat()}T00:00:00Z",
                "value": {
                    "amount": record.awarded_amount_etb,
                    "currency": CURRENCY_ETB,
                },
                "suppliers": [
                    {
                        "id": supplier_id,
                        "name": record.supplier_name,
                    }
                ],
            }
        ],
        "contracts": [
            {
                "id": contract_id,
                "awardID": award_id,
                "title": record.title,
                "status": _map_contract_status(record.reported_status),
                "dateSigned": f"{record.award_date_gc.isoformat()}T00:00:00Z",
                "period": {
                    "startDate": f"{record.award_date_gc.isoformat()}T00:00:00Z",
                    "endDate": f"{end_date}T00:00:00Z",
                },
                "value": {
                    "amount": record.final_contract_amount_etb,
                    "currency": CURRENCY_ETB,
                },
                "implementation": {
                    "status": record.reported_status,
                },
            }
        ],
        "ethiopiaProcurementContext": {
            "proclamationReference": PROCLAMATION_REFERENCE,
            "sector": record.sector,
            "awardDateEC": record.award_date_ec,
            "awardDateGC": record.award_date_gc.isoformat(),
            "plannedCompletionDate": record.planned_completion_date.isoformat(),
            "actualCompletionDate": (
                record.actual_completion_date.isoformat()
                if record.actual_completion_date
                else None
            ),
            "extensionDocumented": record.extension_documented,
            "inspectionSignoffStatus": record.inspection_signoff,
        },
    }


def build_ocds_package(
    records: list[ProcurementRecord], published_date: str | None = None
) -> dict[str, Any]:
    """Assemble normalized releases into an OCDS 1.1 release package."""
    timestamp = published_date or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    releases = [record_to_ocds_release(record) for record in records]
    return {
        "uri": "urn:ethio-procurement-ocds-auditor:release-package:v1",
        "version": OCDS_VERSION,
        "publishedDate": timestamp,
        "publisher": {
            "name": "ethio-procurement-ocds-auditor",
        },
        "license": "https://opensource.org/licenses/MIT",
        "releases": releases,
    }