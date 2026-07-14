
import pandas as pd
import requests
import json
import time
import os
from pathlib import Path

# Use a relative path to the data directory
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw"

USA_SPENDING_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
FEDERAL_API_HEADERS = {"Content-Type": "application/json"}

def fetch_federal_contracts(vendor_name: str, state_code: str = "AZ", start_date: str = "2007-10-01", end_date: str = "2024-12-31") -> tuple:
    """
    Fetches federal contract data for a given vendor and state from USAspending API.
    Returns (total_federal_awards, total_federal_value).
    """
    total_federal_awards = 0
    total_federal_value = 0.0
    page = 1
    has_next_page = True

    while has_next_page:
        payload = {
            "filters": {
                "time_period": [{"start_date": start_date, "end_date": end_date}],
                "recipient_search_text": [vendor_name],
                "pop_state_code": state_code,
                "award_type_codes": ["A", "B", "C", "D", "IDV_A", "IDV_B", "IDV_C", "IDV_D", "IDV_E", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11"]
            },
            "fields": ["total_obligation"],
            "limit": 100, # Max limit per page
            "page": page,
            "sort": "total_obligation",
            "order": "desc",
        }

        try:
            response = requests.post(USA_SPENDING_URL, headers=FEDERAL_API_HEADERS, data=json.dumps(payload))
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            data = response.json()

            if data and "results" in data:
                for award in data["results"]:
                    total_federal_awards += 1
                    total_federal_value += award.get("total_obligation", 0)

            has_next_page = data.get("page_metadata", {}).get("has_next_page", False)
            page += 1
            time.sleep(0.1) # Be a good API citizen

        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error fetching federal data for {vendor_name}: {e}")
            print(f"Response body: {response.text}")
            break
        except Exception as e:
            print(f"An error occurred fetching federal data for {vendor_name}: {e}")
            break
    return total_federal_awards, total_federal_value

def link_renewals_to_federal(
    renewal_vendors_path=DATA_DIR / "top_renewal_vendors.csv",
    output_path=DATA_DIR / "federal_renewal_linkage_report.csv"
):
    """
    Links local renewal vendors to federal contracts in Arizona.
    """
    if not os.path.exists(renewal_vendors_path):
        print(f"Error: Top renewal vendors file not found at {renewal_vendors_path}")
        return

    local_renewals_df = pd.read_csv(renewal_vendors_path)

    federal_data = []
    for index, row in local_renewals_df.iterrows():
        vendor_name = row["ContractVendorName"]
        print(f"Fetching federal data for {vendor_name}...")
        federal_awards, federal_value = fetch_federal_contracts(vendor_name)
        federal_data.append({
            "ContractVendorName": vendor_name,
            "total_federal_awards_az": federal_awards,
            "total_federal_value_az": federal_value
        })

    federal_df = pd.DataFrame(federal_data)

    # Merge local and federal data
    final_report_df = pd.merge(local_renewals_df, federal_df, on="ContractVendorName", how="left")

    # Save the final report
    final_report_df.to_csv(output_path, index=False)
    print(f"Federal renewal linkage report saved to {output_path}")
    print(final_report_df.to_markdown(index=False))

if __name__ == "__main__":
    link_renewals_to_federal()
