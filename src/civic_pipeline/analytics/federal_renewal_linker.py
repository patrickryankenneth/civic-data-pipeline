import pandas as pd
import requests
import json
import time
import os
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw"
USA_SPENDING_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
FEDERAL_API_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
CACHE_PATH = DATA_DIR / "federal_vendor_cache.csv"
MAX_WORKERS = 1


CONTRACT_TYPE_CODES = ["A", "B", "C", "D"]
IDV_TYPE_CODES = ["IDV_A", "IDV_B", "IDV_C", "IDV_D", "IDV_E"]


def _fetch_award_type_group(vendor_name: str, award_type_codes: list, state_code: str,
                             start_date: str, end_date: str, max_retries: int = 3):
    results = []
    page = 1
    has_next_page = True

    while has_next_page:
        payload = {
            "filters": {
                "time_period": [{"start_date": start_date, "end_date": end_date}],
                "recipient_search_text": [vendor_name],
                "place_of_performance_locations": [{"country": "USA", "state": state_code}],
                "award_type_codes": award_type_codes
            },
            "fields": ["Award Amount", "Recipient Name", "Awarding Agency",
                       "Start Date", "End Date", "Contract Award Type"],
            "limit": 100,
            "page": page,
            "sort": "Award Amount",
            "order": "desc",
        }

        data = None
        for attempt in range(max_retries):
            try:
                response = requests.post(USA_SPENDING_URL, headers=FEDERAL_API_HEADERS,
                                          data=json.dumps(payload), timeout=30)
                response.raise_for_status()
                data = response.json()
                break
            except requests.exceptions.HTTPError:
                if response.status_code == 422:
                    raise RuntimeError(f"422 on {vendor_name}: {response.text[:300]}")
                if attempt == max_retries - 1:
                    raise
                time.sleep((2 ** attempt) + random.uniform(0, 1))
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, OSError):
                if attempt == max_retries - 1:
                    raise
                time.sleep(random.uniform(2, 5))

        if data and "results" in data:
            results.extend(data["results"])

        has_next_page = data.get("page_metadata", {}).get("hasNext", False) if data else False
        page += 1

    return results


def fetch_federal_contracts(vendor_name: str, state_code: str = "AZ",
                             start_date: str = "2007-10-01", end_date: str = "2024-12-31"):
    contracts = _fetch_award_type_group(vendor_name, CONTRACT_TYPE_CODES, state_code, start_date, end_date)
    idvs = _fetch_award_type_group(vendor_name, IDV_TYPE_CODES, state_code, start_date, end_date)
    return vendor_name, contracts, idvs


def process_vendor(vendor_name: str):
    try:
        _, contracts, idvs = fetch_federal_contracts(vendor_name)
    except Exception as e:
        print(f"FAILED (will retry next run): {vendor_name}: {e}")
        return None

    return {
        "ContractVendorName": vendor_name,
        "total_contract_awards": len(contracts),
        "total_contract_value": sum(a.get("Award Amount", 0) or 0 for a in contracts),
        "total_idv_awards": len(idvs),
        "total_idv_value": sum(a.get("Award Amount", 0) or 0 for a in idvs),
    }


def link_renewals_to_federal(
    renewal_vendors_path=DATA_DIR / "contracts.csv",
    output_path=DATA_DIR / "federal_renewal_linkage_report.csv"
):
    if not os.path.exists(renewal_vendors_path):
        print(f"Error: {renewal_vendors_path} not found")
        return

    local_df = pd.read_csv(renewal_vendors_path)
    unique_vendors = sorted(local_df["ContractVendorName"].dropna().unique())
    print(f"{len(unique_vendors)} unique vendors to process (deduplicated)")

    already_done = set()
    if CACHE_PATH.exists():
        cached_df = pd.read_csv(CACHE_PATH)
        already_done = set(cached_df["ContractVendorName"])
        print(f"Resuming — {len(already_done)} vendors already cached")
    else:
        pd.DataFrame(columns=[
            "ContractVendorName", "total_contract_awards", "total_contract_value",
            "total_idv_awards", "total_idv_value"
        ]).to_csv(CACHE_PATH, index=False)

    todo = [v for v in unique_vendors if v not in already_done]
    print(f"{len(todo)} vendors remaining")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_vendor, v): v for v in todo}
        for i, future in enumerate(as_completed(futures), 1):
            vendor = futures[future]
            try:
                result = future.result()
            except Exception as e:
                print(f"Failed on {vendor}: {e}")
                continue

            if result is None:
                continue

            pd.DataFrame([result]).to_csv(CACHE_PATH, mode="a", header=False, index=False)
            print(f"[{i}/{len(todo)}] {vendor} done "
                  f"({result['total_contract_awards']} contracts, {result['total_idv_awards']} IDVs)")

    federal_df = pd.read_csv(CACHE_PATH)
    final_report_df = pd.merge(local_df, federal_df, on="ContractVendorName", how="left")
    final_report_df.to_csv(output_path, index=False)
    print(f"Report saved to {output_path}")


if __name__ == "__main__":
    link_renewals_to_federal()