# Ethiopian Public Procurement OCDS Audit Summary

> **Audit Notice:** Red-flag indicators highlight statistical or procedural anomalies for human audit verification only and do not constitute proof of corruption, fraud, or legal liability.

## 1. Run Context & Thresholds

- **Generated At (UTC):** `2026-11-19T16:49:42Z`
- **Standard / Legal Framing:** OCDS 1.1 | Federal Public Procurement and Property Administration Proclamation No. 1333/2024
- **Overrun Threshold:** `25%`
- **Repeat Supplier Threshold:** `3` awards
- **As-Of Date:** `system current date`

## 2. Portfolio Overview

| Metric | Value |
|---|---:|
| Total Procurements Analyzed | 16 |
| Procurements with Red-Flag Indicators | 8 |
| Procurements Without Indicators | 8 |
| Total Red-Flag Indicators Raised | 13 |
| Total Estimated Value (ETB) | 464,700,000.00 |
| Total Awarded Value (ETB) | 463,250,000.00 |
| Total Final Contract Value (ETB) | 488,050,000.00 |

## 3. Indicators by Code & Severity

| Indicator Code | Count |
|---|---:|
| `RF-COMP-001` | 2 |
| `RF-CONC-001` | 3 |
| `RF-COST-001` | 3 |
| `RF-HANDOVER-001` | 2 |
| `RF-TIME-001` | 3 |

**Severity Breakdown:** high: 2, medium: 11

## 4. Detailed Findings Requiring Human Review

| Procurement ID | OCID | Procuring Entity | Supplier | Indicator | Severity | Summary |
|---|---|---|---|---|---|---|
| `ETH-FDRE-2025-003` | `ocds-ethpub-eth-fdre-2025-003` | Ministry of Innovation and Technology | Nile Tech Systems PLC | `RF-COST-001` | **MEDIUM** | Cost variance indicator triggered (final contract value exceeds awarded amount by 36.0%, threshold 25.0%). Requires human review of approved variation orders, market price changes, or engineer estimates. |
| `ETH-FDRE-2025-003` | `ocds-ethpub-eth-fdre-2025-003` | Ministry of Innovation and Technology | Nile Tech Systems PLC | `RF-COMP-001` | **MEDIUM** | Open competitive tender (Open National Competitive Bidding) received only 1 bid. Requires human review of tender advertisement reach, qualification criteria, and technical specification neutrality. |
| `ETH-FDRE-2025-003` | `ocds-ethpub-eth-fdre-2025-003` | Ministry of Innovation and Technology | Nile Tech Systems PLC | `RF-TIME-001` | **MEDIUM** | Undocumented schedule slippage of 56 days (actual completion exceeded planned date, with no documented time extension). Requires human review of site logs, variation approvals, and liquidated damages applicability. |
| `ETH-FDRE-2025-006` | `ocds-ethpub-eth-fdre-2025-006` | Addis Ababa City Administration Health Bureau | Zemen General Contractors PLC | `RF-CONC-001` | **MEDIUM** | Supplier 'Zemen General Contractors PLC' holds 3 awards (18.8% of tenders, 27.2% of total ETB contract value; threshold 3). Requires human review of lot splitting, market capacity, and independent bid evaluation. |
| `ETH-FDRE-2025-006` | `ocds-ethpub-eth-fdre-2025-006` | Addis Ababa City Administration Health Bureau | Zemen General Contractors PLC | `RF-HANDOVER-001` | **HIGH** | Contract is marked 'completed' while final inspection/handover sign-off is 'missing'. Requires human verification of physical delivery certificates and inspection committee minutes before final closure. |
| `ETH-FDRE-2025-007` | `ocds-ethpub-eth-fdre-2025-007` | Ministry of Education | Zemen General Contractors PLC | `RF-COST-001` | **MEDIUM** | Cost variance indicator triggered (final contract value exceeds awarded amount by 33.6%, threshold 25.0%). Requires human review of approved variation orders, market price changes, or engineer estimates. |
| `ETH-FDRE-2025-007` | `ocds-ethpub-eth-fdre-2025-007` | Ministry of Education | Zemen General Contractors PLC | `RF-CONC-001` | **MEDIUM** | Supplier 'Zemen General Contractors PLC' holds 3 awards (18.8% of tenders, 27.2% of total ETB contract value; threshold 3). Requires human review of lot splitting, market capacity, and independent bid evaluation. |
| `ETH-FDRE-2025-008` | `ocds-ethpub-eth-fdre-2025-008` | Oromia Water and Energy Bureau | Rift Valley Water Works PLC | `RF-TIME-001` | **MEDIUM** | Undocumented schedule slippage of 68 days (actual completion exceeded planned date, with no documented time extension). Requires human review of site logs, variation approvals, and liquidated damages applicability. |
| `ETH-FDRE-2025-011` | `ocds-ethpub-eth-fdre-2025-011` | Ethiopian Roads Administration | Zemen General Contractors PLC | `RF-COMP-001` | **MEDIUM** | Open competitive tender (Open National Competitive Bidding) received only 1 bid. Requires human review of tender advertisement reach, qualification criteria, and technical specification neutrality. |
| `ETH-FDRE-2025-011` | `ocds-ethpub-eth-fdre-2025-011` | Ethiopian Roads Administration | Zemen General Contractors PLC | `RF-CONC-001` | **MEDIUM** | Supplier 'Zemen General Contractors PLC' holds 3 awards (18.8% of tenders, 27.2% of total ETB contract value; threshold 3). Requires human review of lot splitting, market capacity, and independent bid evaluation. |
| `ETH-FDRE-2025-013` | `ocds-ethpub-eth-fdre-2025-013` | Ministry of Innovation and Technology | Horn Connect Telecom Services | `RF-COST-001` | **MEDIUM** | Cost variance indicator triggered (awarded amount exceeds initial estimate by 32.5%, threshold 25.0%). Requires human review of approved variation orders, market price changes, or engineer estimates. |
| `ETH-FDRE-2025-014` | `ocds-ethpub-eth-fdre-2025-014` | Ministry of Education | Selam Industrial Machinery PLC | `RF-HANDOVER-001` | **MEDIUM** | Contract is marked 'completed' while final inspection/handover sign-off is 'pending'. Requires human verification of physical delivery certificates and inspection committee minutes before final closure. |
| `ETH-FDRE-2025-015` | `ocds-ethpub-eth-fdre-2025-015` | Oromia Water and Energy Bureau | Blue Nile Hydro Engineering | `RF-TIME-001` | **HIGH** | Undocumented schedule slippage of 259 days (contract remains 'delayed' past planned completion date as of 2026-11-19, with no documented time extension). Requires human review of site logs, variation approvals, and liquidated damages applicability. |

## 5. Provenance & SHA-256 Verification

| Artifact | SHA-256 Digest |
|---|---|
| Input CSV (`sample_tenders.csv`) | `a1ff920b9f5234372194c747a0262cc2b8c518488096d78e35971658bb0a8fcc` |
| OCDS Release Package (`ocds_releases.json`) | `d97af464880cfe2efcb23ebfe26a06bfa04d352afa84d571157e0630e6d374d7` |
| JSON Audit Report (`audit_report.json`) | `2e8a46f8f308341f92f198ecb475a2a02a0299ad0187acd0e0c8ecb9ccf6d92a` |

All artifact hashes are also recorded in `provenance_hashes.sha256` for automated integrity checks.
