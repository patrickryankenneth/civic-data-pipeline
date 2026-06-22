# civic-data-pipeline

A production-style data pipeline that extracts municipal procurement data from a
city's PowerBI dashboard (no public download available), profiles data quality,
and cross-references vendors against federal spending records.

Built as a portfolio project demonstrating end-to-end data engineering without
access to official APIs or data exports.

---

## What it does

**Source:** City of Tempe Procurement Contracts dashboard (PowerBI Gov, updated weekly)  
**Method:** Reverse-engineered the PowerBI DSR binary protocol to extract structured data programmatically  
**Output:** 9,502 contract records across 928 vendors, representing ~$23B in estimated contract value

```
PowerBI Gov endpoint
  └── DSR binary decode (bit-mask reconstruction, value dict resolution)
        └── contracts.csv  (14 columns, 9,502 rows)
              ├── pipeline_profiler.py   → data quality report
              ├── analyze_distributions.py → vendor/value distributions
              └── join_federal.py        → USASpending.gov cross-reference
```

---

## Pipeline stages

### 1. Extraction (`ingest/extract_contracts.py`)

Queries the PowerBI internal querydata API with a manually constructed
SemanticQueryDataShapeCommand payload. Decodes the DSR (Data Shape Response)
format including:

- Bitmask-based row reconstruction (`R` = repeat, `Ø` = null)
- ValueDict index resolution for categorical columns
- Millisecond timestamp conversion for date fields
- Dual-table join across `ContractHistory` and `MasterContracts` entities

Outputs 9,502 records to CSV with 14 verified columns.

### 2. Data quality profiling (`ingest/pipeline_profiler.py`)

Pure-Python profiler (no pandas) that reports per-column:
- Null / empty count
- Literal N/A strings
- Unique value cardinality
- Sample value

Key findings: `DocumentDescription` is 97% null (expected — only populated on
amendments). `Master Contract Number` and `Estimated Contract Value` have ~0.6%
nulls (child records without a parent master contract).

### 3. Distribution analysis (`ingest/analyze_distributions.py`)

- Top document types: Renewal Effective (27%), Pricing Effective (14%), Vendor Offer (13%)
- Status: 68% Closed, 32% Approved, 0.2% Open
- Top vendor by contract count: LEGEND TECHNICAL SERVICES (254 documents)
- Top vendor by cumulative value: ALLEGIANCE BENEFIT PLAN MANAGEMENT ($516M)
- Total portfolio value: $23.0B across all records

### 4. Federal cross-reference (`discovery/join_federal.py`)

Matches local vendors by name against the
[USASpending.gov API](https://api.usaspending.gov/api/v2/search/spending_by_award/)
to identify vendors with a federal contract footprint in Arizona.

For each vendor returns:
- Total federal award value (AZ place of performance)
- Federal award count
- Top awarding federal agency
- USASpending matched recipient name (for fuzzy-match validation)

Initial test: 2 of the top 5 vendors by local value (LEGEND TECHNICAL SERVICES,
SGS NORTH AMERICA INC) have confirmed federal contracts in Arizona.

---

## Data dictionary (14 columns)

| Column | Source table | Notes |
|---|---|---|
| DocumentPdf | ContractHistory | S3-hosted PDF URL |
| ContractNo | ContractHistory | Child contract number (e.g. T25-005-01) |
| DocumentType | ContractHistory | Renewal Effective, Pricing Effective, etc. |
| DocumentDescription | ContractHistory | 97% null |
| ContractVendorName | ContractHistory | 928 unique vendors |
| ContractDescription | ContractHistory | |
| ContractStatus | ContractHistory | Approved / Closed / Open |
| DocumentAddDate | ContractHistory | Date record added to system |
| ContractBeginDate | ContractHistory | |
| ContractRenewalEndDate | ContractHistory | |
| ContractExpirationDate | ContractHistory | |
| Master Contract Number | ContractHistory | Parent contract (e.g. 25-005) |
| Estimated Contract Value | MasterContracts | Value at master contract level |
| Master Contract Description | MasterContracts | |

---

## Setup

```bash
git clone https://github.com/patrickryankenneth/civic-data-pipeline.git
cd civic-data-pipeline
python -m venv .venv && source .venv/bin/activate
pip install requests pandas
```

Run the full pipeline:

```bash
# 1. Extract from PowerBI
python src/civic_pipeline/ingest/extract_contracts.py

# 2. Profile data quality
python src/civic_pipeline/ingest/pipeline_profiler.py

# 3. Analyze distributions
python src/civic_pipeline/ingest/analyze_distributions.py

# 4. Cross-reference against federal spending (top 50 vendors, ~30 sec)
python src/civic_pipeline/discovery/join_federal.py \
  --input /tmp/contracts.csv \
  --top 50 \
  --output vendor_federal_crossref.csv
```

---

## Key technical decisions

**Why reverse-engineer PowerBI instead of downloading the CSV?**
The dashboard has no export button. The data is published as a public PowerBI
Gov report but locked behind the DSR protocol. Decoding it directly was the
only programmatic path to the data.

**Why pure Python for the profiler?**
The profiler runs immediately after extraction in the same process. Avoiding a
pandas import keeps the extraction stage dependency-free and fast.

**Why USASpending for enrichment instead of SAM.gov?**
USASpending has a fully public REST API requiring no account or API key.
SAM.gov requires registration and has stricter rate limits. For vendor
footprint analysis, USASpending award data is sufficient.

---

## Data source

**City of Tempe Procurement Contracts**  
Published by: Michael Greene, Procurement Administration (michael_greene@tempe.gov)  
Updated: Weekly (automated)  
Source systems: SQL Server, Oracle, PDF document storage  
Public dashboard: https://data.tempe.gov/documents/bb33874274f44b6384598b633b017a4e