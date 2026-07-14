"""
link_vendors_to_federal.py
--------------------------
Cross-references Tempe procurement vendors against USASpending.gov federal awards.

Strategy:
  1. Load contracts.csv, deduplicate vendors, rank by total local contract value
  2. For the top N vendors, query USASpending /spending_by_award/ with recipient_search_text
  3. Output a ranked CSV: local_value, federal_value, federal_award_count, top_federal_agency
  4. Print a summary report

Rate limiting: USASpending allows ~10 req/sec sustained. We use 0.3s sleep between
calls and exponential backoff on 429s. Scanning top 100 vendors takes ~35 seconds.

Usage:
  python link_vendors_to_federal.py --input /ramdisk/contracts.csv --top 100 --output vendor_federal_crossref.csv
"""

import requests
import csv
import json
import time
import argparse
import sys
from collections import defaultdict
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────

USA_SPENDING_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
RATE_LIMIT_SLEEP = 0.35   # seconds between requests
MAX_RETRIES      = 3
RETRY_BACKOFF    = 2.0    # seconds, doubles each retry

# Fetch awards across all years we care about
TIME_PERIODS = [
    {"start_date": "2019-10-01", "end_date": "2026-09-30"}
]

AWARD_TYPE_CODES = ["A", "B", "C", "D"]  # all contract types

FIELDS = [
    "Award ID",
    "Award Amount",
    "Awarding Agency",
    "Recipient Name",
    "Start Date",
    "End Date",
    "Description",
    "recipient_id",
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_vendors(csv_path: str) -> list[dict]:
    """
    Read contracts.csv, aggregate by vendor:
      - total_local_value
      - contract_count (unique Master Contract Numbers)
      - document_count (rows)
    Returns list of dicts sorted by total_local_value desc.
    """
    agg = defaultdict(lambda: {
        "total_local_value": 0.0,
        "master_contracts": set(),
        "document_count": 0,
    })

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["ContractVendorName"].strip()
            if not name:
                continue
            try:
                val = float(row["Estimated Contract Value"]) if row["Estimated Contract Value"] else 0.0
            except ValueError:
                val = 0.0

            agg[name]["total_local_value"] += val
            agg[name]["document_count"] += 1
            mcn = row.get("Master Contract Number", "").strip()
            if mcn:
                agg[name]["master_contracts"].add(mcn)

    result = []
    for vendor, stats in agg.items():
        result.append({
            "vendor_name": vendor,
            "total_local_value": stats["total_local_value"],
            "local_contract_count": len(stats["master_contracts"]),
            "local_document_count": stats["document_count"],
        })

    result.sort(key=lambda x: x["total_local_value"], reverse=True)
    return result


def query_usaspending(vendor_name: str) -> dict:
    """
    Search USASpending for a vendor by name.
    Returns:
      {
        "federal_total": float,
        "federal_award_count": int,
        "top_agency": str,
        "matched_name": str,  # what USASpending returned as recipient name
      }
    """
    payload = {
        "filters": {
            "time_period": TIME_PERIODS,
            "award_type_codes": AWARD_TYPE_CODES,
            "recipient_search_text": [vendor_name],
        },
        "fields": FIELDS,
        "limit": 100,
        "page": 1,
        "sort": "Award Amount",
        "order": "desc",
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(USA_SPENDING_URL, json=payload, timeout=15)

            if resp.status_code == 429:
                wait = RETRY_BACKOFF * (2 ** attempt)
                print(f"  [rate limit] sleeping {wait:.1f}s ...", flush=True)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])

            if not results:
                return {"federal_total": 0.0, "federal_award_count": 0, "top_agency": "", "matched_name": ""}

            federal_total = sum(
                float(r.get("Award Amount") or 0) for r in results
            )
            award_count = data.get("page_metadata", {}).get("total", len(results))

            # Tally agencies
            agency_tally = defaultdict(float)
            for r in results:
                agency = r.get("Awarding Agency") or "Unknown"
                agency_tally[agency] += float(r.get("Award Amount") or 0)
            top_agency = max(agency_tally, key=agency_tally.get) if agency_tally else ""

            matched_name = results[0].get("Recipient Name", "") if results else ""

            return {
                "federal_total": federal_total,
                "federal_award_count": award_count,
                "top_agency": top_agency,
                "matched_name": matched_name,
            }

        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF)
            else:
                print(f"  [error] {vendor_name}: {e}", flush=True)
                return {"federal_total": 0.0, "federal_award_count": 0, "top_agency": "", "matched_name": ""}

    return {"federal_total": 0.0, "federal_award_count": 0, "top_agency": "", "matched_name": ""}


def fmt_usd(val: float) -> str:
    return f"${val:,.0f}"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cross-reference Tempe vendors with USASpending federal data")
    parser.add_argument("--input",  default="/ramdisk/contracts.csv", help="Path to contracts.csv")
    parser.add_argument("--top",    type=int, default=50,             help="Number of top vendors to query (by local $ value)")
    parser.add_argument("--output", default="vendor_federal_crossref.csv", help="Output CSV path")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  Tempe Contracts ↔ USASpending Federal Cross-Reference")
    print(f"{'='*60}")
    print(f"  Input:  {args.input}")
    print(f"  Output: {args.output}")
    print(f"  Querying top {args.top} vendors by local contract value")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Load and rank vendors
    print("Loading vendors from contracts.csv ...")
    vendors = load_vendors(args.input)
    print(f"  Found {len(vendors)} unique vendors total.")

    top_vendors = vendors[:args.top]
    total_local_in_scope = sum(v["total_local_value"] for v in top_vendors)
    all_local_total      = sum(v["total_local_value"] for v in vendors)

    print(f"  Top {args.top} vendors represent {fmt_usd(total_local_in_scope)} "
          f"of {fmt_usd(all_local_total)} total local value "
          f"({100*total_local_in_scope/all_local_total:.1f}%)\n")

    # Query USASpending for each vendor
    results = []
    for i, vendor in enumerate(top_vendors, 1):
        name = vendor["vendor_name"]
        print(f"  [{i:>3}/{args.top}] {name[:55]:<55}", end=" ", flush=True)

        fed = query_usaspending(name)
        time.sleep(RATE_LIMIT_SLEEP)

        row = {**vendor, **fed}
        results.append(row)

        status = fmt_usd(fed["federal_total"]) if fed["federal_total"] > 0 else "not found"
        print(f"→ {status}", flush=True)

    # Write output CSV
    fieldnames = [
        "vendor_name",
        "total_local_value",
        "local_contract_count",
        "local_document_count",
        "federal_total",
        "federal_award_count",
        "top_agency",
        "matched_name",
    ]

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n  ✅ Wrote {len(results)} rows to {args.output}")

    # ── Summary Report ──────────────────────────────────────────────────────
    found     = [r for r in results if r["federal_total"] > 0]
    not_found = [r for r in results if r["federal_total"] == 0]

    total_federal = sum(r["federal_total"] for r in found)

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    print(f"  Vendors with federal footprint: {len(found)} / {len(results)}")
    print(f"  Total federal award value found: {fmt_usd(total_federal)}")
    print(f"  Total local contract value (top {args.top}): {fmt_usd(total_local_in_scope)}")

    print(f"\n  Top 10 by COMBINED local + federal value:")
    results_sorted = sorted(results, key=lambda x: x["total_local_value"] + x["federal_total"], reverse=True)
    print(f"  {'Vendor':<45} {'Local':>14} {'Federal':>14} {'Top Agency'}")
    print(f"  {'-'*45} {'-'*14} {'-'*14} {'-'*30}")
    for r in results_sorted[:10]:
        agency_short = r["top_agency"][:30] if r["top_agency"] else "—"
        print(f"  {r['vendor_name'][:45]:<45} {fmt_usd(r['total_local_value']):>14} "
              f"{fmt_usd(r['federal_total']):>14}  {agency_short}")

    if not_found:
        print(f"\n  Vendors with NO federal record ({len(not_found)}):")
        for r in not_found[:10]:
            print(f"    - {r['vendor_name']} (local: {fmt_usd(r['total_local_value'])})")
        if len(not_found) > 10:
            print(f"    ... and {len(not_found)-10} more (see CSV)")

    print(f"\n  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()