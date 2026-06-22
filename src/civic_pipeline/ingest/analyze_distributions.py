import pandas as pd

# Load the local CSV
file_path = "/ramdisk/contracts.csv"
df = pd.read_csv(file_path, keep_default_na=False)

# Convert financial values to numeric
df["Estimated Contract Value"] = pd.to_numeric(df["Estimated Contract Value"], errors="coerce")

print("==================================================")
print("             KEY VALUE DISTRIBUTIONS              ")
print("==================================================")

# 1. Top Document Types
print("\n📋 Top 5 Document Types:")
print(df["DocumentType"].value_counts().head(5))

# 2. Top Statuses
print("\n🛡️ Contract Status Distribution:")
print(df["ContractStatus"].value_counts())

# 3. Top 5 Vendors by Record Count
print("\n🏢 Top 5 Most Frequent Vendors (by number of contracts/amendments):")
print(df["ContractVendorName"].value_counts().head(5))

# 4. Top 5 Vendors by Total Financial Value
print("\n💰 Top 5 Vendors by Cumulative Estimated Value:")
top_spend_vendors = df.groupby("ContractVendorName")["Estimated Contract Value"].sum().sort_values(ascending=False).head(5)
for vendor, value in top_spend_vendors.items():
    print(f"  {vendor:<50} | ${value:,.2f}")

# 5. Financial Statistics
print("\n💵 Financial Value Stats:")
stats = df["Estimated Contract Value"].describe()
print(f"  Total Estimated Active/Closed Value: ${df['Estimated Contract Value'].sum():,.2f}")
print(f"  Mean Value per Record:               ${stats['mean']:,.2f}")
print(f"  Max Single Contract Value:           ${stats['max']:,.2f}")
print("==================================================")