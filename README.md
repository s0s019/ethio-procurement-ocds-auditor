# ethio-procurement-ocds-auditor

An open-source civic technology and public finance transparency starter toolkit for normalizing Ethiopian public procurement records into the **Open Contracting Data Standard (OCDS 1.1)**, running deterministic red-flag risk checks, and producing tamper-evident audit artifacts backed by **SHA-256 provenance hashes**.

---

## Project Purpose & Scope

Public procurement represents one of the largest channels of public expenditure in Ethiopia across infrastructure, health, education, water, agriculture, and digital public infrastructure. Ethiopia's **Federal Public Procurement and Property Administration Proclamation No. 1333/2024** (which replaced Proclamation No. 649/2009 and expanded coverage to public enterprises) emphasizes transparency, accessibility, and administrative accountability throughout the procurement lifecycle.

Raw procurement spreadsheets or portal exports are often fragmented, inconsistently named, and difficult to analyze across agencies. Normalizing these records into **OCDS** enables:

- **Interoperable public oversight:** A standardized schema (`ocid`, `parties`, `tender`, `awards`, `contracts`) that journalists, supreme audit institutions, civil society, and procurement authorities can inspect with shared tools.
- **Cross-entity analysis:** Deterministic party identifiers make it possible to track supplier concentration and repeat awards across ministries, bureaus, and public enterprises.
- **Reproducible audit trails:** Every run generates canonical JSON/Markdown outputs alongside SHA-256 digests so reviewers can verify that reports correspond exactly to the source dataset.

> **Important Framing:** Flagged items are **red-flag risk indicators requiring human review or formal audit verification**. They are **never** automatic proof of corruption, fraud, or legal guilt.

---

## Architecture & Data Flow

```text
+---------------------------+
|   Raw CSV Procurement     |
|   Input (ETB, EC/GC)      |
+-------------+-------------+
              |
              |  1. Parse, validate & coerce types
              v
+-------------+-------------+
|  Normalization & OCDS 1.1 |
|  Release Package Builder  |
|  (ocid, tender, awards,   |
|   contracts, parties)     |
+-------------+-------------+
              |
              |  2. Run configurable heuristics
              v
+-------------+-------------+
|  Deterministic Red-Flag   |
|  Checks (Cost, Single Bid,|
|  Concentration, Delay,    |
|  Missing Handover Signoff)|
+-------------+-------------+
              |
              |  3. Generate reports & digests
              v
+-------------+-------------+
|  Audit Outputs + Provenance|
|  - ocds_releases.json     |
|  - audit_report.json      |
|  - audit_summary.md       |
|  - provenance_hashes.sha256|
+---------------------------+
