import json
import urllib.request
import urllib.error
import uuid
import ssl
import os
import csv
import datetime
import shutil
from pathlib import Path

# Fallback to /tmp/ramdisk if we don't have sudo permissions for root /ramdisk
try:
    os.makedirs("/ramdisk", exist_ok=True)
    RAMDISK_DIR = "/ramdisk"
except PermissionError:
    RAMDISK_DIR = "/tmp/ramdisk"
    os.makedirs(RAMDISK_DIR, exist_ok=True)

# The exact 14 columns mapped to their correct tables and backend properties
fields = [
    # ContractHistory columns (12)
    {"entity": "ContractHistory", "property": "Document Pdf", "source": "c"},
    {"entity": "ContractHistory", "property": "Contract Number", "source": "c"},
    {"entity": "ContractHistory", "property": "Document Type", "source": "c"},
    {"entity": "ContractHistory", "property": "Document Description", "source": "c"},
    {"entity": "ContractHistory", "property": "Contract Vendor Name", "source": "c"},
    {"entity": "ContractHistory", "property": "Contract Description", "source": "c"},
    {"entity": "ContractHistory", "property": "Contract Status", "source": "c"},
    {"entity": "ContractHistory", "property": "Document Add Date", "source": "c"},
    {"entity": "ContractHistory", "property": "Contract Begin Date", "source": "c"},
    {"entity": "ContractHistory", "property": "Contract Renewal End Date", "source": "c"},
    {"entity": "ContractHistory", "property": "Contract Expiration Date", "source": "c"},
    {"entity": "ContractHistory", "property": "MasterContractNo", "source": "c"},  # <--- VERIFIED!

    # MasterContracts columns (2)
    {"entity": "MasterContracts", "property": "EstimatedContractValue", "source": "m"},
    {"entity": "MasterContracts", "property": "MasterContractDescription", "source": "m"}
]

# The clean headers expected by your data dictionary/downstream pipeline
expected_headers = [
    "DocumentPdf", 
    "ContractNo", 
    "DocumentType", 
    "DocumentDescription", 
    "ContractVendorName", 
    "ContractDescription", 
    "ContractStatus", 
    "DocumentAddDate", 
    "ContractBeginDate", 
    "ContractRenewalEndDate", 
    "ContractExpirationDate", 
    "Master Contract Number", 
    "Estimated Contract Value", 
    "Master Contract Description"
]

def is_bit_set(index, bitset):
    return (bitset >> index) & 1 == 1

def extract_and_decode():
    select_clause = []
    for col in fields:
        select_clause.append({
            "Column": {"Expression": {"SourceRef": {"Source": col["source"]}}, "Property": col["property"]},
            "Name": f"{col['entity']}.{col['property']}"
        })

    payload = {
        "version": "1.0.0",
        "queries": [{
            "Query": {
                "Commands": [{
                    "SemanticQueryDataShapeCommand": {
                        "Query": {
                            "Version": 2,
                            "From": [
                                {"Name": "c", "Entity": "ContractHistory", "Type": 0},
                                {"Name": "m", "Entity": "MasterContracts", "Type": 0}
                            ],
                            "Select": select_clause
                        },
                        "Binding": {
                            "Primary": {"Groupings": [{"Projections": list(range(len(fields)))}]},
                            "DataReduction": {"DataVolume": 3, "Primary": {"Top": {"Count": 10000}}}, # Fetch full 10k rows
                            "Version": 1
                        }
                    }
                }]
            },
            "ApplicationContext": {
                "DatasetId": "e59519f4-8037-4443-9ca1-6d0447952892",
                "Sources": [{"ReportId": "5c4b9dc5-4573-4b62-9f4e-fe329b24db5c", "VisualId": "5cd4ea60c49686e59640"}]
            }
        }],
        "cancelQueries": [],
        "modelId": 552006
    }

    req = urllib.request.Request(
        "https://wabi-us-gov-iowa-api.analysis.usgovcloudapi.net/public/reports/querydata?synchronous=true",
        data=json.dumps(payload).encode(),
        headers={
            "x-powerbi-resourcekey": "6ff2c073-64c4-4f85-ad57-4ef52113ca44",
            "content-type": "application/json;charset=UTF-8",
            "accept": "application/json, text/plain, */*",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64)",
            "referer": "https://app.powerbigov.us/",
            "activityid": str(uuid.uuid4()),
            "requestid": str(uuid.uuid4())
        }
    )

    ctx = ssl._create_unverified_context()

    try:
        response_data = json.loads(urllib.request.urlopen(req, context=ctx).read())
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR {e.code}: {e.reason}")
        print(e.read().decode('utf-8'))
        return

    # Check for silent odata errors
    data_shapes = response_data.get("results", [{}])[0].get("result", {}).get("data", {}).get("dsr", {}).get("DataShapes", [])
    for shape in data_shapes:
        if "odata.error" in shape:
            print(f"POWERBI REJECTED: {shape['odata.error']['message']['value']}")
            return

    dsr = response_data['results'][0]['result']['data']['dsr']['DS'][0]
    dm0 = dsr['PH'][0]['DM0']
    value_dicts = dsr.get('ValueDicts', {})

    structure = dm0[0]['S']
    num_cols = len(structure)
    
    decoded_rows = []
    prev_item = None
    
    for item in dm0:
        current_item = item.get("C", []).copy()
        
        # 1. Reconstruct using R (repeat) and Ø (delete/null) bitmasks
        if "R" in item or "Ø" in item:
            copy_bitset = item.get("R", 0)
            delete_bitset = item.get("Ø", 0)
            
            reconstructed = []
            c_idx = 0
            for i in range(num_cols):
                if is_bit_set(i, copy_bitset):
                    reconstructed.append(prev_item[i])
                elif is_bit_set(i, delete_bitset):
                    reconstructed.append(None)
                else:
                    reconstructed.append(current_item[c_idx])
                    c_idx += 1
            current_item = reconstructed
        
        prev_item = current_item
        
        # 2. Resolve index mappings against ValueDicts
        row_values = []
        for i, val in enumerate(current_item):
            if val is None:
                row_values.append("")
                continue
            
            col_meta = structure[i]
            if 'DN' in col_meta:
                dict_key = col_meta['DN']
                if dict_key in value_dicts and isinstance(val, int) and val < len(value_dicts[dict_key]):
                    row_values.append(value_dicts[dict_key][val])
                else:
                    row_values.append(val)
            else:
                # Handle dates (T: 7 is datetime, stored as millisecond timestamp)
                if col_meta.get('T') == 7 and isinstance(val, (int, float)):
                    dt = datetime.datetime.fromtimestamp(val / 1000.0, tz=datetime.timezone.utc)
                    row_values.append(dt.strftime('%Y-%m-%d'))
                else:
                    row_values.append(val)
                    
        decoded_rows.append(row_values)

    # Write to ramdisk (primary/fast path)
    output_file = os.path.join(RAMDISK_DIR, "contracts.csv")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(expected_headers)
        writer.writerows(decoded_rows)

    # Also persist a durable copy to data/raw/ (relative to repo root, portable across machines)
    repo_root = Path(__file__).resolve().parents[3]  # adjust index if this file moves
    persistent = repo_root / "data" / "raw" / "contracts.csv"
    persistent.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output_file, persistent)
    print(f"Also saved to {persistent}")

    print(f"Successfully processed {len(decoded_rows)} records into {output_file}")

if __name__ == "__main__":
    extract_and_decode()