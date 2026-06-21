import json
import pandas as pd

with open('/ramdisk/raw_contracts.json', 'r') as f:
    data = json.load(f)

# The first element seems to contain schema metadata 'S', others just data.
# We want to extract 'G0' from all elements.
records = []
for entry in data:
    if 'G0' in entry:
        records.append({'Contract Vendor Name': entry['G0']})

df = pd.DataFrame(records)
df.to_csv('/ramdisk/contracts.csv', index=False)
print(f"Successfully processed {len(df)} records into /ramdisk/contracts.csv")
