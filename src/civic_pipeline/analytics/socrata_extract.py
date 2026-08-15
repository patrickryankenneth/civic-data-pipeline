"""
Socrata SODA API extractor.

Unlike the Tempe PowerBI DSR extractor, Socrata-hosted portals expose a
standard, documented REST API (no protocol reverse-engineering needed).
Any Socrata dataset can be queried at:

    https://{domain}/resource/{dataset_id}.json?$limit=N&$offset=M

This module is written as a generic Socrata extractor so it can be pointed
at any Socrata-hosted dataset by changing DOMAIN / DATASET_ID, not just
NY State's procurement report.
"""

import requests
import pandas as pd
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw"

DOMAIN = "data.ny.gov"
DATASET_ID = "ehig-g5x3"  # Procurement Report for State Authorities
BASE_URL = f"https://{DOMAIN}/resource/{DATASET_ID}.json"

PAGE_SIZE = 1000  # Socrata's default max without an app token is usually 1000
MAX_RETRIES = 3


def fetch_page(offset: int, limit: int = PAGE_SIZE) -> list[dict]:
    """Fetch a single page of results from the Socrata SODA API."""
    params = {"$limit": limit, "$offset": offset, "$order": ":id"}
    # $order=:id ensures stable pagination — without an explicit order,
    # Socrata doesn't guarantee consistent row ordering across pages,
    # which could silently duplicate or skip rows mid-extraction.

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            print(f"HTTP error at offset {offset}: {response.status_code} — {response.text[:200]}")
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)

    return []


def extract_all(output_path: Path = None) -> pd.DataFrame:
    """
    Paginate through the full dataset and return it as a DataFrame.
    Writes incrementally to CSV so a Ctrl+C or crash doesn't lose progress —
    same resumable pattern used in federal_renewal_linker.py.
    """
    if output_path is None:
        output_path = DATA_DIR / f"ny_state_procurement_raw.csv"

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    offset = 0
    total_rows = 0
    first_write = True

    # Resume support: if the output file already exists, figure out how
    # many rows we already have and skip that many pages.
    if output_path.exists():
        existing = pd.read_csv(output_path)
        total_rows = len(existing)
        offset = (total_rows // PAGE_SIZE) * PAGE_SIZE
        print(f"Resuming from offset {offset} ({total_rows} rows already saved)")
        first_write = False

    while True:
        print(f"Fetching offset {offset}...")
        page = fetch_page(offset)

        if not page:
            print("Empty page — extraction complete.")
            break

        df_page = pd.DataFrame(page)
        df_page.to_csv(
            output_path,
            mode="a" if not first_write else "w",
            header=first_write,
            index=False
        )
        first_write = False

        total_rows += len(page)
        print(f"  -> {len(page)} rows (total so far: {total_rows})")

        if len(page) < PAGE_SIZE:
            print("Final page reached (short page).")
            break

        offset += PAGE_SIZE
        time.sleep(0.2)  # be a good API citizen

    print(f"Extraction complete: {total_rows} rows saved to {output_path}")
    return pd.read_csv(output_path)


if __name__ == "__main__":
    extract_all()