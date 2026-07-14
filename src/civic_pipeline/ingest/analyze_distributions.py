import pandas as pd
from pathlib import Path

# Load the local CSV
data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw"
file_path = data_dir / "contracts.csv"
df = pd.read_csv(file_path, keep_default_na=False)

# Convert financial values to numeric
df["Estimated Contract Value"] = pd.to_numeric(df["Estimated Contract Value"], errors="coerce")

# Handle unique contract ID creation
# If 'Master Contract Number' is empty, fall back to 'ContractNo' so we don't discard standalone contracts
df['UniqueContractID'] = df['Master Contract Number'].replace('', None).fillna(df['ContractNo'])
df_deduped = df.drop_duplicates(subset=['UniqueContractID'])

print("==================================================")
print("        DEDUPLICATED VALUE DISTRIBUTIONS          ")
print("==================================================")

# 1. Top Document Types (from transaction rows)
print("1. Document Types (Transaction Row Counts):")
print(df["DocumentType"].value_counts().head(5))
print("-" * 50)

# 2. Top Statuses
print("\n2. Contract Status (Transaction Row Counts):")
print(df["ContractStatus"].value_counts())
print("-" * 50)

# 3. Top 5 Vendors by Record Count
print("\n3. Top 5 Most Frequent Vendors (by transaction row counts):")
print(df["ContractVendorName"].value_counts().head(5))
print("-" * 50)

# 4. Top 5 Vendors by Total Financial Value (DEDUPLICATED)
print("\n4. Top 5 Vendors by Total Financial Value (Deduplicated on Unique Contracts):")
top_spend_vendors = df_deduped.groupby("ContractVendorName")["Estimated Contract Value"].sum().sort_values(ascending=False).head(5)
for vendor, value in top_spend_vendors.items():
    print(f"  {vendor:<50} | ${value:,.2f}")
print("-" * 50)

# 5. Financial Statistics Comparison
print("\n5. Financial Value Stats (Raw vs. Deduplicated):")
raw_total = df["Estimated Contract Value"].sum()
deduped_total = df_deduped["Estimated Contract Value"].sum()
stats_deduped = df_deduped["Estimated Contract Value"].describe()

print(f"  Raw Sum (Inflated by Fan-out):     ${raw_total:,.2f}")
print(f"  Deduplicated Sum (True Total):     ${deduped_total:,.2f}")
print(f"  Mean Value per Unique Contract:     ${stats_deduped['mean']:,.2f}")
print(f"  Max Single Contract Value:          ${stats_deduped['max']:,.2f}")
print("==================================================")