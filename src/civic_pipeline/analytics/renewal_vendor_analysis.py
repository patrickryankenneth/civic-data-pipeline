
import pandas as pd
import os
from pathlib import Path

# Use a relative path to the data directory, ensuring it exists
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw"
os.makedirs(DATA_DIR, exist_ok=True)

def analyze_renewal_vendors(contracts_path=DATA_DIR / "contracts.csv", output_path=DATA_DIR / "top_renewal_vendors.csv", top_n=10):
    """
    Analyzes local contracts to identify vendors with the most "Renewal Effective" contracts.

    Args:
        contracts_path (str): Path to the local contracts CSV file.
        output_path (str): Path to save the CSV of top renewal vendors.
        top_n (int): Number of top vendors to identify.
    """
    if not os.path.exists(contracts_path):
        print(f"Error: Contracts file not found at {contracts_path}")
        return

    df = pd.read_csv(contracts_path)

    # Filter for "Renewal Effective" documents
    renewal_df = df[df['DocumentType'] == 'Renewal Effective']

    if renewal_df.empty:
        print("No 'Renewal Effective' contracts found.")
        return

    # Group by vendor and count renewals, also sum estimated value
    vendor_renewal_summary = renewal_df.groupby('ContractVendorName').agg(
        renewal_count=('DocumentType', 'count'),
        total_renewal_value=('Estimated Contract Value', 'sum')
    ).reset_index()

    # Sort by renewal count and get top N
    top_renewal_vendors = vendor_renewal_summary.sort_values(by='renewal_count', ascending=False).head(top_n)

    # Save the top vendors to a CSV
    top_renewal_vendors.to_csv(output_path, index=False)
    print(f"Top {top_n} renewal vendors saved to {output_path}")
    print(top_renewal_vendors.to_markdown(index=False))

if __name__ == "__main__":
    analyze_renewal_vendors()
