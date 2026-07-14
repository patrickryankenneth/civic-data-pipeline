import pandas as pd
from pathlib import Path

data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw"
df = pd.read_csv(data_dir / 'contracts.csv', keep_default_na=False)
df['Estimated Contract Value'] = pd.to_numeric(df['Estimated Contract Value'], errors='coerce')
df['UniqueContractID'] = df['Master Contract Number'].replace('', None).fillna(df['ContractNo'])

# 1. Calculate Churn (how many document rows per contract)
churn = df.groupby('UniqueContractID').size().to_frame('ChurnCount')
df = df.merge(churn, on='UniqueContractID')

# 2. Identify Expiring Soon
df['ContractExpirationDate'] = pd.to_datetime(df['ContractExpirationDate'], errors='coerce')
active = df[df['ContractStatus'] == 'Approved']
expiring_soon = active[(active['ContractExpirationDate'].dt.year >= 2026) & (active['ContractExpirationDate'].dt.year <= 2027)].drop_duplicates(subset=['UniqueContractID'])

# 3. Score them
# Risk Score: Higher Churn + High Value + Low Federal Overlap = VULNERABLE
expiring_soon['RiskScore'] = (expiring_soon['ChurnCount'] * 0.1) + (expiring_soon['Estimated Contract Value'] / 1_000_000)

print('====================================================================')
print('        ⚡ CONTRACT VULNERABILITY WATCHLIST (2026-2027) ⚡           ')
print('====================================================================')
for _, row in expiring_soon.sort_values('RiskScore', ascending=False).head(10).iterrows():
    print(f"Vendor: {str(row['ContractVendorName'])[:30]:<30} | Value: ${row['Estimated Contract Value']:>10,.0f} | Churn: {row['ChurnCount']:>2} | Score: {row['RiskScore']:.1f}")
